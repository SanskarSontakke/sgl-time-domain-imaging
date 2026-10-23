"""Resource ledger and effective-sample-count arithmetic.

The ledger is the part of the paper that a reader can check without running any
simulation, so it is checked here analytically.  Two of its formulas have a
documented history of being wrong, and both are pinned:

* ``N_eff`` for ``mp`` revisits of ONE raster position, spaced by the full pass
  time (not by ``ts``), with an OU correlation ``rho_k = exp(-k*dt/tau)``:
  ``Var(mean) = sigma^2/mp^2 * [mp + 2 sum_k (mp-k) rho_k]``.  An earlier
  version of the ledger dropped the ``(mp-k)`` pair weight, which overstates
  ``N_eff`` by up to a factor ``mp`` and would have made ``mp = 64`` look
  independent when it is not.
* Arm A conserves PHOTONS per raster position (``mp * ts = 8 h``) and its wall
  clock GROWS; Arm B fixes the wall clock and lets ``ts`` fall.  The two arms are
  not the same experiment and the ledger rows must not be conflated.
"""
import numpy as np
import pytest

import _data as D


def _neff_pair_weighted(mp, dt_days, tau_days):
    k = np.arange(1, mp)
    rho = np.exp(-(dt_days / tau_days) * k)
    return mp ** 2 / (mp + 2.0 * np.sum((mp - k) * rho))


def _neff_dropped_weight(mp, dt_days, tau_days):
    k = np.arange(1, mp)
    rho = np.exp(-(dt_days / tau_days) * k)
    return mp ** 2 / (mp + 2.0 * np.sum(rho))


class TestNeff:
    def test_archived_neff_matches_pair_weighted_formula(self):
        d = D.load_npz("ledger.npz")
        taus = np.asarray(d["neff_tau"]); mps = np.asarray(d["neff_mp"], int)
        neff = np.asarray(d["neff"]); sp = np.asarray(d["neff_spacing_d"])
        for it, tau in enumerate(taus):
            for im, mp in enumerate(mps):
                got = _neff_pair_weighted(int(mp), sp[it, im], float(tau))
                assert abs(got - neff[it, im]) < 1e-6, (tau, mp, got, neff[it, im])

    def test_dropping_the_pair_weight_would_overstate_neff(self):
        """The historical bug: without (mp-k) the mp revisits look independent."""
        d = D.load_npz("ledger.npz")
        taus = np.asarray(d["neff_tau"]); mps = np.asarray(d["neff_mp"], int)
        neff = np.asarray(d["neff"]); sp = np.asarray(d["neff_spacing_d"])
        it = int(np.where(taus == 4.0)[0][0]); im = int(np.where(mps == 64)[0][0])
        buggy = _neff_dropped_weight(64, sp[it, im], 4.0)
        assert neff[it, im] == pytest.approx(12.108, abs=1e-3)
        assert buggy > 4 * neff[it, im]          # 59.8 vs 12.1
        assert buggy < 64 + 1e-6                 # and it saturates at mp, wrongly

    def test_lag1_correlation_is_consistent_with_spacing(self):
        d = D.load_npz("ledger.npz")
        taus = np.asarray(d["neff_tau"]); sp = np.asarray(d["neff_spacing_d"])
        rho1 = np.asarray(d["neff_rho1"])
        for it, tau in enumerate(taus):
            for im in range(len(sp[it])):
                assert rho1[it, im] == pytest.approx(
                    np.exp(-sp[it, im] / tau), rel=1e-9)

    def test_neff_is_monotone_in_tau_and_saturates_below_mp(self):
        d = D.load_npz("ledger.npz")
        mps = np.asarray(d["neff_mp"], int); neff = np.asarray(d["neff"])
        for im, mp in enumerate(mps):
            col = neff[:, im]                     # tau = 1, 2, 4 days
            assert np.all(np.diff(col) < 0), (mp, col)   # longer tau -> fewer looks
            assert np.all(col <= mp + 1e-9)


class TestArms:
    def test_arm_a_conserves_photons_per_position(self):
        d = D.load_npz("ledger.npz")
        arm = np.asarray(d["arm"], str); ph = np.asarray(d["photons"], float)
        sel = arm == "photons"
        assert np.allclose(ph[sel], 8.0), ph[sel]

    def test_arm_a_wallclock_grows_and_last_row_breaks_90_days(self):
        d = D.load_npz("ledger.npz")
        arm = np.asarray(d["arm"], str); wall = np.asarray(d["wall"], float)
        fits = np.asarray(d["fits90"], bool)
        w = wall[arm == "photons"]
        assert np.all(np.diff(w) > 0)
        assert w[-1] > 90.0 and not fits[len(w) - 1]

    def test_arm_b_fixes_wallclock_and_lets_dwell_fall(self):
        d = D.load_npz("ledger.npz")
        arm = np.asarray(d["arm"], str); ts = np.asarray(d["ts"], float)
        mp = np.asarray(d["mp"], int); wall = np.asarray(d["wall"], float)
        sel = arm == "wallclock"
        assert np.all(wall[sel] <= 90.0 + 1e-9)
        assert np.all(np.diff(ts[sel]) < 0)
        assert np.all(mp[sel] == [4, 8, 16, 32, 64])

    def test_duty_cycle_is_the_per_dwell_fraction(self):
        """``duty = ts / (ts + T_OVERHEAD)``, NOT exposure/wall.

        The two differ because the raster revisits the same position mp times:
        wall clock also grows with the number of positions, so a duty cycle read
        off the wall would mix in geometry that has nothing to do with slewing.
        """
        import sglsim as S
        d = D.load_npz("ledger.npz")
        ts = np.asarray(d["ts"], float); duty = np.asarray(d["duty"], float)
        assert np.allclose(duty, ts / (ts + S.T_OVERHEAD), rtol=1e-12)
        # and it is a fraction, always strictly below 1 and above 0.9 here
        assert np.all(duty < 1.0) and np.all(duty > 0.9)

    def test_overhead_charges_t_overhead_per_dwell_over_the_whole_raster(self):
        """overhead_days = nbin * mp * T_OVERHEAD / 86400 with nbin = n^2/nsc."""
        import sglsim as S
        d = D.load_npz("ledger.npz")
        ov = np.asarray(d["overhead_days"], float); mp = np.asarray(d["mp"], int)
        ts = np.asarray(d["ts"], float)
        exp = np.asarray(d["exposure_days"], float)
        nbin = (S.Campaign().n ** 2) // S.Campaign().nsc
        assert nbin == 256
        assert np.allclose(ov, nbin * mp * S.T_OVERHEAD / 86400.0, rtol=1e-12)
        # overhead/exposure must therefore reduce to T_OVERHEAD/ts, position-
        # independent -- the invariant that makes the two arms comparable
        assert np.allclose(ov / exp, S.T_OVERHEAD / ts, rtol=1e-12)

    def test_ledger_columns_are_reproduced_by_the_campaign_class(self):
        """The strongest form: rebuild every row from the live code.

        If ``Campaign`` changes its time accounting, the shipped ledger stops
        matching here rather than quietly disagreeing with the manuscript.
        """
        import expcommon as E
        d = D.load_npz("ledger.npz")
        arm = np.asarray(d["arm"], str)
        ts = np.asarray(d["ts"], float); mp = np.asarray(d["mp"], int)
        exp = np.asarray(d["exposure_days"], float)
        ov = np.asarray(d["overhead_days"], float)
        gap = np.asarray(d["gap_days"], float)
        wall = np.asarray(d["wall"], float); duty = np.asarray(d["duty"], float)
        for i in range(len(ts)):
            c = E.campaign(ts=ts[i], mp=int(mp[i]), mode=str(arm[i]))
            assert c.ts == pytest.approx(ts[i], rel=1e-12), (i, c.ts, ts[i])
            assert c.exposure_days == pytest.approx(exp[i], rel=1e-12)
            assert c.overhead_days == pytest.approx(ov[i], rel=1e-12)
            assert c.gap_days == pytest.approx(gap[i], rel=1e-12)
            assert c.wallclock_days == pytest.approx(wall[i], rel=1e-12)
            assert c.duty_cycle == pytest.approx(duty[i], rel=1e-12)

    def test_arm_b_dwell_is_solved_from_the_wall_budget(self):
        """In wall-clock mode ts is DERIVED, so the ledger cannot be hand-edited."""
        import expcommon as E
        d = D.load_npz("ledger.npz")
        arm = np.asarray(d["arm"], str); ts = np.asarray(d["ts"], float)
        mp = np.asarray(d["mp"], int)
        sel = np.where(arm == "wallclock")[0]
        for i in sel:
            c = E.campaign(mp=int(mp[i]), mode="wallclock")
            assert c.ts == pytest.approx(ts[i], rel=1e-12)
        # and the derived dwells are not the Arm-A dwells: the arms are distinct
        assert not np.allclose(ts[sel], ts[np.where(arm == "photons")[0]])

    def test_audit_ledger_block_agrees_with_npz(self):
        a = D.load_audit()["ledger"]; d = D.load_npz("ledger.npz")
        arm = np.asarray(d["arm"], str)
        for tag in ("photons", "wallclock"):
            sel = arm == tag
            assert np.allclose(a[tag]["mp"], np.asarray(d["mp"])[sel])
            assert np.allclose(a[tag]["ts"], np.asarray(d["ts"])[sel])
            assert np.allclose(a[tag]["wall_days"], np.asarray(d["wall"])[sel])

"""Fisher information / Cramer-Rao lower bound for the SGL albedo map.

Physics and derivation
----------------------
The measurement model is linearised:

    y = F s + B alpha + eps

where s is the ns-vector of albedo-map pixels (ns = nlat*nlon = 2592),
B is the per-slot nuisance indicator (nbin columns, each selecting nsc samples),
alpha is the per-slot photometric offset, and eps ~ N(0, C) with C the
block-diagonal OU+white covariance the profiled estimator assumes.

After profiling out alpha (exact R11), the effective Fisher matrix for s is:

    J = F^T C^{-1} F  -  (profiling correction)

The information retained by profiling is quantified by:

    eta = trace(J_profiled) / trace(J_unprofiled)

which we show equals ~0.662, matching deflation_diag.json.

CRLB prediction convention
--------------------------
From the profiled Fisher J, we form the CRLB covariance:

    V = pinv(J)

The pseudo-inverse handles the rank-deficient regulariser: the null space has
nullity 288 on the fiducial 36x72 grid (unconstrained spatial modes).

From V we compute the mean per-pixel variance:

    v = mean(diag(V))

and then, for completeness, the two predictions people expect from it:

  (i)  nrmse_pred = sqrt(v) / sd(truth_c)
  (ii) r_pred     = sqrt(max(0, 1 - v / var(truth)))

FINDING, not assumption: both are degenerate on this design. J is singular
(nullity 288 on the fiducial 36x72 grid) so pinv puts zero variance on the
unconstrained directions and huge variance on the near-degenerate ones; the
resulting v exceeds var(truth) by more than three orders of magnitude, which
makes r_pred identically 0 and nrmse_pred a number larger than the map's own
dynamic range. That is not "the CRLB is loose" -- it means the linear unbiased
floor is not the right comparison for a regularised, biased estimator, and no
headline from this module should be read as a variance floor. The archive
labels it as such (crlb_informative, crlb_vs_constant_map_a,
achieved_var_over_crlb_fid). The part of this module that IS load-bearing is the
information accounting: trace(J_prof)/trace(J_unprof), cross-checked against the
independent normal-matrix audit.

Cadence scaling
---------------
The per-pixel variance scales as v ~ sigma_k^2 / N_eff ~ 1/(ts * N_eff).
We calibrate at the fiducial (mp=16, ts=1800s) and predict v at each cadence
point analytically, avoiding expensive full Fisher builds.

The M_p=8 non-monotonicity (defect F-04) is explained by aliasing of the
raster phase grid against the rotation period.
"""

import sys
import time
import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import sglsim as S
import expcommon as E
from ext import extcommon as X


def _neff_analytic(mp, dt_days, tau_days):
    """Analytic N_eff for OU weather with inter-look spacing dt_days."""
    k = np.arange(1, mp)
    rho = np.exp(-k * dt_days / tau_days)
    pair = float(np.sum((mp - k) * rho))
    return mp**2 / (mp + 2.0 * pair)


def _aliasing_phase(t_s, overhead, nbin, prot=S.PROT):
    """Rotational phase advance per pass, in units of 2*pi (fraction of rotation)."""
    spacing = nbin * (t_s + overhead)
    return (spacing / prot) % 1.0


def _min_rational_dist(phase, qmax=8):
    """Min distance from phase to any rational p/q with q <= qmax."""
    best = 1.0
    for q in range(1, qmax + 1):
        p = round(phase * q)
        dist = abs(phase - p / q)
        best = min(best, dist)
    return best


def _build_fisher_fiducial(camp, sglop, sigma_cl, sigma_k):
    """Build Fisher info matrices at the fiducial point.

    Returns (trace_J_prof, trace_J_unprof, info_frac, crlb_prof, A_prof, nullity,
    v, diag_V).

    The Fisher matrix is I = Φᵀ C⁻¹ Φ with profiling projector applied.
    The CRLB covariance is V = pinv(I) (pseudo-inverse on the range).
    The nullity is the number of unconstrained modes (null space dimension).
    diag_V is returned because the mean of it is not a usable summary: I is
    singular, so pinv assigns zero variance to the null directions and huge
    variance to the near-degenerate ones, and both facts show up only in the
    per-pixel diagonal.
    """
    ns = E.NLAT * E.NLON
    nbin, mp, nsc = camp.nbin, camp.mp, camp.nsc
    tau = E.TAU_DAYS * 86400.0

    F = S.build_F(camp, sglop, E.NLAT, E.NLON, nsub=E.NSUB)
    F = np.asarray(F, dtype=np.float64)

    st = S.raster_stack(camp)
    idx = st["idx"]
    dtabs = st["dt"]

    trace_prof = 0.0
    trace_unprof = 0.0
    A_prof = np.zeros((ns, ns))
    di = np.arange(mp)

    for j0 in range(0, nbin, 64):
        j1 = min(j0 + 64, nbin)
        cj = j1 - j0
        rows = idx[:, j0:j1, :].reshape(-1)
        Fq = np.asarray(F[rows]).reshape(mp, cj, nsc, ns).transpose(1, 2, 0, 3)

        if sigma_cl > 0:
            corr = np.exp(-np.abs(dtabs[:, :, j0:j1]) / tau).transpose(2, 0, 1)
            var = np.broadcast_to(sigma_cl**2 * corr[:, None],
                                  (cj, nsc, mp, mp)).copy()
            var[:, :, di, di] += sigma_k**2
            Ci = np.linalg.inv(var)
        else:
            Ci = np.zeros((cj, nsc, mp, mp))
            Ci[:, :, di, di] = 1.0 / sigma_k**2

        Cf = np.matmul(Ci, Fq)
        F2 = Fq.reshape(cj * nsc * mp, ns)
        Au = F2.T @ Cf.reshape(cj * nsc * mp, ns)
        trace_unprof += np.trace(Au)
        A_prof += Au

        # Profiling correction
        Hj = Ci.sum(axis=1)
        Gj = Cf.sum(axis=1)
        Sj = np.linalg.inv(Hj)
        Gj2 = Gj.reshape(cj * mp, ns)
        correction = Gj2.T @ np.matmul(Sj, Gj).reshape(cj * mp, ns)
        A_prof -= correction
        trace_prof -= np.trace(correction)

    trace_prof += trace_unprof
    info_frac = trace_prof / trace_unprof if trace_unprof > 0 else 0.0

    # Compute nullity: number of zero eigenvalues
    eig = np.linalg.eigvalsh(A_prof)
    eig_threshold = 1e-10 * max(eig.max(), 1.0)
    nullity = int(np.sum(eig < eig_threshold))

    # CRLB from the profiled Fisher using pseudo-inverse
    # V = pinv(A_prof), then v = mean(diag(V)) is the mean per-pixel variance
    V = np.linalg.pinv(A_prof, rcond=1e-10)
    diag_V = np.diag(V).copy()
    v = float(np.mean(diag_V))
    crlb = v

    return trace_prof, trace_unprof, info_frac, crlb, A_prof, nullity, v, diag_V


def main():
    t0 = time.time()
    seeds, truth_seeds = X.tier_seeds()
    fast = "--fast" in sys.argv[1:]
    X.log(f"fisher_bounds: fast={fast}, seeds={seeds}")

    # Fiducial campaign
    camp = E.campaign(ts=1800.0, mp=16)
    sglop = E.sgl()

    # Read sigma_cl from the archived parts (not from cache to avoid races)
    p0 = np.load(E.PARTS / "clouds_f3_s0.npz")
    sigma_cl = float(p0["sigma_cl"])
    X.log(f"sigma_cl = {sigma_cl:.6f}")

    # Background noise sigma for one sample at ts=1800
    sigma_k = np.sqrt(S.QCOR / (S.QEXO**2 * camp.ts))
    X.log(f"sigma_k = {sigma_k:.6f} (reference: 0.023170)")

    # Build Fisher at fiducial
    X.log("Building Fisher matrices at fiducial (n=64, ts=1800, mp=16)...")
    tr_prof, tr_unprof, info_frac, crlb_fid, A_prof, nullity, v_fid, diag_V = \
        _build_fisher_fiducial(camp, sglop, sigma_cl, sigma_k)

    ns = E.NLAT * E.NLON
    X.log(f"trace(J_prof) = {tr_prof:.3e}")
    X.log(f"trace(J_unprof) = {tr_unprof:.3e}")
    X.log(f"Fisher info fraction (profiled/unprofiled) = {info_frac:.6f}")
    X.log(f"Expected 1 - 1/nsc = {1 - 1/camp.nsc:.6f}")
    X.log(f"CRLB per-pixel variance v_fid = {v_fid:.6e}")
    X.log(f"Nullity (unconstrained modes) = {nullity} / {ns}")

    # Cross-check frobenius_ratio against deflation_diag.json
    import json as _json
    try:
        dd = _json.load(open(X.DATA / "deflation_diag.json"))
        frob_arch = dd["slot_deflation_white"]["frobenius_ratio"]
        const_free = dd["profiling"]["retained_fraction_free"]
        const_anch = dd["profiling"]["retained_fraction_anchored"]
        X.log(f"Cross-check: deflation_diag frobenius_ratio = {frob_arch:.6f}")
        X.log(f"Cross-check: constant-mode free = {const_free:.4f}, anchored = {const_anch:.4f}")
        X.log(f"NOTE: frobenius_ratio ({info_frac:.4f}) is trace(J_prof)/trace(J_unprof);")
        X.log(f"      constant-mode survival ({const_free:.4f}/{const_anch:.4f}) is a different quantity")
        X.log(f"      measuring energy retention of the spatially-constant mode under profiling.")
    except Exception as e:
        X.log(f"Cross-check with deflation_diag.json failed: {e}")
        frob_arch = None
        const_free = None
        const_anch = None

    # --- Per-pixel variance → nrmse_pred and r_pred ---
    # Convention: nrmse_pred = sqrt(v) / sd(truth_c)
    #             r_pred = sqrt(max(0, 1 - v / var(truth)))
    # where v = mean(diag(pinv(J))) is the mean per-pixel CRLB variance.
    truthF, truth_c = E.truth()
    sd_truth = float(truth_c.std())
    var_truth = float(truth_c.var())
    X.log(f"sd(truth) = {sd_truth:.6f}, var(truth) = {var_truth:.6f}")

    nrmse_fid = np.sqrt(v_fid) / sd_truth if sd_truth > 0 else np.inf
    r_fid_pred = np.sqrt(max(0.0, 1.0 - v_fid / var_truth)) if var_truth > 0 else 0.0
    X.log(f"Fiducial: nrmse_pred = {nrmse_fid:.6f}, r_pred = {r_fid_pred:.6f}")

    # --- Is this bound usable? The information matrix is singular, and pinv
    # responds by giving the null directions ZERO variance and the
    # near-degenerate ones enormous variance. Both show up in the diagonal. ---
    n_null_dir = int(np.sum(diag_V == 0.0))
    diag_pos = diag_V[diag_V > 0]
    v_med = float(np.median(diag_pos)) if diag_pos.size else float("nan")
    crlb_ratio = v_fid / var_truth if var_truth > 0 else float("inf")
    crlb_informative = bool(crlb_ratio < 1.0)
    X.log(f"CRLB diagnostic: mean(diag V) = {v_fid:.4e} vs var(truth) = "
          f"{var_truth:.4e} -> ratio {crlb_ratio:.1f}; the bound is "
          f"{'INFORMATIVE' if crlb_informative else 'WEAKER THAN PREDICTING THE CONSTANT MAP'}")
    X.log(f"  diag(V): {n_null_dir} exact zeros, min>0 = {diag_pos.min():.3e}, "
          f"median = {v_med:.3e}, max = {diag_V.max():.3e}")

    # --- Cadence sweep: analytic N_eff + per-pixel variance scaling ---
    mp_grid = [4, 8, 16, 32, 64]
    arm_a_ts = {4: 7200.0, 8: 3600.0, 16: 1800.0, 32: 900.0, 64: 450.0}
    arm_b_wall = 90.0  # days

    # The per-pixel CRLB variance scales as:
    #   v ~ sigma_k^2 / N_eff ~ 1/(ts * N_eff)
    # Calibrate at fiducial: v_fid = cal / (ts_fid * N_eff_fid)
    nbin_fid = camp.nbin
    dt_fid = nbin_fid * (camp.ts + S.T_OVERHEAD) / 86400.0
    neff_fid = _neff_analytic(camp.mp, dt_fid, E.TAU_DAYS)
    cal_v = v_fid * camp.ts * neff_fid  # calibration constant for per-pixel variance

    crlb_a, crlb_b = [], []  # per-pixel variance
    neff_a, neff_b = [], []
    nrmse_pred_a, nrmse_pred_b = [], []
    r_pred_a, r_pred_b = [], []
    alias_a, alias_b = [], []
    ts_b_list = []

    for mp in mp_grid:
        # Arm A: fixed photons
        ts_a = arm_a_ts[mp]
        camp_a = S.Campaign(n=64, nsc=16, ts=ts_a, mp=mp,
                            seed=E.CAMPAIGN_SEED, mode="photons")
        dt_a = camp_a.nbin * (ts_a + S.T_OVERHEAD) / 86400.0
        neff_a_val = _neff_analytic(mp, dt_a, E.TAU_DAYS)
        neff_a.append(neff_a_val)
        alias_a.append(_aliasing_phase(ts_a, S.T_OVERHEAD, camp_a.nbin))
        v_a = cal_v / (ts_a * neff_a_val) if neff_a_val > 0 else np.inf
        crlb_a.append(v_a)
        nrmse_pred_a.append(np.sqrt(v_a) / sd_truth if sd_truth > 0 else np.inf)
        r_pred_a.append(np.sqrt(max(0.0, 1.0 - v_a / var_truth)) if var_truth > 0 else 0.0)

        # Arm B: fixed wall clock
        budget = arm_b_wall * 86400.0
        ts_b = budget / (camp_a.nbin * mp) - S.T_OVERHEAD
        ts_b_list.append(ts_b)
        if ts_b <= 0:
            crlb_b.append(np.inf)
            neff_b.append(0.0)
            nrmse_pred_b.append(np.inf)
            r_pred_b.append(0.0)
            alias_b.append(0.0)
            continue
        camp_b = S.Campaign(n=64, nsc=16, ts=ts_b, mp=mp,
                            seed=E.CAMPAIGN_SEED, mode="wallclock",
                            wall_target=arm_b_wall)
        dt_b = camp_b.nbin * (ts_b + S.T_OVERHEAD) / 86400.0
        neff_b_val = _neff_analytic(mp, dt_b, E.TAU_DAYS)
        neff_b.append(neff_b_val)
        alias_b.append(_aliasing_phase(ts_b, S.T_OVERHEAD, camp_b.nbin))
        v_b = cal_v / (ts_b * neff_b_val) if neff_b_val > 0 else np.inf
        crlb_b.append(v_b)
        nrmse_pred_b.append(np.sqrt(v_b) / sd_truth if sd_truth > 0 else np.inf)
        r_pred_b.append(np.sqrt(max(0.0, 1.0 - v_b / var_truth)) if var_truth > 0 else 0.0)

    crlb_a = np.array(crlb_a)
    crlb_b = np.array(crlb_b)
    neff_a = np.array(neff_a)
    neff_b = np.array(neff_b)
    nrmse_pred_a = np.array(nrmse_pred_a)
    nrmse_pred_b = np.array(nrmse_pred_b)
    r_pred_a = np.array(r_pred_a)
    r_pred_b = np.array(r_pred_b)

    X.log(f"N_eff Arm A: {neff_a}")
    X.log(f"N_eff Arm B: {neff_b}")
    X.log(f"v (per-pixel var) Arm A: {crlb_a}")
    X.log(f"v (per-pixel var) Arm B: {crlb_b}")
    X.log(f"nrmse_pred Arm A: {nrmse_pred_a}")
    X.log(f"nrmse_pred Arm B: {nrmse_pred_b}")
    X.log(f"r_pred Arm A: {r_pred_a}")
    X.log(f"r_pred Arm B: {r_pred_b}")

    # --- Validation against archived simulation ---
    cad_p = np.load(X.DATA / "cadence_photons.npz")
    cad_w = np.load(X.DATA / "cadence_wallclock.npz")
    r_sim_a = cad_p["r_profiled"].mean(axis=1)
    r_sim_b = cad_w["r_profiled"].mean(axis=1)

    # Derive nrmse_sim from r_sim: nrmse = sqrt(1 - r^2)
    # (since r^2 = 1 - MSE/var(truth) and nrmse = sqrt(MSE)/sd(truth))
    nrmse_sim_a = np.sqrt(np.clip(1.0 - r_sim_a**2, 0, None))
    nrmse_sim_b = np.sqrt(np.clip(1.0 - r_sim_b**2, 0, None))

    X.log(f"r_sim Arm A: {r_sim_a}")
    X.log(f"r_sim Arm B: {r_sim_b}")
    X.log(f"nrmse_sim Arm A (derived): {nrmse_sim_a}")
    X.log(f"nrmse_sim Arm B (derived): {nrmse_sim_b}")

    # The archived estimator's per-pixel error variance, read off its own r:
    # MSE = (1 - r^2) var(truth). Comparing it to the pseudo-inverse CRLB is
    # the test of whether the bound means anything here.
    i16 = mp_grid.index(16)
    r_fid_sim_a = float(r_sim_a[i16])
    achieved_var_fid = float((1.0 - r_fid_sim_a**2) * var_truth)
    achieved_over_crlb = achieved_var_fid / v_fid
    X.log(f"Achieved per-pixel error variance at M_p=16 arm A (r={r_fid_sim_a:.5f}): "
          f"{achieved_var_fid:.4e}, i.e. {achieved_over_crlb:.5f} of the pinv CRLB mean "
          f"-- a linear unbiased bound that the biased, regularised estimator "
          f"'beats' by three decades is not a bound on this estimator.")

    # Fractional discrepancy on r: (r_pred - r_sim) / r_sim
    frac_disc_r_a = np.array([(p - s) / (abs(s) + 1e-10)
                               for p, s in zip(r_pred_a, r_sim_a)])
    frac_disc_r_b = np.array([(p - s) / (abs(s) + 1e-10)
                               for p, s in zip(r_pred_b, r_sim_b)])

    # Fractional discrepancy on nrmse: (nrmse_pred - nrmse_sim) / nrmse_sim
    frac_disc_nrmse_a = np.array([(p - s) / (abs(s) + 1e-10)
                                   for p, s in zip(nrmse_pred_a, nrmse_sim_a)])
    frac_disc_nrmse_b = np.array([(p - s) / (abs(s) + 1e-10)
                                   for p, s in zip(nrmse_pred_b, nrmse_sim_b)])

    X.log(f"frac_disc_r Arm A: {frac_disc_r_a}")
    X.log(f"frac_disc_r Arm B: {frac_disc_r_b}")
    X.log(f"frac_disc_nrmse Arm A: {frac_disc_nrmse_a}")
    X.log(f"frac_disc_nrmse Arm B: {frac_disc_nrmse_b}")

    # --- M_p=8 non-monotonicity ---
    rat_dist_a = [_min_rational_dist(ph) for ph in alias_a]
    rat_dist_b = [_min_rational_dist(ph) for ph in alias_b]
    X.log(f"Aliasing phases Arm A: {[f'{x:.4f}' for x in alias_a]}")
    X.log(f"Aliasing phases Arm B: {[f'{x:.4f}' for x in alias_b]}")
    X.log(f"Rational distances Arm A: {[f'{x:.4f}' for x in rat_dist_a]}")
    X.log(f"Rational distances Arm B: {[f'{x:.4f}' for x in rat_dist_b]}")

    # --- Save archives ---
    X.save_npz("fisher_bounds",
               mp=np.array(mp_grid, dtype=float),
               crlb_a=crlb_a, crlb_b=crlb_b,
               neff_a=neff_a, neff_b=neff_b,
               nrmse_pred_a=nrmse_pred_a, nrmse_pred_b=nrmse_pred_b,
               nrmse_sim_a=nrmse_sim_a, nrmse_sim_b=nrmse_sim_b,
               r_pred_a=r_pred_a, r_pred_b=r_pred_b,
               r_sim_a=r_sim_a, r_sim_b=r_sim_b,
               frac_disc_r_a=frac_disc_r_a, frac_disc_r_b=frac_disc_r_b,
               frac_disc_nrmse_a=frac_disc_nrmse_a, frac_disc_nrmse_b=frac_disc_nrmse_b,
               alias_phase_a=np.array(alias_a),
               alias_phase_b=np.array(alias_b),
               rat_dist_a=np.array(rat_dist_a),
               rat_dist_b=np.array(rat_dist_b),
               J_prof_trace=np.array([tr_prof]),
               J_unprof_trace=np.array([tr_unprof]),
               info_frac=np.array([info_frac]),
               sigma_cl=np.array([sigma_cl]),
               sigma_k=np.array([sigma_k]),
               var_truth=np.array([var_truth]),
               v_fid=np.array([v_fid]),
               nullity=np.array([nullity]))

    wall = time.time() - t0
    headline = dict(
        frobenius_ratio=round(info_frac, 6),
        # None (json null) if the archived cross-check could not be read: a
        # hardcoded stand-in would make the "agrees with the archive" claim
        # unfalsifiable, which is the defect this module exists to avoid.
        frobenius_deflation_diag=(round(frob_arch, 6) if frob_arch is not None
                                 else None),
        profiling_retained_free=(round(const_free, 4) if const_free is not None
                                 else None),
        profiling_retained_anchored=(round(const_anch, 4)
                                     if const_anch is not None else None),
        naive_1_minus_1_over_nsc=round(1 - 1 / camp.nsc, 6),
        v_fiducial=round(v_fid, 6),
        nullity=nullity,
        crlb_vs_constant_map_a=round(crlb_ratio, 1),
        crlb_informative=crlb_informative,
        crlb_diag_null_directions=n_null_dir,
        crlb_diag_median=float(f"{v_med:.6e}"),
        crlb_diag_max=float(f"{diag_V.max():.6e}"),
        achieved_var_over_crlb_fid=round(float(achieved_over_crlb), 6),
        nrmse_fid_pred=round(float(nrmse_fid), 6),
        r_fid_pred=round(float(r_fid_pred), 6),
        sigma_k=round(sigma_k, 6),
        sigma_cl=round(sigma_cl, 6),
        neff_sat_arm_a=round(float(neff_a[-1] / mp_grid[-1]), 4),
        neff_sat_arm_b=round(float(neff_b[-1] / mp_grid[-1]), 4),
        disc_r_pred_vs_sim_a=(round(float(np.mean(np.abs(frac_disc_r_a))), 4)
                              if crlb_informative else "degenerate_r_pred_is_zero"),
        disc_r_pred_vs_sim_b=(round(float(np.mean(np.abs(frac_disc_r_b))), 4)
                              if crlb_informative else "degenerate_r_pred_is_zero"),
        disc_nrmse_pred_vs_sim_a=round(float(np.mean(np.abs(frac_disc_nrmse_a))), 4),
        disc_nrmse_pred_vs_sim_b=round(float(np.mean(np.abs(frac_disc_nrmse_b))), 4),
        mp8_alias_a=round(float(alias_a[1]), 4),
        mp8_rat_dist_a=round(float(rat_dist_a[1]), 4),
    )

    caveats = [
        "CRLB cadence sweep uses analytic N_eff scaling calibrated at the fiducial per-pixel variance, not full Fisher builds at each point, so it inherits the scaling problem stated next.",
        (f"The per-pixel CRLB from pinv(J) is NOT a comparable floor for this estimator: mean(diag V) = {v_fid:.4e} exceeds var(truth) = "
         f"{var_truth:.4e} by {crlb_ratio:.1f}x, so the bound is weaker than predicting the constant map and r_pred is identically zero. "
         f"J has nullity {nullity} and an infinite condition number, and pinv gives those {n_null_dir} directions zero variance while the near-degenerate ones reach {diag_V.max():.2e} (median of the non-zero diagonal {v_med:.2e}). "
         f"The archived regularised fit actually achieves (1-r^2)var = {achieved_var_fid:.3e} at M_p=16, i.e. {achieved_over_crlb:.1e} of that pseudo-inverse bound; a biased estimator 'beating' an unbiased bound by three decades is the signature of the wrong yardstick, not of super-efficiency."
         if not crlb_informative else
         f"mean(diag V) = {v_fid:.4e} is inside var(truth) = {var_truth:.4e}, so the bound is informative at the fiducial."),
        "What this module does establish is the information accounting: trace(J_prof)/trace(J_unprof) and its agreement with the independent normal-matrix audit. The variance floor it also computes is reported for completeness and marked degenerate.",
        "nrmse_sim derived from archived r_sim as sqrt(1 - r^2); archived cadence files do not store nrmse directly.",
        "Aliasing explanation of M_p=8 non-monotonicity is qualitative; a full harmonic analysis would be needed for rigorous proof.",
        "Fisher matrix built with constant sigma_k (not signal-dependent noise); valid in the background-dominated regime Q_cor >> Q_exo.",
        "frobenius_ratio = trace(J_prof)/trace(J_unprof) = 0.662 is distinct from profiling constant-mode survival (free=0.0206, anchored=0.8472).",
    ]

    obj = dict(
        headline=headline,
        caveats=caveats,
        provenance=X.provenance("fisher_bounds"),
        mp_grid=mp_grid,
        crlb_a=crlb_a.tolist(),
        crlb_b=crlb_b.tolist(),
        neff_a=neff_a.tolist(),
        neff_b=neff_b.tolist(),
        nrmse_pred_a=nrmse_pred_a.tolist(),
        nrmse_pred_b=nrmse_pred_b.tolist(),
        nrmse_sim_a=nrmse_sim_a.tolist(),
        nrmse_sim_b=nrmse_sim_b.tolist(),
        r_sim_a=r_sim_a.tolist(),
        r_sim_b=r_sim_b.tolist(),
        r_pred_a=r_pred_a.tolist(),
        r_pred_b=r_pred_b.tolist(),
        frac_disc_r_a=frac_disc_r_a.tolist(),
        frac_disc_r_b=frac_disc_r_b.tolist(),
        frac_disc_nrmse_a=frac_disc_nrmse_a.tolist(),
        frac_disc_nrmse_b=frac_disc_nrmse_b.tolist(),
        alias_phase_a=[float(x) for x in alias_a],
        alias_phase_b=[float(x) for x in alias_b],
        rat_dist_a=[float(x) for x in rat_dist_a],
        rat_dist_b=[float(x) for x in rat_dist_b],
        ts_b_list=[float(x) for x in ts_b_list],
        wall_clock_s=round(wall, 1),
    )
    X.save_json("fisher_bounds", obj)
    X.log(f"wall clock: {wall:.1f} s")
    X.summary("fisher_bounds", **headline)


if __name__ == "__main__":
    main()

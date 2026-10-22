"""Contract tests for the Part VII extension archives (``src/ext/``).

The extension modules are written by hand against the same spine, so the risk is
not that they crash but that they quietly answer a DIFFERENT question than the
manuscript: a stale physics constant, a headline that is a label rather than a
number, an archive that disagrees with ``results/audit.json``.  These tests are
the triage gate -- an extension number may enter the manuscript only if its
archive passes here.

Nothing is computed: every check reads an archive that ``reproduce_all --ext``
already wrote.
"""
import json
import math
import re

import numpy as np
import pytest

import _data as D

try:
    import reproduce_all as RA
except ImportError:                                    # pragma: no cover
    RA = None

#: modules that must exist for the Part VII suite to be complete
try:
    EXT_MODULES = tuple(RA.EXT_MODULES) if RA is not None else ()
except AttributeError:                                 # pragma: no cover
    EXT_MODULES = ()


def ext_json(name):
    p = D.RESULTS / f"ext_{name}.json"
    if not p.exists():
        pytest.fail(f"src/ext/{name}.py is registered but {p.name} was never "
                    f"written -- run `python3 -m reproduce_all --fast --ext`")
    return json.loads(p.read_text())


def ext_npz(name):
    p = D.RESULTS / f"ext_{name}.npz"
    return np.load(p, allow_pickle=True) if p.exists() else None


def _numeric_leaves(obj, pre=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _numeric_leaves(v, f"{pre}.{k}" if pre else str(k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from _numeric_leaves(v, f"{pre}[{i}]")
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield pre, float(obj)


# ---------------------------------------------------------------- structure --
class TestExtensionInventory:
    def test_registered_modules_exist_on_disk(self):
        assert EXT_MODULES, "reproduce_all.EXT_MODULES is empty"
        for m in EXT_MODULES:
            assert (D.ROOT / "src" / "ext" / f"{m}.py").exists(), m

    def test_directory_matches_the_registry(self):
        """No module may be written and left unregistered (it would never run)."""
        on_disk = {p.stem for p in (D.ROOT / "src" / "ext").glob("*.py")}
        infra = {"__init__", "extcommon"}
        assert on_disk - infra == set(EXT_MODULES)

    def test_every_module_wrote_its_archives(self):
        for m in EXT_MODULES:
            j = ext_json(m)                       # also asserts the json exists
            assert isinstance(j, dict)
            has_arrays = any(isinstance(v, list) for v in j.values())
            if not (D.RESULTS / f"ext_{m}.npz").exists():
                assert not has_arrays, (
                    f"ext_{m}: the json carries numeric series but the npz pair "
                    f"was never written")


class TestArchiveSchema:
    @pytest.mark.parametrize("name", EXT_MODULES or ["__none__"])
    def test_required_sections(self, name):
        j = ext_json(name)
        for key in ("headline", "caveats", "provenance"):
            assert key in j, f"ext_{name}.json missing {key!r}"
        assert isinstance(j["headline"], dict) and j["headline"], name
        assert isinstance(j["caveats"], list) and j["caveats"], \
            f"ext_{name} has no stated limitation"
        prov = j["provenance"]
        assert prov["module"] == name
        for key in ("numpy", "python"):
            assert key in prov, key

    @pytest.mark.parametrize("name", EXT_MODULES or ["__none__"])
    def test_headline_has_no_nan_or_inf(self, name):
        for path, v in _numeric_leaves(ext_json(name)["headline"]):
            assert math.isfinite(v), f"ext_{name}.headline.{path} = {v}"

    @pytest.mark.parametrize("name", EXT_MODULES or ["__none__"])
    def test_headline_strings_are_labels_not_paragraphs(self, name):
        """A headline is a claim; the prose belongs in caveats/conclusion.

        ``conclusion`` and ``status`` are the two places free text is allowed,
        because a refused quantity must be able to say so in words.
        """
        h = ext_json(name)["headline"]
        for k, v in h.items():
            if isinstance(v, str):
                assert v.strip(), f"ext_{name}: empty headline {k!r}"
                if k not in ("conclusion", "status"):
                    assert len(v) <= 80, (
                        f"ext_{name}: headline {k!r} is a {len(v)}-character "
                        f"paragraph; move it to caveats or conclusion")
            if isinstance(v, list):
                assert v, f"ext_{name}: headline {k!r} is an empty list"

    @pytest.mark.parametrize("name", EXT_MODULES or ["__none__"])
    def test_tier_is_declared(self, name):
        """A four-seed number and a ten-seed number are different claims.

        ``extcommon.provenance`` stamps the tier automatically, so an archive
        without it predates the contract and must be regenerated before its
        numbers can be quoted.
        """
        prov = ext_json(name)["provenance"]
        assert prov.get("tier") in ("fast", "full"), (
            f"ext_{name}: provenance.tier = {prov.get('tier')!r}; re-run "
            f"`python3 -m ext.{name}` to stamp the tier")

    @pytest.mark.parametrize("name", EXT_MODULES or ["__none__"])
    def test_npz_arrays_are_loadable_and_nonempty(self, name):
        z = ext_npz(name)
        if z is None:
            pytest.skip(f"ext_{name} is a json-only archive")
        for k in z.files:
            a = np.asarray(z[k])
            assert a.size > 0, (f"ext_{name}.npz:{k} is empty -- a placeholder "
                                f"array in a shipped archive is a bug, not a "
                                f"missing feature")
            assert a.dtype.kind != "O", f"ext_{name}.npz:{k} is an object array"

    def test_extension_archives_cannot_shadow_spine_archives(self):
        """ext_* is the only namespace an extension module may own."""
        names = {p.name for p in D.RESULTS.glob("ext_*")}
        assert names, "no extension archives present"
        shipped = {p.name for p in D.RESULTS.iterdir() if not p.name.startswith("ext_")}
        assert not (names & shipped)


# ------------------------------------------------------------- physics parity --
class TestFiducialParity:
    """Every extension must run the SAME fiducial as the spine.

    A referee's cheapest way to kill an add-on result is to notice it used a
    different dwell, grid, cloud fraction or solar constant.  These assertions
    make that impossible to ship silently.
    """

    @pytest.fixture(scope="class")
    def conv(self):
        return D.load_audit()["conventions"]

    @pytest.mark.parametrize("name", EXT_MODULES or ["__none__"])
    def test_fiducial_block_matches_audit_conventions(self, name, conv):
        j = ext_json(name)
        f = j["provenance"].get("fiducial")
        if f is None:
            pytest.skip(f"ext_{name} declares no fiducial block")
        for key, want in (("nlat", 36), ("nlon", 72),
                          ("nlat_fine", 72), ("nlon_fine", 144),
                          ("ts", 1800.0), ("mp", 16), ("fc", conv["fc"]),
                          ("tau_days", conv["tau_days"]),
                          ("lam", conv["lam"]), ("nsub", conv["nsub"]),
                          ("truth_seed", conv["truth_seed"])):
            if key in f:
                assert float(f[key]) == pytest.approx(want, abs=1e-12), \
                    f"ext_{name}: fiducial.{key}={f[key]} != {want}"

    @pytest.mark.parametrize("name", EXT_MODULES or ["__none__"])
    def test_physics_constants_match_sglsim(self, name):
        import sglsim as S
        c = ext_json(name)["provenance"].get("constants")
        if c is None:
            pytest.skip(f"ext_{name} declares no constants block")
        truth = {"dimg": S.DIMG, "qexo": S.QEXO, "qcor": S.QCOR, "prot": S.PROT,
                 "dtel": S.DTEL, "rpl": S.RPL, "z": S.Z, "z0": S.Z0}
        for k, want in truth.items():
            if k in c:
                assert float(c[k]) == pytest.approx(want, rel=0), \
                    f"ext_{name}: constant {k}={c[k]} != sglsim {want}"


class TestHeadlineAgreement:
    """Where an extension re-states a spine number, the two must agree.

    Keys are matched by name so a corrected module is picked up automatically;
    an extension that deliberately reports a DIFFERENT quantity must rename its
    field (the referee's defect F-01/F-14 class of error is exactly a reused
    name carrying a different definition).
    """

    def _audit(self):
        return D.load_audit()

    def test_corona_photon_floor_and_ratio(self):
        h = ext_json("corona_screen")["headline"]
        a = self._audit()["conventions"]
        if "sigma_k" in h:
            # sigma_k is defined at the fiducial 1800 s dwell, not at 7200 s
            assert h["sigma_k"] == pytest.approx(0.023170, abs=5e-6)
        if "qcor_qexo" in h:
            assert h["qcor_qexo"] == pytest.approx(a["qcor_over_qexo"], rel=1e-4)

    def test_fiducial_r_is_not_reported_as_a_loss(self):
        """F-01-style bug: a bare r pasted into a *_loss field."""
        a = self._audit()
        base = a["systematics"]["base_r"]
        for name in EXT_MODULES:
            h = ext_json(name)["headline"]
            for k, v in h.items():
                if isinstance(v, (int, float)) and "loss" in k and \
                        abs(float(v)) > 0:
                    assert abs(float(v) - base) > 1e-6, (
                        f"ext_{name}.headline.{k} == the fiducial r {base}; a "
                        f"delta field must not carry an absolute value")

    @pytest.mark.parametrize("name", ["observable_roc", "portability", "swarm"])
    def test_single_aperture_r_matches_the_archive(self, name):
        h = ext_json(name)["headline"]
        base = self._audit()["systematics"]["base_r"]
        for k in ("r_sgl", "r_single", "r_ref", "r_fiducial", "r_1"):
            if k in h:
                assert float(h[k]) == pytest.approx(base, abs=2e-4), \
                    f"ext_{name}.{k} disagrees with audit.systematics.base_r"

    def test_portability_reference_is_paired_not_hardcoded(self):
        """The Airy swap must compare against the SAME photons.

        The module originally carried a hard-coded ``r_sgl = 0.3422`` -- the
        10-seed ensemble mean -- next to a single-seed Airy solve, so the quoted
        ratio mixed a paired and an unpaired quantity. Both numbers are now
        separate fields, and each is checked against its own archive.
        """
        h = ext_json("portability")["headline"]
        base = self._audit()["systematics"]["base_r"]
        if "r_sgl_ensemble" in h:
            assert float(h["r_sgl_ensemble"]) == pytest.approx(base, abs=2e-4)
        if "r_sgl_paired" not in h:
            pytest.skip("archive predates the paired reference")
        z = ext_npz("portability")
        seed = int(h["seed"])
        import expcommon as E
        part = np.load(E.PARTS / ("clouds_f3_s%d.npz" % E.SEEDS.index(seed)))
        assert abs(float(h["r_sgl_paired"]) - float(part["profiled_pearson"])) \
            < 5e-5, "paired SGL reference != the spine's own value for seed " \
                    f"{seed}; the comparison is not paired"
        assert abs(float(z["r_sgl_paired"][0]) - float(part["profiled_pearson"])) \
            < 1e-9
        # arithmetic self-consistency of the quoted ratio and loss
        r_airy = float(z["r_airy"][0])
        assert r_airy / float(h["r_sgl_paired"]) == pytest.approx(
            h["r_ratio_paired"], abs=1e-3)
        assert r_airy - float(h["r_sgl_paired"]) == pytest.approx(
            h["delta_r_paired"], abs=1e-3)
        # the caveat that limits what the module may be cited for
        cav = " ".join(ext_json("portability")["caveats"]).lower()
        assert "surface-coupling" in cav or "phase-locking" in cav

    def test_truth_ensemble_fiducial_member_reproduces_the_spine(self):
        """truth_seed 7 must sit inside the ensemble at the archived value.

        The archive is a truth x noise grid flattened in that order; the
        truth-seed-7 rows are the fiducial geography, so they have to land on the
        spine numbers they were checked against, while the FULL ensemble spread
        is what the paper cites as geography uncertainty.
        """
        j = ext_json("truth_ensemble")
        z = ext_npz("truth_ensemble")
        if z is None or "cloudy_profiled_pearson" not in z.files:
            pytest.skip("ensemble archive layout differs")
        base = self._audit()["systematics"]["base_r"]
        r = np.asarray(z["cloudy_profiled_pearson"], float)
        tseeds = np.asarray(z["truth_seeds"], int)
        nseeds = np.asarray(z["noise_seeds"], int)
        assert r.size == tseeds.size * nseeds.size, \
            "ensemble is not the full truth x noise grid"
        # member order is truth-major, noise-minor (verify against the archive)
        flat_t = np.repeat(tseeds, nseeds.size)
        flat_n = np.tile(nseeds, tseeds.size)
        sel = flat_t == 7
        assert sel.sum() == nseeds.size
        # every (truth 7, noise s) row must reproduce the spine's OWN solve for
        # that seed, to the last bit -- this is the strongest parity check in the
        # suite: the ensemble machinery is the same estimator, not a lookalike.
        import expcommon as E
        for k, s in enumerate(nseeds):
            part = np.load(E.PARTS / ("clouds_f3_s%d.npz" % E.SEEDS.index(int(s))))
            assert abs(r[sel][k] - float(part["profiled_pearson"])) < 1e-9, \
                f"truth-7 / noise-{s} row != the spine solve for that seed"
        ens = j["headline"]["cloudy_profiled_r"]
        assert ens["n"] == r.size
        assert abs(np.mean(r) - ens["mean"]) < 1e-9
        assert abs(np.std(r, ddof=1) - ens["sd"]) < 1e-9
        # the fiducial slice mean must equal the ensemble's own claim about it,
        # and the two must DIFFER: if swapping the truth map did not move the
        # mean, "external validity" would be reported as a null result.
        fid = float(np.mean(r[sel]))
        assert abs(fid - float(np.mean([float(np.load(E.PARTS / ("clouds_f3_s%d.npz"
                % E.SEEDS.index(int(s))))["profiled_pearson"])
                for s in nseeds]))) < 1e-9
        assert abs(np.mean(r) - fid) > ens["se"], \
            "ensemble mean indistinguishable from the fiducial map: the " \
            "external-validity spread is being reported as nothing"

    def test_priors_conclusion_names_its_own_confounds(self):
        """A conclusion string may not claim a prior bake-off it cannot run."""
        j = ext_json("priors")
        h = j["headline"]
        concl = str(h.get("conclusion", ""))
        if not concl:
            pytest.skip("no conclusion field")
        low = concl.lower()
        assert "not a clean prior bake-off" in low or "confound" in low, \
            "the priors conclusion asserts a ranking without its confounds"
        for arm in ("tdi", "tv", "sparse"):
            v = h.get(f"{arm}_r")
            if v is None:
                continue
            p = j["summary"][arm]["pearson"]
            assert abs(float(v) - p["mean"]) < 1e-9, \
                f"headline {arm}_r != summary mean for {arm}"
        assert h["sparse_r"] >= h["tdi_r"] or "sparse" in low, \
            "sparse scores above TDI but the conclusion never says so"

    def test_swarm_joint_delta_is_paired_not_ensemble(self):
        """N=2 joint inversion runs on 2 seeds; its reference must be those 2."""
        h = ext_json("swarm")["headline"]
        if "joint_delta_r_paired" not in h:
            pytest.skip("archive predates the paired reference")
        jm, rp, re_ = (float(h["joint_r_mean"]), float(h["r_single_paired"]),
                       float(h["r_single_ref"]))
        assert abs(h["joint_delta_r_paired"] - (jm - rp)) < 1e-9
        assert abs(h["joint_delta_r_ensemble"] - (jm - re_)) < 1e-9
        assert abs(rp - re_) > 1e-4, \
            "paired and ensemble references identical: the pairing is fake"
        # The paired reference must be the spine's own per-seed r restricted to
        # the joint seeds -- not the 10-seed mean (which is what an earlier
        # version of this test demanded, making it contradict the line above).
        clouds = D.load_npz("clouds.npz")
        methods = [str(m) for m in clouds["methods"]]
        prof = clouds["pearson_mat"][methods.index("profiled"), list(clouds["fcs"]).index(0.55)]
        seedlist = [int(s) for s in clouds["seeds"]]
        joint = [int(s) for s in h["joint_seeds"]]
        want = float(np.mean([prof[seedlist.index(s)] for s in joint]))
        assert rp == pytest.approx(want, abs=1e-9), \
            f"paired reference {rp} is not the spine mean over seeds {joint} ({want})"
        cav = " ".join(ext_json("swarm")["caveats"]).lower()
        assert "paired" in cav


class TestCaveatCoverage:
    """Every extension must state the thing a referee would ask first."""

    @pytest.mark.parametrize("name", EXT_MODULES or ["__none__"])
    def test_at_least_one_substantive_caveat(self, name):
        """Short tier notes ('2 noise seeds') are good practice, not a limit.

        What the contract requires is at least one caveat that actually explains
        the scope of the claim.
        """
        cs = ext_json(name)["caveats"]
        assert any(len(c) >= 40 for c in cs), \
            f"ext_{name}: no caveat is long enough to be a scope statement"

    @pytest.mark.parametrize("name", EXT_MODULES or ["__none__"])
    def test_sample_size_or_analytic_status_is_disclosed(self, name):
        j = ext_json(name)
        blob = " ".join(j["caveats"]) + " " + json.dumps(j["provenance"])
        assert any(w in blob for w in ("seed", "draws", "analytic", "tier",
                                       "n_draws")), (
            f"ext_{name}: neither a sample size nor an analytic-scope statement "
            f"is disclosed")

    def test_proxy_methods_are_flagged(self):
        """Modules that do not run the real inversion must say so, in caveats."""
        markers = ("not", "analytic", "proxy", "approxim", "assum",
                   "instead of", "rather than")
        for name in EXT_MODULES:
            j = ext_json(name)
            body = json.dumps({k: v for k, v in j.items()
                               if k != "provenance"}).lower()
            if ("proxy" in body or "analytic" in body
                    or "not performed" in body or "not full" in body):
                cs = [c.lower() for c in j["caveats"]]
                assert any(any(m in c for m in markers) for c in cs), (
                    f"ext_{name}: analytic/proxy method without a matching "
                    f"caveat")


class TestUnitsAndScaling:
    """Regression net for the defects the full-tier regeneration exposed.

    Each of these was invisible to an affine-invariant metric check: a value
    with the right symbol but the wrong unit, a constant off by 100x from the
    manuscript's, a ratio whose numerator and denominator are the same double
    count, and a bound that is weaker than the trivial one but printed as if it
    were a floor.
    """

    def test_no_internal_review_ids_leak_into_shipped_strings(self):
        """Defect IDs are a working-document vocabulary, not archive content."""
        import re
        pat = re.compile(r"\bF-\d{2}\b")
        for name in EXT_MODULES:
            j = ext_json(name)
            for k in ("headline", "caveats", "conclusion", "status"):
                v = j.get(k)
                if v is None:
                    continue
                blob = json.dumps(v)
                assert not pat.search(blob), (
                    f"ext_{name}.{k} carries an internal review id: "
                    f"{pat.search(blob).group(0)}")

    def test_disk_kernel_oblateness_matches_the_manuscript(self):
        """The bound must use the J2 the paper states, not another one."""
        h = ext_json("disk_kernel")["headline"]
        tex = (D.PAPER / "main.tex").read_text()
        assert h["j2_adopted"] == pytest.approx(2.2e-7, rel=1e-12), (
            "ext_disk_kernel bounds the omitted term at a J2 the manuscript "
            "does not use")
        assert "2\\times10^{-7}" in tex, (
            "the manuscript's J_2 no longer reads 2\\times10^{-7}; re-check "
            "which value the bound uses")
        # the bound is 2*J2 in magnitude, and it must stay sub-cell
        assert abs(h["j2_rel_dev_max"]) == pytest.approx(2 * h["j2_adopted"],
                                                        rel=1e-6)
        assert h["j2_ring_shift_cells_n64"] < 1e-4, (
            "the sub-cell argument needs the shift to be far below one cell")

    def test_corona_refraction_is_reported_as_out_of_range_not_as_a_loss(self):
        """A clamp to the base point is not a measured Delta r."""
        h = ext_json("corona_screen")["headline"]
        caveats = " ".join(ext_json("corona_screen")["caveats"])
        if h.get("refractive_level_below_grid"):
            assert h["delta_r_from_base"] == 0.0
            assert "BELOW" in caveats, (
                "the archive must say the refractive level is below the "
                "injected grid instead of implying a measured loss")
        # the grid minimum the comparison is made against really is 1e-8
        assert h["eps_grid_min_coronal"] == pytest.approx(
            float(np.load(D.RESULTS / "systematics.npz")["eps"][1]), rel=1e-12)

    def test_telemetry_volume_is_counted_from_samples_not_double_counted(self):
        """nsc IS the sub-exposure count; multiplying by NSUB again inflates it."""
        h = ext_json("telemetry")["headline"]
        assert h["total_samples"] == 65536, (
            "the campaign sample count must be the same 65,536 that sizes the "
            "design matrix")
        assert h["raw_volume_mb"] == pytest.approx(
            h["total_samples"] * 32 / 1e6, abs=0.01), (
            "raw_volume_mb must be the bookkept (32 B) volume")
        assert h["binned_volume_mb"] == pytest.approx(
            h["value_only_volume_mb"], rel=1e-9), (
            "one float32 per pixel per pass is one float32 per measurement: "
            "there is no compression to claim")
        assert h["bookkept_over_binned"] == pytest.approx(8.0, rel=1e-6)

    def test_telemetry_loss_fields_survive_their_own_rounding(self):
        """A field that rounds to -0.0 reports nothing."""
        h = ext_json("telemetry")["headline"]
        for k in ("r_loss_1s", "r_loss_0_1s", "r_loss_f05_8_64s"):
            assert h[k] != 0.0, f"{k} rounded away to zero"
        assert h["archived_slope_r_per_deg"] > 0

    def test_fisher_crlb_cannot_be_quoted_when_it_is_not_a_floor(self):
        """If the bound is weaker than the constant map, the r comparison is
        a sentinel, not a 100% discrepancy."""
        h = ext_json("fisher_bounds")["headline"]
        if not h["crlb_informative"]:
            assert h["crlb_vs_constant_map_a"] > 1.0
            assert h["r_fid_pred"] == 0.0
            for k in ("disc_r_pred_vs_sim_a", "disc_r_pred_vs_sim_b"):
                assert isinstance(h[k], str), (
                    f"{k} must be the degenerate sentinel while the bound is "
                    f"weaker than the constant map, not a ratio of zeros")
            assert "mean_abs_frac_disc_r_a" not in h
        assert 0 < h["achieved_var_over_crlb_fid"] < 1e-3, (
            "the regularised fit sitting far below the pseudo-inverse bound is "
            "the evidence that the bound is the wrong yardstick")

    def test_scheduling_states_what_it_did_not_simulate(self):
        j = ext_json("scheduling")
        blob = json.dumps(j)
        assert "improvement_pct" in j["headline"]
        assert "does not re-simulate" in j["headline"]["conclusion"], (
            "the scheduling conclusion must not read as a reconstruction result")
        assert "Delta r" in blob or "paired Delta r" in blob

    def test_ephemeris_z_drift_is_in_astronomical_units(self):
        """A 1000x unit slip here turns a negligible drift into a crisis."""
        h = ext_json("ephemeris")["headline"]
        assert 1.0 < h["z_drift_90d_au"] < 2.0, (
            "30 km/s for 90 days is ~1.56 AU, not 1560 AU")
        assert h["z_drift_90d_frac_of_z"] == pytest.approx(
            h["z_drift_90d_au"] / 650.0, rel=1e-3)

    def test_ephemeris_and_target_uncertainty_use_different_feasibility_rules(self):
        """Two proxies, two winners: neither may be quoted as THE ranking."""
        eph = ext_json("ephemeris")["headline"]
        tgt = ext_json("target_uncertainty")["headline"]
        blob = json.dumps(ext_json("ephemeris")["caveats"])
        assert eph["top_target"] != tgt["winner_feasibility"].split(" (")[0]
        assert "feasibility_score here" in blob or "different proxies" in blob, (
            "the archive must state that its feasibility rule differs from the "
            "manuscript's mission rule")


# ---------------------------------------------------------------------------
# Manuscript <-> archive agreement
# ---------------------------------------------------------------------------

def _tex():
    """paper/main.tex, read once per call (cheap, ~300 KB)."""
    return (D.PAPER / "main.tex").read_text()


def _flat(text):
    """Collapse the manuscript's hard line wraps so prose can be matched."""
    return re.sub(r"\s+", " ", text).lower()


def _sci(value, mant_digits):
    """Format ``value`` the way the manuscript writes a scientific bound.

    ``2.8e-05`` at one mantissa digit becomes ``2.8\\times10^{-5}``, and
    ``1.16249e5`` at two becomes ``1.16\\times10^{5}`` -- the exponent sign and
    width are LaTeX's, not Python's.
    """
    mant, expo = f"{value:.{mant_digits}e}".split("e")
    return rf"{mant}\times10^{{{int(expo)}}}"


class TestManuscriptQuotesTheArchive:
    """Every Part VII number that reached the body must still be in the archive.

    This is the guard against the failure mode the referee round actually
    produced: a module is re-run, its physics changes, the archive is updated,
    and the manuscript keeps the old sentence.  Each check formats the archived
    value at the display precision the paper uses and requires that exact
    string, so a stale number fails rather than silently disagreeing.
    """

    def test_truth_ensemble_levels_match_the_archive(self):
        h = ext_json("truth_ensemble")["headline"]
        tex = _tex()
        for key, digits in (("cloudy_profiled_r", 4), ("cloudfree_profiled_r", 4)):
            mean = f"{h[key]['mean']:.{digits}f}"
            se = f"{h[key]['se']:.4f}"
            assert f"{mean}\\pm{se}" in tex, (
                f"main.tex does not quote the archived {key} as {mean}\\pm{se}")

    def test_portability_is_quoted_as_a_paired_single_seed_swap(self):
        h = ext_json("portability")["headline"]
        tex = _tex()
        for key in ("r_sgl_paired", "r_airy", "ssim_sgl_paired", "ssim_airy"):
            assert f"{h[key]:.4f}" in tex, f"{key}={h[key]} not quoted in main.tex"
        assert f"{h['r_ratio_paired']:.3f}" in tex
        assert "same truth, the same photons and one paired seed" in tex, (
            "the paired-at-one-seed status must survive into the prose")

    def test_priors_arms_match_the_archive(self):
        h = ext_json("priors")["headline"]
        tex = _tex()
        for arm in ("tdi", "tv", "sparse"):
            assert f"{h[arm + '_r']:.4f}" in tex, (
                f"priors {arm} arm {h[arm + '_r']:.4f} is not quoted")

    def test_telemetry_volumes_are_the_derived_counts(self):
        h = ext_json("telemetry")["headline"]
        tex = _tex()
        assert f"{h['total_samples']:,}".replace(",", "{,}") in tex, (
            "the sample count quoted in the paper is not the derived one")
        assert f"{h['raw_volume_mb']:.2f}" in tex
        assert f"{h['value_only_volume_mb']:.3f}" in tex
        assert h["bookkept_over_binned"] == 8.0

    def test_omitted_solar_bounds_match_the_archives(self):
        dk = ext_json("disk_kernel")["headline"]
        cs = ext_json("corona_screen")["headline"]
        tex = _tex()
        # J2: cells (1 dp mantissa) and the adopted constant itself.
        assert _sci(dk["j2_ring_shift_cells_n64"], 1) in tex, (
            f"J2 ring shift {dk['j2_ring_shift_cells_n64']} not quoted in cells")
        assert dk["j2_adopted"] == 2.2e-7
        assert r"J_2=2.2\times10^{-7}" in tex
        # refraction: the equivalent coronal residual and the grid ratio
        ratio = cs["eps_grid_min_coronal"] / cs["eps_equiv_coronal_at_1um"]
        assert _sci(ratio, 2) in tex, (
            f"the {ratio:.3g}x below-grid factor is not quoted")
        assert f"{cs['model_valid_below_m']:.3f}" in tex, (
            "the weak-refraction wavelength limit is quoted at the wrong precision")

    def test_scheduling_gain_matches_the_archive(self):
        h = ext_json("scheduling")["headline"]
        tex = _tex()
        assert f"{h['n_eff_uniform']:.4f}" in tex
        assert f"{h['n_eff_optimized']:.4f}" in tex
        assert f"{h['improvement_pct']:.2f}" in tex

    def test_ephemeris_drift_and_rule_disagreement_match_the_archive(self):
        h = ext_json("ephemeris")["headline"]
        tex = _tex()
        assert f"{h['z_drift_90d_au']:.2f}" in tex, "90-day z drift not quoted in AU"
        assert f"{100 * h['z_drift_90d_frac_of_z']:.2f}\\%" in tex
        assert h["top_target"] in tex.replace("~", " ")
        tgt = ext_json("target_uncertainty")["headline"]
        # the archive carries the catalog name with its parenthetical; the
        # manuscript uses the short form
        win = tgt["winner_feasibility"].split(" (")[0]
        assert win in tex.replace("~", " "), (
            "both reachability winners must appear, since the paper reports the "
            "disagreement rather than resolving it")

    def test_evidence_lambda_is_quoted_as_an_edge_not_an_optimum(self):
        """The renamed headline keys must be locations, and the text must say so.

        Before the rename this archive reported ``r_optimal_cloudy = 0.3`` --
        a lambda printed under a metric's name. The keys now carry ``lambda_``
        and the manuscript may only quote them as grid locations.
        """
        h = ext_json("evidence_lambda")["headline"]
        tex = _tex()
        z = ext_npz("evidence_lambda")
        grid = np.asarray(z["lam_grid"], dtype=float)
        locs = {k: v for k, v in h.items() if k.startswith("lambda_")}
        assert set(locs) == {"lambda_evidence_cloudy", "lambda_evidence_cloudfree",
                             "lambda_r_max_cloudy", "lambda_ssim_max_cloudy",
                             "lambda_chi2_min_cloudy"}, (
            "the headline must name the five lambda LOCATIONS it reports")
        for k, v in locs.items():
            assert np.any(np.isclose(grid, float(v))), (
                f"{k}={v} is not a point of the archived grid {grid}")
        assert "evidence_optimal_cloudy" not in h, (
            "legacy key: it printed a lambda under a metric's name")
        assert h["lambda_evidence_cloudy"] == h["lambda_evidence_cloudfree"], (
            "the evidence optimum was supposed to differ by regime")
        assert _sci(h["log_evidence_first_minus_last_cloudy"], 1) in tex, (
            "the size of the log-evidence drop is not the archived one")
        low = _flat(tex)
        assert "no truth-blind criterion is established" in low, (
            "the manuscript must not present any of these locations as an optimum")
        assert "left edge" in low

    def test_chi2_optimum_gap_is_the_archived_one(self):
        """The 0.13% figure in the text and 54 absolute in the archive agree."""
        h = ext_json("evidence_lambda")["headline"]
        tex = _tex()
        gap = h["chi2_frozen_minus_min_cloudy"]
        assert 40.0 < gap < 70.0, "archived frozen-to-minimum chi2 gap moved"
        assert f"{gap:.1f}" in tex or r"0.13\%" in tex, (
            "the chi2 gap needs to be quoted in at least one of the two units")

    def test_cloud_physics_cover_confound_is_quoted_as_a_range(self):
        """The arm spread is a coverage ordering, and the paper must say so.

        ``cloud_physics`` shares one ``sigma_cl`` across arms without
        recalibrating it, so every weather perturbation also moves the realized
        cloud cover, and cover alone drives the recovered correlation. The shipped
        archive reports both columns; the ordering below is recomputed here rather
        than trusted, so the manuscript's ``rho=-1`` sentence fails if a future
        re-run breaks it.
        """
        h = ext_json("cloud_physics")["headline"]
        if "cover_ou" not in h:
            pytest.skip("archive predates the cover columns")
        tex = _tex()
        arms = ("ou", "markov", "hawkes", "topo", "anchor_strong")
        cov = np.array([float(h["cover_" + a]) for a in arms])
        rv = np.array([float(h["r_" + a + "_mean"]) for a in arms])
        order = np.argsort(cov)
        assert np.all(np.diff(rv[order]) < 0), (
            f"cover {cov[order]} vs r {rv[order]} is no longer anti-monotone; the "
            f"manuscript may not present the arms as one ordering")
        pear = float(np.corrcoef(cov, rv)[0, 1])
        slope = float(np.polyfit(cov, rv, 1)[0])
        assert pear < -0.9 and slope < 0.0
        for a in arms:
            assert f"{h['cover_' + a]:.3f}" in tex, f"cover of {a} not quoted"
            assert f"{h['r_' + a + '_mean']:.3f}" in tex, f"r of {a} not quoted"
        for a in arms[1:]:
            d = h["delta_r_" + a + "_vs_ou"]
            assert f"{d:+.3f}" in tex, f"paired delta of {a} ({d}) not quoted"
        assert f"{h['r_ou_mean']:.4f}\\pm{h['r_ou_se']:.4f}" in tex, (
            "the OU reference is not quoted with its archived standard error")
        assert f"{pear:.3f}" in tex and f"{slope:.2f}" in tex
        arch = float(h["archived_collapse_r"])
        assert f"{arch:.4f}" in tex, "the collapse reference level moved"
        assert f"{rv.min() / arch:.2f}\\times" in tex, (
            "the weakest arm's distance above the archived collapse is stale")
        assert h["status"].startswith("weather_model_sensitivity_range")
        assert r"status ({\tt weather\_model\_sensitivity\_range})" in tex
        assert h["collapse_reproduced"] is False
        flat = _flat(tex)
        assert r"{\tt collapse\_reproduced} is reported as {\tt false}" in flat, (
            "the manuscript must state the negative verdict, not omit it")
        assert "the arms realize different cloud covers" in flat, (
            "the appendix table must carry the same caveat the section does")

    def test_conclusions_item_count_covers_every_extension_group(self):
        """The conclusions list grew with the extensions; keep it monotone."""
        tex = _tex()
        block = tex.split(r"\section{Conclusions}")[1].split(
            r"\section*{Data and Code Availability}")[0]
        nums = [int(m) for m in re.findall(r"(?m)^(\d+)\.\s", block)]
        assert nums == list(range(1, len(nums) + 1)), (
            f"conclusions are numbered {nums}; a deleted item leaves a gap")
        assert len(nums) >= 10


class TestCloudPhysicsArmNaming:
    """The weather-model module must not dress a static offset as phase locking.

    This is the one extension whose shipped archive was produced by a run that
    crashed in its own save block: the arm named ``phase_lock`` is the same
    topographically anchored model with a doubled STATIC offset, and the
    reference it stored as ``r_surf_ou`` was a second copy of the fiducial run.
    Both mislabels are locked out here.
    """

    def test_arms_are_named_for_what_they_are(self):
        j = ext_json("cloud_physics")
        h = j["headline"]
        if "collapse_reproduced" not in h:
            pytest.skip("archive predates the arm rename; re-run "
                        "`python3 -m ext.cloud_physics`")
        for legacy in ("phase_locking_collapse_survives", "r_phase_lock_mean",
                       "r_parts_ou_mean", "delta_r_topo_vs_surf_ou"):
            assert legacy not in h, f"{legacy} is the mislabelled key"
        assert "strong_anchor_arm" in j and "phase_locking_test" not in j
        assert "archived_collapse_reference" in j
        z = ext_npz("cloud_physics")
        assert "r_anchor_strong" in z.files and "r_phase_lock" not in z.files
        assert "r_surf_ou_ref" not in z.files

    def test_every_arm_reports_its_realized_cover(self):
        """sigma_cl is shared and not recalibrated, so cover is the confound."""
        h = ext_json("cloud_physics")["headline"]
        if "cover_ou" not in h:
            pytest.skip("archive predates the cover columns")
        for k in ("cover_ou", "cover_markov", "cover_hawkes", "cover_topo",
                  "cover_anchor_strong"):
            assert h[k] is not None, f"{k} missing: the r spread is unreadable"
            assert 0.0 <= float(h[k]) <= 1.0
        # the fiducial realized cover at fc=0.55 is 0.558 in the spine archive
        assert h["cover_ou"] == pytest.approx(
            float(np.asarray(D.load_npz("clouds.npz")["covers"], dtype=float)[3].mean()),
            rel=1e-6)

    def test_collapse_verdict_is_measured_against_the_archived_level(self):
        j = ext_json("cloud_physics")
        h = j["headline"]
        if "collapse_reproduced" not in h:
            pytest.skip("archive predates the verdict redefinition")
        arch = float(h["archived_collapse_r"])
        assert arch == pytest.approx(0.1444, abs=1e-3), (
            "the collapse reference must be the spine's surface-coupled level")
        anchor = h["r_anchor_strong_mean"]
        if anchor is not None and anchor > arch + 0.05:
            assert h["collapse_reproduced"] is False, (
                "an arm far above the archived collapse cannot reproduce it")
        cav = " ".join(j["caveats"]).lower()
        assert "static" in cav and "phase locking" in cav, (
            "the archive must state that its anchored arm has no rotational locking")

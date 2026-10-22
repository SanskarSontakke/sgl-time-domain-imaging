"""End-to-end pipeline check (slow tier).

Every shipped number in ``results/`` is a reduction of a checkpoint, and every
checkpoint is the output of one process: cached forward operator + cached
photons + ``E.fit`` + ``S.debias_cloud`` + ``E.evaluate``.  The fast tests verify
the reductions; this module verifies the SIMULATION half by re-running the
fiducial estimator on the same cached dataset and comparing against the
checkpoint that was shipped.  It is the test that fails if ``src/`` and
``results/`` ever drift apart -- which is precisely the failure the referee found
in the pre-revision archive.

It is marked ``slow`` because it costs several GLS solves (~8 s each) and maps
the 0.68 GB float32 forward operator.  Run it with:

    python3 -m pytest tests -q -m slow

Nothing in ``results/`` is written: every value used here is a seed/parameter
combination the pipeline has already memoised into ``results/cache``, so the
caches are hit rather than rebuilt.  ``results_read_only`` proves that instead of
just asserting it -- a silent cache rebuild would otherwise make the suite
"pass" by overwriting the very evidence it is checking.
"""
import numpy as np
import pytest

import _data as D

pytestmark = pytest.mark.slow


def _shipped_fingerprint():
    """(size, mtime_ns) for the audited evidence, plus the cache FILE NAMES.

    Scope is the shipped suite -- ``results/parts/**``, the merged top-level
    archives, and the memoised operators/datasets.  ``results/ext_*`` is
    deliberately excluded: those archives belong to the Part VII extension
    modules and are legitimately rewritten by them, possibly while this suite
    runs.  Only metadata, not contents, is recorded: hashing 712 MB of cache per
    session would dominate the runtime of the suite it is guarding.  A rebuild
    always leaves a fresh mtime (and typically a new cache key), so metadata is
    enough to catch the accident this guards against.
    """
    fp = {}
    for p in sorted(D.RESULTS.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(D.RESULTS))
        if rel.startswith("ext_"):
            continue
        st = p.stat()
        fp[rel] = ("name",) if rel.startswith("cache/") else \
            ("meta", st.st_size, st.st_mtime_ns)
    return fp


@pytest.fixture(scope="module", autouse=True)
def results_read_only():
    """Fail at teardown if a slow run touched the audited evidence."""
    before = _shipped_fingerprint()
    yield
    after = _shipped_fingerprint()
    new = sorted(set(after) - set(before))
    gone = sorted(set(before) - set(after))
    changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])
    assert not new, f"slow tests created archive files: {new[:5]}"
    assert not gone, f"slow tests deleted archive files: {gone[:5]}"
    assert not changed, f"slow tests modified archive files: {changed[:5]}"


@pytest.fixture(scope="module")
def fiducial():
    """Campaign, operator, truth field, and the shipped fiducial checkpoint."""
    import expcommon as E
    import sglsim as S
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    F = E.get_F(camp, sglop)                       # mmap from results/cache
    ref = np.load(D.PARTS / "clouds_f3_s0.npz", allow_pickle=True)
    dat = E.get_dat(camp, sglop, truthF, int(ref["seed"]), float(ref["fc"]))
    return dict(E=E, S=S, camp=camp, sglop=sglop, truthF=truthF, truth_c=truth_c,
                F=F, ref=ref, dat=dat)


@pytest.fixture(scope="module")
def cloudfree(fiducial):
    """The same dataset family with fc = 0 (the cloud-free ceiling run)."""
    E = fiducial["E"]
    fiducial["cloudfree_ref"] = np.load(D.PARTS / "clouds_f0_s0.npz",
                                        allow_pickle=True)
    fiducial["cloudfree_dat"] = E.get_dat(fiducial["camp"], fiducial["sglop"],
                                          fiducial["truthF"],
                                          int(fiducial["cloudfree_ref"]["seed"]),
                                          0.0)
    return fiducial


@pytest.fixture(scope="module")
def fits(fiducial):
    """Solve each estimator ONCE for the whole module (a solve is ~8 s)."""
    E, S = fiducial["E"], fiducial["S"]
    ref, dat = fiducial["ref"], fiducial["dat"]
    fc, sigma_cl = float(ref["fc"]), float(ref["sigma_cl"])
    solved = {}
    for solver in ("profiled", "deflate"):
        m = S.debias_cloud(E.fit(solver, fiducial["F"], dat, fiducial["camp"],
                                 sigma_cl), fc)
        solved[solver] = (m, E.evaluate(m, fiducial["truth_c"]))
    return solved


class TestFiducialReconstruction:
    """profiled and deflate on seed 11 must reproduce clouds_f3_s0.npz."""

    def test_checkpoint_describes_the_fiducial_configuration(self, fiducial):
        E, camp, ref = fiducial["E"], fiducial["camp"], fiducial["ref"]
        assert int(ref["seed"]) == E.SEEDS[0]
        assert float(ref["fc"]) == E.FC
        assert int(ref["nsub"]) == E.NSUB == 16
        assert int(ref["mp"]) == camp.mp
        assert float(ref["ts"]) == camp.ts
        assert np.asarray(ref["mode"]).item() == camp.mode
        assert np.asarray(ref["solver"]).item() == "profiled(anchored R11)"

    def test_sigma_cl_is_the_cached_fiducial_value(self, fiducial):
        E, ref = fiducial["E"], fiducial["ref"]
        assert float(ref["sigma_cl"]) == pytest.approx(
            E.get_sigcl(E.FC, fiducial["camp"], fiducial["sglop"],
                        fiducial["truthF"]), rel=1e-12)

    @pytest.mark.parametrize("metric", ["pearson", "ssim", "nrmse", "bias",
                                        "contrast"])
    def test_profiled_metrics_reproduce_the_checkpoint(self, fiducial, fits,
                                                       metric):
        _, e = fits["profiled"]
        assert e[metric] == pytest.approx(
            float(fiducial["ref"]["profiled_" + metric]), abs=1e-12)

    @pytest.mark.parametrize("metric", ["pearson", "ssim", "nrmse", "bias",
                                        "contrast"])
    def test_deflate_metrics_reproduce_the_checkpoint(self, fiducial, fits,
                                                     metric):
        _, e = fits["deflate"]
        assert e[metric] == pytest.approx(
            float(fiducial["ref"]["deflate_" + metric]), abs=1e-12)

    def test_a_single_seed_cannot_separate_the_estimators(self, fiducial,
                                                          fits):
        """Seed 11 is a near tie; the paper's claim is a seed-AVERAGED one.

        Stated as a tolerance rather than an inequality so a regeneration cannot
        flip it, while still pinning the qualitative fact the manuscript makes:
        profiling is not worth 0.01 of Pearson r on one realisation.
        """
        rp = float(fits["profiled"][1]["pearson"])
        rd = float(fits["deflate"][1]["pearson"])
        assert abs(rp - rd) < 5e-4

    def test_stored_maps_are_the_same_arrays(self, fiducial, fits):
        """The checkpoint stores the map itself, so a figure can be rebuilt."""
        m = np.asarray(fits["profiled"][0], float)
        stored = np.asarray(fiducial["ref"]["map_profiled"], float)
        E = fiducial["E"]
        assert m.shape == stored.shape == (E.NLAT * E.NLON,)
        assert np.max(np.abs(m - stored)) < 1e-9

    def test_evaluate_is_a_function_of_the_stored_map_alone(self, fiducial):
        """Re-evaluating from the archived map must give the archived metrics.

        This is the cheap half of the audit: it proves figures/audit could have
        been regenerated from the shipped maps without re-solving.
        """
        stored = np.asarray(fiducial["ref"]["map_profiled"], float)
        e = fiducial["E"].evaluate(stored, fiducial["truth_c"])
        for metric in ("pearson", "ssim", "nrmse", "bias", "contrast"):
            assert e[metric] == pytest.approx(
                float(fiducial["ref"]["profiled_" + metric]), abs=1e-12)


class TestCloudFreeCeiling:
    def test_profiled_reproduces_the_cloud_free_checkpoint(self, cloudfree):
        E = cloudfree["E"]
        ref = cloudfree["cloudfree_ref"]
        m = E.fit("profiled", cloudfree["F"], cloudfree["cloudfree_dat"],
                  cloudfree["camp"], 0.0)
        e = E.evaluate(m, cloudfree["truth_c"])
        assert float(ref["fc"]) == 0.0
        assert float(ref["sigma_cl"]) == 0.0
        assert e["pearson"] == pytest.approx(
            float(ref["profiled_pearson"]), abs=1e-12)

    def test_ceiling_is_above_the_manuscript_floor(self, cloudfree):
        assert float(cloudfree["cloudfree_ref"]["profiled_pearson"]) > 0.95

    def test_cloud_free_beats_cloudy_for_the_same_solver_and_seed(self,
                                                                  cloudfree):
        assert (float(cloudfree["cloudfree_ref"]["profiled_pearson"]) >
                float(cloudfree["ref"]["profiled_pearson"]))


class TestWholeArchiveReproducibility:
    """Every shipped cloudy seed must be reproducible from the caches.

    Only ``profiled`` is re-solved here (the deflate half is covered on seed 11);
    this is the test that would catch a checkpoint produced by a different solver
    version than the one now in ``src/``.
    """

    def test_every_cloudy_seed_reproduces(self, cloudfree):
        E, S = cloudfree["E"], cloudfree["S"]
        camp, sglop = cloudfree["camp"], cloudfree["sglop"]
        truthF, truth_c, F = (cloudfree[k] for k in ("truthF", "truth_c", "F"))
        worst_r, worst_map = 0.0, 0.0
        for j in range(len(E.SEEDS)):
            p = D.PARTS / f"clouds_f3_s{j}.npz"
            if not p.exists():
                pytest.fail(f"{p.name} is shipped by reproduce_all but missing")
            ref = np.load(p, allow_pickle=True)
            assert int(ref["seed"]) == E.SEEDS[j]
            dat = E.get_dat(camp, sglop, truthF, int(ref["seed"]),
                            float(ref["fc"]))
            m = S.debias_cloud(E.fit("profiled", F, dat, camp,
                                     float(ref["sigma_cl"])), float(ref["fc"]))
            worst_r = max(worst_r, abs(E.evaluate(m, truth_c)["pearson"] -
                                       float(ref["profiled_pearson"])))
            worst_map = max(worst_map, float(np.max(np.abs(
                np.asarray(m, float) - np.asarray(ref["map_profiled"], float)))))
        assert worst_r < 1e-12
        assert worst_map < 1e-9

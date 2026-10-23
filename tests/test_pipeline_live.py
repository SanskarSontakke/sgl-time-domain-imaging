"""End-to-end pipeline check (slow tier).

Every shipped number in ``results/`` is a reduction of a checkpoint, and every
checkpoint is the output of one process: cached forward operator + cached
photons + ``E.fit`` + ``S.debias_cloud`` + ``E.evaluate``.  The fast tests verify
the reductions; this module verifies the SIMULATION half by re-running the
fiducial estimator on the same cached dataset and comparing against the
checkpoint that was shipped.  It is the test that fails if ``src/`` and
``results/`` ever drift apart -- which is precisely the failure found in the
pre-revision archive.

It is marked ``slow`` because it costs several GLS solves (~8 s each) and maps
the 0.68 GB float32 forward operator.  Run it with:

    python3 -m pytest tests -q -m slow

On a warm tree nothing in ``results/`` is written: every value used here is a
seed/parameter combination the pipeline has already memoised into
``results/cache``, so the caches are hit rather than rebuilt.  A cold clone has
no such cache (it is 731 MB and gitignored), so it must rebuild one, and
``results_read_only`` separates those two events instead of forbidding both.
New keys under ``results/cache/`` are derived data that
``tools/array_manifest.py`` deliberately skips; any other write is the silent
rebuild that would otherwise make the suite "pass" by overwriting the very
evidence it is checking.
"""
import warnings

import numpy as np
import pytest

import _data as D

pytestmark = pytest.mark.slow

#: the one directory under ``results/`` that is scratch rather than evidence
CACHE = "cache/"

#: the memoisation families ``src/expcommon`` keys into ``results/cache``
MEMO_PREFIXES = ("dat_", "F_", "LtL_", "sigma_")


def _shipped_fingerprint():
    """(size, mtime_ns) for the audited evidence, plus the cache FILE NAMES.

    Scope is the shipped suite -- ``results/parts/**``, the merged top-level
    archives, and the memoised operators/datasets.  ``results/ext_*`` is
    deliberately excluded: those archives belong to the extension
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


def _evidence_delta(before, after):
    """Classify a fingerprint diff into the five things that can have happened.

    ``created``, ``deleted`` and ``modified`` are violations of the shipped
    evidence.  ``rebuilt`` is a cold tree earning its memoisation, and ``stray``
    is a file under ``results/cache/`` that belongs to no memoisation family --
    a cache key this suite has never seen is how a parameter change in ``src/``
    hides inside a passing run, so it is reported even though it is not evidence.
    """
    new = sorted(set(after) - set(before))
    in_cache = [k for k in new if k.startswith(CACHE)]
    return {
        "created": [k for k in new if not k.startswith(CACHE)],
        "rebuilt": in_cache,
        "deleted": sorted(set(before) - set(after)),
        "modified": sorted(k for k in set(before) & set(after)
                           if before[k] != after[k]),
        "stray": [k for k in in_cache
                  if not k[len(CACHE):].startswith(MEMO_PREFIXES)],
    }


@pytest.fixture(scope="module", autouse=True)
def results_read_only():
    """Fail at teardown if a slow run touched the audited evidence."""
    before = _shipped_fingerprint()
    yield
    delta = _evidence_delta(before, _shipped_fingerprint())
    assert not delta["created"], \
        f"slow tests created archive files: {delta['created'][:5]}"
    assert not delta["deleted"], \
        f"slow tests deleted archive files: {delta['deleted'][:5]}"
    assert not delta["modified"], \
        f"slow tests modified archive files: {delta['modified'][:5]}"
    assert not delta["stray"], \
        f"unexpected file under results/cache: {delta['stray'][:5]}"
    if delta["rebuilt"]:
        warnings.warn(
            f"cold tree: this run built {len(delta['rebuilt'])} memoisation "
            f"caches (oldest key {delta['rebuilt'][0]!r}); the shipped "
            "evidence is untouched, but the run paid for the rebuild",
            stacklevel=1)


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
        assert np.asarray(ref["solver"]).item() == "profiled(anchored_slot)"

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

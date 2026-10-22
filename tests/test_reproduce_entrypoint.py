"""Tests for the top-level reproduction entry point (``reproduce_all.py``).

Defect F-10 in the revision record was that the manuscript printed a reproduction
command that did not exist.  ``reproduce_all.py`` is the fix, so it needs the
same treatment as the science: the stage inventory must cover every subcommand,
the diff engine must be able to SEE a difference (including the ones numpy hides,
like an all-NaN slice or a truncated ``<U`` label), and -- the property that makes
this tool safe to advertise -- a verification run must not be able to write into
the shipped ``results/`` tree.
"""
import json
import os
import shutil
import subprocess
import sys

import numpy as np
import pytest

import _data as D
import reproduce_all as RA


def _write_npz(path, **kw):
    np.savez(path, **kw)
    return path


# ------------------------------------------------------------- inventories --
class TestStageInventory:
    def test_full_inventory_shape(self):
        st = RA.full_stages()
        assert st[0][0] == "setup"
        assert st[-1] == ("merge", [])
        assert len(st) == 70, "stage count changed: the manuscript quotes it"

    def test_no_duplicate_invocations(self):
        st = {(n, tuple(a)) for n, a in RA.full_stages()}
        assert len(st) == len(RA.full_stages())

    def test_every_stage_is_a_real_subcommand(self):
        """A typo here would silently skip a whole archive.

        Standalone generators (``STANDALONE``) are the exception: they are their
        own script rather than a ``run_experiments`` subcommand, and they exist
        precisely so that no artifact-producing script sits outside the driver.
        """
        import run_experiments as R
        names = {n for n, _ in RA.full_stages()} | {n for n, _ in RA.FAST_STAGES}
        pipeline = names - set(RA.STANDALONE)
        assert pipeline <= set(R.COMMANDS), sorted(pipeline - set(R.COMMANDS))
        # and the reverse: nothing the front end offers is left unrunnable
        assert set(R.COMMANDS) <= names, sorted(set(R.COMMANDS) - names)
        for name in RA.STANDALONE:
            assert (D.ROOT / "src" / f"{name}.py").exists(), f"src/{name}.py missing"

    def test_arguments_are_strings(self):
        for name, args in RA.full_stages():
            assert all(isinstance(a, str) for a in args), name

    def test_fast_tier_is_a_subset_of_full(self):
        # stage args are lists, so hash on a tuple projection
        full = {(n, tuple(a)) for n, a in RA.full_stages()}
        assert {(n, tuple(a)) for n, a in RA.FAST_STAGES} <= full
        assert ("merge", []) in RA.FAST_STAGES

    def test_fast_tier_covers_the_merge_of_everything(self):
        """`merge` is what turns checkpoints into the shipped archives, so a
        fast run that ended without it would compare nothing."""
        assert RA.FAST_STAGES[-1] == ("merge", [])

    def test_cloud_and_cadence_sweeps_are_complete(self):
        st = RA.full_stages()
        assert [a for n, a in st if n == "clouds"] == [[str(i)]
                                                       for i in range(5)]
        cad = [(a[0], a[1]) for n, a in st if n == "cadence"]
        assert len(cad) == 10 and {c[0] for c in cad} == {"photons", "wallclock"}
        ctrl = [(a[0], a[1], a[2]) for n, a in st if n == "cadence_control"]
        assert len(ctrl) == 20

    def test_extension_registry_matches_the_directory(self):
        on_disk = {p.stem for p in (D.ROOT / "src" / "ext").glob("*.py")}
        assert set(RA.EXT_MODULES) == on_disk - {"__init__", "extcommon"}


class TestParseStages:
    def test_groups_arguments_with_their_stage(self):
        got = RA.parse_stages("quadrature clouds 3 cadence photons 2")
        assert got == [("quadrature", []), ("clouds", ["3"]),
                       ("cadence", ["photons", "2"])]

    def test_merge_is_a_known_stage(self):
        assert RA.parse_stages("merge") == [("merge", [])]

    def test_repeated_stage_keeps_both_entries(self):
        assert RA.parse_stages("clouds 0 clouds 3") == [("clouds", ["0"]),
                                                        ("clouds", ["3"])]

    def test_unknown_token_is_a_hard_error(self):
        with pytest.raises(SystemExit) as e:
            RA.parse_stages("frobnicate 3")
        assert "frobnicate" in str(e.value)

    def test_leading_argument_without_a_stage_is_rejected(self):
        with pytest.raises(SystemExit):
            RA.parse_stages("3 clouds")


# ---------------------------------------------------------------- diff_json --
class TestDiffJson:
    def _cmp(self, tmp_path, a, b, tol=0.0):
        pa, pb = tmp_path / "a.json", tmp_path / "b.json"
        pa.write_text(json.dumps(a))
        pb.write_text(json.dumps(b))
        return RA.diff_json(pa, pb, tol)

    def test_identical_documents_have_no_diffs(self, tmp_path):
        bad, worst, n = self._cmp(tmp_path, {"x": [1, 2], "y": {"z": 3.5}},
                                 {"x": [1, 2], "y": {"z": 3.5}})
        assert bad == [] and worst == 0.0 and n == 3

    def test_generated_timestamp_is_ignored(self, tmp_path):
        a = {"generated_utc": "2026-01-01T00:00:00Z", "r": 0.342}
        b = {"generated_utc": "2026-10-22T00:00:00Z", "r": 0.342}
        bad, worst, _ = self._cmp(tmp_path, a, b)
        assert bad == []

    def test_nested_timestamp_is_ignored_too(self, tmp_path):
        """The ignore rule is leaf-name based, so a timestamp inside provenance
        cannot fail the gate either."""
        a = {"provenance": {"generated_utc": "x"}}
        b = {"provenance": {"generated_utc": "y"}}
        bad, _, _ = self._cmp(tmp_path, a, b)
        assert bad == []

    def test_numeric_difference_beyond_tolerance_is_caught(self, tmp_path):
        bad, worst, _ = self._cmp(tmp_path, {"r": 0.342}, {"r": 0.3425}, tol=0.0)
        assert len(bad) == 1 and bad[0][0] == "r"
        assert worst == pytest.approx(0.0005 / 1.0, rel=1e-3)

    def test_tolerant_mode_passes_blas_reordering(self, tmp_path):
        bad, _, _ = self._cmp(tmp_path, {"x": 1.0}, {"x": 1.0 + 1e-13},
                             tol=1e-12)
        assert bad == []

    def test_missing_key_is_a_presence_error(self, tmp_path):
        bad, _, _ = self._cmp(tmp_path, {"a": 1, "b": 2}, {"a": 1})
        assert bad and bad[0][3] == "presence"

    def test_bool_and_number_are_not_confused(self, tmp_path):
        bad, _, _ = self._cmp(tmp_path, {"k": True}, {"k": 1})
        assert len(bad) == 1 and bad[0][3] == "bool"

    def test_string_leaves_are_compared(self, tmp_path):
        bad, _, _ = self._cmp(tmp_path, {"m": "profiled"}, {"m": "deflate"})
        assert len(bad) == 1 and bad[0][3] == "str"

    def test_null_vs_number_does_not_crash(self, tmp_path):
        bad, _, _ = self._cmp(tmp_path, {"v": None}, {"v": 0.0})
        assert len(bad) == 1 and bad[0][3] == "str"

    def test_walk_json_flattens_lists_and_dicts(self):
        leaves = dict(RA.walk_json({"a": {"b": 1}, "c": [2, {"d": 3}]}))
        assert leaves == {"a.b": 1, "c[0]": 2, "c[1].d": 3}


# ---------------------------------------------------------------- diff_npz --
class TestDiffNpz:
    def test_identical_trees_pass(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir(); b.mkdir()
        for p in (a, b):
            _write_npz(p / "x.npz", r=np.array([0.34, 0.98]), m=np.zeros(4))
        bad, worst, nf, na = RA.diff_npz(a, b, 0.0)
        assert bad == [] and nf == 1 and na == 2 and worst == 0.0

    def test_numeric_difference_is_caught(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir(); b.mkdir()
        _write_npz(a / "x.npz", r=np.array([0.34, 0.98]))
        _write_npz(b / "x.npz", r=np.array([0.34, 0.980001]))
        bad, worst, _, _ = RA.diff_npz(a, b, 0.0)
        assert len(bad) == 1 and bad[0][3] == "numeric"
        assert worst > 0

    def test_missing_file_is_reported_not_crashed(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir(); b.mkdir()
        _write_npz(a / "x.npz", r=np.zeros(3))
        bad, _, _, _ = RA.diff_npz(a, b, 0.0)
        assert bad == [("x.npz", "<present>", "<missing>", "presence")]

    def test_extra_key_in_one_tree_is_reported(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir(); b.mkdir()
        _write_npz(a / "x.npz", r=np.zeros(3))
        _write_npz(b / "x.npz", r=np.zeros(3), extra=np.ones(2))
        bad, _, _, _ = RA.diff_npz(a, b, 0.0)
        assert bad and bad[0][0] == "x.npz:extra"

    def test_all_nan_array_matches_itself(self, tmp_path):
        """Regression: np.max on an all-NaN slice used to warn and mis-report."""
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir(); b.mkdir()
        n = np.full(5, np.nan)
        _write_npz(a / "x.npz", v=n)
        _write_npz(b / "x.npz", v=n.copy())
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            bad, worst, _, _ = RA.diff_npz(a, b, 0.0)
        assert bad == [] and worst == 0.0

    def test_nan_mask_mismatch_is_a_mask_error(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir(); b.mkdir()
        _write_npz(a / "x.npz", v=np.array([1.0, np.nan, 3.0]))
        _write_npz(b / "x.npz", v=np.array([1.0, 2.0, np.nan]))
        bad, _, _, _ = RA.diff_npz(a, b, 0.0)
        assert len(bad) == 1 and bad[0][3] == "mask"

    def test_nan_vs_zero_is_not_silently_equal(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir(); b.mkdir()
        _write_npz(a / "x.npz", v=np.array([np.nan]))
        _write_npz(b / "x.npz", v=np.array([0.0]))
        bad, _, _, _ = RA.diff_npz(a, b, 0.0)
        assert bad and bad[0][3] == "mask"

    def test_label_arrays_compare_by_content(self, tmp_path):
        """The <U truncation hazard: a 5-char dtype silently clips 'deflate'."""
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir(); b.mkdir()
        _write_npz(a / "x.npz", m=np.array(["profiled", "deflate"], dtype="<U9"))
        _write_npz(b / "x.npz", m=np.array(["profiled", "deflat"], dtype="<U8"))
        bad, _, _, _ = RA.diff_npz(a, b, 0.0)
        assert len(bad) == 1 and bad[0][3] == "labels"

    def test_shape_mismatch_is_a_shape_error(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir(); b.mkdir()
        _write_npz(a / "x.npz", v=np.zeros((4, 2)))
        _write_npz(b / "x.npz", v=np.zeros(8))
        bad, _, _, _ = RA.diff_npz(a, b, 0.0)
        assert bad and bad[0][3] == "shape"

    def test_zero_sized_array_is_skipped(self, tmp_path):
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir(); b.mkdir()
        _write_npz(a / "x.npz", v=np.zeros(0))
        _write_npz(b / "x.npz", v=np.zeros(0))
        bad, _, _, na = RA.diff_npz(a, b, 0.0)
        assert bad == [] and na == 1


# ------------------------------------------------------------- the redirect --
class TestResultsDirRedirect:
    """The safety property the whole tool rests on."""

    def test_both_harnesses_honour_sgldir(self, tmp_path):
        code = ("import expcommon as E;"
                "from ext import extcommon as X;"
                "print(E.DATA); print(X.DATA); print(E.PARTS.parent == E.DATA)")
        env = dict(os.environ, SGL_RESULTS_DIR=str(tmp_path))
        p = subprocess.run([sys.executable, "-c", code], cwd=str(D.ROOT / "src"),
                           env=env, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
        assert p.returncode == 0, p.stdout
        lines = p.stdout.split()
        assert lines[0] == lines[1] == str(tmp_path)
        assert lines[2] == "True"

    def test_default_is_the_shipped_tree(self):
        code = "import expcommon as E; print(E.DATA)"
        env = {k: v for k, v in os.environ.items() if k != "SGL_RESULTS_DIR"}
        p = subprocess.run([sys.executable, "-c", code], cwd=str(D.ROOT / "src"),
                           env=env, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
        assert p.stdout.strip() == str(D.RESULTS)


@pytest.mark.slow
class TestEntryPointRuns:
    """Functional test of the printed command, at the cheapest possible stage."""

    def test_quadrature_stage_reproduces_bit_for_bit(self, tmp_path):
        if shutil.disk_usage("/tmp").free < 3 * 1024**3:
            pytest.skip("scratch copy needs ~1 GB of free space")
        out = tmp_path / "repro.log"
        cmd = [sys.executable, "-m", "reproduce_all", "--stages", "quadrature",
               "--scratch", str(tmp_path / "scratch")]
        with open(out, "w") as fh:
            rc = subprocess.call(cmd, cwd=str(D.ROOT), stdout=fh,
                                 stderr=subprocess.STDOUT)
        text = out.read_text()
        assert rc == 0, text[-3000:]
        assert "RESULT: OK (0 archive diffs)" in text, text[-3000:]
        assert "archives:" in text and "audit.json:" in text

    def test_quadrature_stage_is_isolated_from_the_shipped_tree(self, tmp_path):
        before = {p.name: p.stat().st_mtime_ns for p in D.RESULTS.glob("*")
                  if p.is_file() and not p.name.startswith("ext_")}
        cmd = [sys.executable, "-m", "reproduce_all", "--stages", "quadrature",
               "--scratch", str(tmp_path / "scratch")]
        rc = subprocess.call(cmd, cwd=str(D.ROOT), stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        assert rc == 0
        after = {p.name: p.stat().st_mtime_ns for p in D.RESULTS.glob("*")
                 if p.is_file() and not p.name.startswith("ext_")}
        assert before == after, "a verification run wrote into results/"

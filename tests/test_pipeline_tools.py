"""Pipeline writer and tool tests.

Tests pure functions from tools/*.py: flat_name, remap/old_key inverses,
word-boundary substitution round trip, brace matcher in strip_rev, the portable
array manifest, and the shape of the CI LaTeX gate in tools/check_pdf_build.sh.
"""
import json
import sys
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from tests._data import TOOLS, RESULTS, ROOT


class TestFlattenArchives:
    """Test pure functions from tools/flatten_archives.py."""

    def test_flat_name_strips_prefix(self):
        sys.path.insert(0, str(TOOLS))
        from flatten_archives import flat_name
        assert flat_name("v2_clouds_s0") == "clouds_s0"
        assert flat_name("v1_res_s3") == "res_s3"
        assert flat_name("v3_null_s5") == "null_s5"

    def test_flat_name_no_prefix(self):
        sys.path.insert(0, str(TOOLS))
        from flatten_archives import flat_name
        assert flat_name("clouds_s0") == "clouds_s0"

    def test_flat_name_sigclv2(self):
        sys.path.insert(0, str(TOOLS))
        from flatten_archives import flat_name
        assert flat_name("sigclv2_s0") == "sigcldeflate_s0"

    def test_key_map_completeness(self):
        sys.path.insert(0, str(TOOLS))
        from flatten_archives import KEY_MAP
        # All keys should map v2 -> deflate
        for old, new in KEY_MAP.items():
            assert "v2" in old
            assert "deflate" in new


class TestVerifyFlat:
    """Test pure functions from tools/verify_flat.py."""

    def test_remap_v2_to_deflate(self):
        sys.path.insert(0, str(TOOLS))
        from verify_flat import remap
        assert remap("v2") == "deflate"
        assert remap("r_v2") == "r_deflate"

    def test_remap_compound(self):
        sys.path.insert(0, str(TOOLS))
        from verify_flat import remap
        assert remap("C_v2_deflate") == "C_deflate"

    def test_remap_word_boundary(self):
        sys.path.insert(0, str(TOOLS))
        from verify_flat import remap
        # sigma_sensitivity_v2 -> sigma_sensitivity_deflate
        assert remap("sigma_sensitivity_v2") == "sigma_sensitivity_deflate"


class TestVerifyPartsTransform:
    """Test old_key inverse from tools/verify_parts_transform.py."""

    def test_old_key_inverse(self):
        sys.path.insert(0, str(TOOLS))
        from verify_parts_transform import old_key
        # deflate -> v2 (inverse of KEY_MAP)
        assert old_key("deflate_pearson") == "v2_pearson"
        # No match -> identity
        assert old_key("r_profiled") == "r_profiled"


class TestStripRev:
    """Test brace matcher from tools/strip_rev.py."""

    def test_strip_simple(self):
        sys.path.insert(0, str(TOOLS))
        from strip_rev import strip
        text = r"Hello \rev{world}!"
        result, n = strip(text)
        assert result == "Hello world!"
        assert n == 1

    def test_strip_nested_braces(self):
        sys.path.insert(0, str(TOOLS))
        from strip_rev import strip
        text = r"\rev{text with {nested} braces}"
        result, n = strip(text)
        assert result == "text with {nested} braces"
        assert n == 1

    def test_strip_multiple(self):
        sys.path.insert(0, str(TOOLS))
        from strip_rev import strip
        text = r"\rev{first} and \rev{second}"
        result, n = strip(text)
        assert result == "first and second"
        assert n == 2

    def test_strip_no_rev(self):
        sys.path.insert(0, str(TOOLS))
        from strip_rev import strip
        text = "no markup here"
        result, n = strip(text)
        assert result == text
        assert n == 0

    def test_strip_escaped_braces(self):
        sys.path.insert(0, str(TOOLS))
        from strip_rev import strip
        text = r"\rev{text with \{ escaped \} braces}"
        result, n = strip(text)
        assert result == r"text with \{ escaped \} braces"
        assert n == 1

    def test_strip_roundtrip_on_tmp(self, tmp_path):
        """Test the full strip_rev on a tmp copy (does NOT touch paper/)."""
        sys.path.insert(0, str(TOOLS))
        from strip_rev import strip
        text = r"\documentclass{article}\rev{Revised text here.} End."
        result, n = strip(text)
        assert "Revised text here." in result
        assert r"\rev{" not in result


class TestArrayManifest:
    """Test pure functions from tools/array_manifest.py."""

    def test_digest_deterministic(self):
        sys.path.insert(0, str(TOOLS))
        from array_manifest import digest
        a = np.array([1.0, 2.0, 3.0])
        d1 = digest(a)
        d2 = digest(a)
        assert d1 == d2

    def test_digest_differs_for_different_arrays(self):
        sys.path.insert(0, str(TOOLS))
        from array_manifest import digest
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([1.0, 2.0, 4.0])
        assert digest(a) != digest(b)

    def test_manifest_keys_are_relative_to_the_root(self, tmp_path):
        """A frozen baseline must survive a different checkout path.

        The keys used to be absolute, which meant ``reproduce_all --check`` -- the
        CI drift gate -- could only pass on the machine that wrote the manifest.
        """
        sys.path.insert(0, str(TOOLS))
        from array_manifest import manifest
        root = tmp_path / "results"
        (root / "parts").mkdir(parents=True)
        np.savez_compressed(root / "a.npz", x=np.arange(4.0))
        np.savez_compressed(root / "parts" / "b.npz", y=np.ones(3))
        (root / "c.json").write_text('{"k": 1}')
        m = manifest(str(root))
        assert sorted(m) == ["a.npz", "c.json", "parts/b.npz"], sorted(m)
        assert not any(k.startswith("/") for k in m)

    def test_check_passes_from_a_copied_tree(self, tmp_path):
        """Write in one directory, check in another: same verdict, no MISSING."""
        import shutil
        sys.path.insert(0, str(TOOLS))
        from array_manifest import compare, manifest
        a = tmp_path / "aaa" / "results"
        a.mkdir(parents=True)
        np.savez_compressed(a / "x.npz", v=np.linspace(0, 1, 7))
        (a / "y.json").write_text('{"n": 7}')
        before = manifest(str(a))
        b = tmp_path / "bbb" / "results"
        shutil.copytree(a, b)
        problems, n = compare(str(b), before, {})
        assert problems == [], problems
        assert n == 2  # one npz array + one json archive

    def test_check_reads_a_legacy_absolute_manifest(self, tmp_path):
        """Absolute keys from an older freeze still resolve to the right files."""
        sys.path.insert(0, str(TOOLS))
        from array_manifest import compare, manifest_npz
        root = tmp_path / "results"
        root.mkdir()
        np.savez_compressed(root / "x.npz", v=np.arange(3.0))
        legacy = {str(root / "x.npz"): manifest_npz(root / "x.npz")}
        problems, _ = compare(str(root), legacy, {})
        assert problems == [], problems

    def test_check_reports_a_real_change(self, tmp_path):
        sys.path.insert(0, str(TOOLS))
        from array_manifest import compare, manifest
        a = tmp_path / "results"
        a.mkdir()
        np.savez_compressed(a / "x.npz", v=np.arange(3.0))
        before = manifest(str(a))
        np.savez_compressed(a / "x.npz", v=np.arange(3.0) + 1)
        problems, _ = compare(str(a), before, {})
        assert any("content differs" in p for p in problems), problems


class TestPdfBuildGate:
    """The CI paper gate: tools/check_pdf_build.sh and the job that calls it.

    Two bugs lived here in sequence, and both were invisible until CI ran.  The
    first: the job grepped ``pdftotext main.pdf`` for "Solar Gravitational Lens",
    but the typeset title breaks as "... with the Solar /\\nGravitational Lens:", so
    the phrase is never on one line of the raw text stream and a perfect 36-page PDF
    failed the check.  The second: the job compiled into the working tree and only
    then compared the document mirrors byte-for-byte -- pdfTeX stamps a creation date
    into every PDF, so any in-tree build makes that gate fail no matter what was
    changed.  These tests pin the shape of the fixed jobs.
    """

    SCRIPT = ROOT / "tools" / "check_pdf_build.sh"
    WORKFLOW = ROOT / ".github" / "workflows" / "verify.yml"

    def test_gate_script_exists_and_parses(self):
        assert self.SCRIPT.is_file(), "tools/check_pdf_build.sh is missing"
        p = subprocess.run(["bash", "-n", str(self.SCRIPT)],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True)
        assert p.returncode == 0, p.stdout

    def test_gate_script_flattens_whitespace_before_grepping(self):
        """The phrase check must run on whitespace-normalised text."""
        body = self.SCRIPT.read_text()
        assert "tr '[:space:]' ' '" in body, "text is not flattened before grep"
        assert 'tr -s \' \'' in body, "runs of whitespace are not squeezed"
        # the exact shape of the old bug: grepping the raw stream for a phrase
        assert not re.search(r"pdftotext[^\n|]*\|\s*grep", body), \
            "raw pdftotext stream piped straight into grep"

    def test_gate_script_compares_page_counts_not_bytes(self):
        """A fresh build is never byte-identical to a shipped PDF."""
        body = self.SCRIPT.read_text()
        assert "sha256sum" not in body and "md5sum" not in body
        assert re.search(r'pdfinfo "\$\(shipped\)"|pdfinfo "\$shipped"', body), \
            "the shipped PDF's length is not measured"
        assert '"$fresh" = "$pages"' in body

    def test_gate_script_forces_a_real_compile(self):
        """latexmk will call a copied PDF up to date and compile nothing."""
        body = self.SCRIPT.read_text()
        assert re.search(r"-name '\*\.pdf'.*?-delete", body, re.S), \
            "the copied PDFs are not deleted, so latexmk may skip the build"
        assert "$build/paper" in body, "the build does not happen in a scratch copy"

    def test_gate_needles_are_present_in_the_shipped_pdfs(self):
        """Every phrase the gate greps for must exist, or the gate is theatre.

        The needles are read from the script rather than duplicated here: this is
        what caught the retitle, when the gate was still grepping for a subtitle
        that the manuscript no longer has.  ``" ".join(raw.split())`` is the
        ``tr`` pipeline the gate runs -- pdftotext breaks the typeset title across
        a line, so the phrase exists in the document but never on one line of its
        raw text stream.
        """
        pdfs = {"main": ROOT / "paper" / "main.pdf",
                "cover_letter": ROOT / "submission" / "cover_letter.pdf"}
        body = self.SCRIPT.read_text()
        sets = re.findall(r"(\w+)_needles=\((.*?)\)\n", body, re.S)
        assert len(sets) == 2, sets
        if shutil.which("pdftotext") is None:
            pytest.skip("pdftotext unavailable")
        for job, rhs in sets:
            needles = re.findall(r'"([^"]+)"', rhs)
            assert needles, job + " declares no needles"
            pdf = pdfs[job]
            assert pdf.is_file(), str(pdf) + " is missing"
            raw = subprocess.run(["pdftotext", str(pdf), "-"],
                                 stdout=subprocess.PIPE, text=True).stdout
            flat = " ".join(raw.split())
            assert raw.strip(), str(pdf) + " has no extractable text"
            for needle in needles:
                assert needle in flat, f"{job}: '{needle}' is not in {pdf.name}"

    def test_ci_paper_job_checks_mirrors_before_building(self):
        yaml = pytest.importorskip("yaml")
        spec = yaml.safe_load(self.WORKFLOW.read_text())
        steps = spec["jobs"]["paper"]["steps"]
        runs = [s.get("name", "") + "\n" + str(s.get("run", "")) for s in steps]
        mirror = next(i for i, r in enumerate(runs) if "make_app_docs.py --check" in r)
        build = next(i for i, r in enumerate(runs) if "check_pdf_build.sh" in r)
        assert mirror < build, \
            "the mirror gate must read the untouched checkout, not a rebuilt tree"
        # nothing may compile into the checkout at all
        for s in steps:
            assert "working-directory" not in s, s.get("name")
            run = str(s.get("run", ""))
            assert "latexmk -pdf" not in run, \
                "the job compiles directly in the working tree: " + str(s.get("name"))

    def test_ci_gates_job_gives_the_fast_tier_a_numeric_tolerance(self):
        """Bit-for-bit equality is a property of one BLAS, not of the result.

        The first CI run of this workflow failed here for exactly that reason: 5
        of 639 stored arrays came back 4.2e-15 away from the shipped values on an
        Ubuntu runner.  The gate is only meaningful if it says what it compares.
        """
        yaml = pytest.importorskip("yaml")
        spec = yaml.safe_load(self.WORKFLOW.read_text())
        runs = [str(s.get("run", "")) for s in spec["jobs"]["gates"]["steps"]]
        fast = [r for r in runs if "reproduce_all --fast" in r]
        assert fast, "the gates job no longer runs the fast reproduction tier"
        for r in fast:
            assert "--tol" in r, "CI compares floats for exact equality: " + r


class TestVerifyNumbersStack:
    """tools/verify_numbers.sh -- the proof stack as one command.

    The repository now has four numeric gates plus two structural ones, and a
    reviewer is not going to remember the order.  The script is the order, so it
    is worth pinning: a step that quietly disappears from it is a gate nobody ran,
    and a step that starts compiling into the checkout breaks the mirror gate that
    keeps ``public/docs/`` honest.
    """

    SCRIPT = ROOT / "tools" / "verify_numbers.sh"
    WORKFLOW = ROOT / ".github" / "workflows" / "verify.yml"

    def body(self) -> str:
        return self.SCRIPT.read_text()

    def test_it_exists_and_parses(self):
        assert self.SCRIPT.is_file(), "the one-command proof stack is missing"
        p = subprocess.run(["bash", "-n", str(self.SCRIPT)],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True)
        assert p.returncode == 0, p.stdout

    def test_it_is_executable(self):
        assert self.SCRIPT.stat().st_mode & 0o111, \
            "a gate nobody can run without typing bash is a gate people skip"

    def test_it_reports_a_count_and_fails_on_one(self):
        body = self.body()
        assert '[ "$fails" -eq 0 ] || exit 1' in body, \
            "the script must not end green when a step went red"
        assert 'printf' in body and "passed," in body

    def test_every_proof_layer_is_in_the_stack(self):
        body = self.body()
        for tool, flag in (("tools/derive_stats.py", "--check"),
                           ("tools/claims.py", "--check"),
                           ("tools/claims.py", "--coverage"),
                           ("tools/manuscript_outline.py", ""),
                           ("tools/doc_numbers.py", ""),
                           ("tools/verify_flat.sh", "bash"),
                           ("src/make_app_docs.py", "--check")):
            assert tool in body and flag in body, f"{tool} {flag} is not run"

    def test_the_ledger_is_run_strictly_not_loosely(self):
        """``--max-untraceable 0`` is the standard the manuscript claims."""
        body = self.body()
        assert "--max-untraceable 0" in body
        assert re.search(r"--min-claims +\d+", body), \
            "an empty ledger would pass a check with no floor"

    def test_the_suites_that_test_the_tools_are_included(self):
        body = self.body()
        for suite in ("tests/test_claims_ledger.py", "tests/test_manuscript_outline.py",
                      "tests/test_doc_numbers.py"):
            assert suite in body, f"{suite} is not part of the stack"
        assert "--strict-markers" in body and "--strict-config" in body

    def test_it_delegates_the_build_rather_than_compiling(self):
        """Same rule as CI: pdfTeX stamps a creation date, so the checkout is not
        a build directory."""
        body = self.body()
        assert re.search(r"\blatexmk -pdf\b", body) is None, \
            "the stack compiles on its own; it must call tools/check_pdf_build.sh"
        assert "command -v latexmk" in body, "the toolchain is assumed, not probed"
        assert "tools/check_pdf_build.sh" in body
        assert "--with-pdf" in body, "the rebuild is opt-in, not skipped silently"
        assert "mktemp -d" in body and 'rm -rf "$scratch"' in body

    def test_the_pdf_branch_audits_the_fresh_build(self):
        body = self.body()
        assert "--build-dir" in body and "--pdf-text" in body
        assert re.search(r"--compare-record[\s\S]{0,90}manuscript_build_record\.json",
                         body), "the tracked record is not diffed against the build"

    def test_quick_only_skips_the_slow_layers(self):
        body = self.body()
        assert "--quick" in body
        assert body.count('[ "$QUICK" -eq 0 ]') == 2, \
            "--quick must guard the suites and the gates, nothing else"
        first_guard = body.index('[ "$QUICK" -eq 0 ]')
        for tool in ("derive_stats.py", "claims.py", "doc_numbers.py",
                     "manuscript_outline.py"):
            assert body.index(tool) < first_guard, \
                f"{tool} sits behind --quick, so a quick run skips a number gate"

    def test_ci_runs_the_same_layers_the_script_does(self):
        """The script is the local entry point and the ``numbers`` job is the
        remote one; a step present in only half of them is a step that will pass
        locally and surprise nobody until it is the only evidence."""
        yaml = pytest.importorskip("yaml")
        spec = yaml.safe_load(self.WORKFLOW.read_text())
        steps = spec["jobs"]["numbers"]["steps"]
        runs = "\n".join(str(s.get("run", "")) for s in steps)
        body = self.body()
        for tool in ("tools/derive_stats.py", "tools/claims.py",
                     "tools/doc_numbers.py", "tools/manuscript_outline.py"):
            assert (tool in runs) == (tool in body), f"{tool} is in one gate only"


class TestPackageTestEntryPoints:
    """package.json's test scripts, so the repository has one npm-shaped door."""

    PKG = json.loads((ROOT / "package.json").read_text())

    def test_the_app_scripts_are_untouched(self):
        scripts = self.PKG["scripts"]
        for name, value in (("dev", "next dev"), ("build", "next build"),
                            ("start", "next start")):
            assert scripts[name] == value, name

    def test_a_test_script_exists_for_each_tier(self):
        scripts = self.PKG["scripts"]
        assert "test" in scripts and "test:slow" in scripts
        assert "test:numbers" in scripts and "test:paper" in scripts

    def test_the_default_test_script_is_the_fast_tier(self):
        run = self.PKG["scripts"]["test"]
        assert "-m \"not slow\"" in run, "npm test would re-run the simulation"
        assert "--strict-markers" in run and "--strict-config" in run

    def test_the_slow_script_selects_only_the_slow_tier(self):
        assert "-m slow" in self.PKG["scripts"]["test:slow"]

    def test_the_number_scripts_call_the_stack(self):
        assert "tools/verify_numbers.sh" in self.PKG["scripts"]["test:numbers"]
        assert "tools/verify_numbers.sh --with-pdf" in self.PKG["scripts"]["test:paper"]

    def test_the_ci_gates_job_and_npm_test_ask_for_the_same_thing(self):
        yaml = pytest.importorskip("yaml")
        spec = yaml.safe_load((ROOT / ".github" / "workflows" / "verify.yml").read_text())
        runs = [str(s.get("run", "")) for s in spec["jobs"]["gates"]["steps"]]
        pytest_runs = [r for r in runs if "pytest tests" in r]
        assert len(pytest_runs) == 1, "the gates job runs pytest more than once"
        for flag in ("-q", '-m "not slow"', "--strict-markers", "--strict-config"):
            assert flag in pytest_runs[0], f"CI does not pass {flag}: {pytest_runs[0]}"
            assert flag in self.PKG["scripts"]["test"], f"npm test lacks {flag}"


class TestCiNumbersJob:
    """The third job: what makes a numeric defect fail a push, cheaply."""

    WORKFLOW = ROOT / ".github" / "workflows" / "verify.yml"

    def spec(self):
        yaml = pytest.importorskip("yaml")
        return yaml.safe_load(self.WORKFLOW.read_text())

    def test_the_three_jobs_exist_and_are_split_by_dependency(self):
        spec = self.spec()
        assert set(spec["jobs"]) == {"gates", "numbers", "paper"}
        paper_runs = "\n".join(str(s.get("run", ""))
                               for s in spec["jobs"]["paper"]["steps"])
        numbers_runs = "\n".join(str(s.get("run", ""))
                                 for s in spec["jobs"]["numbers"]["steps"])
        assert "apt-get install" in paper_runs, "TeX Live belongs to the paper job"
        assert "apt-get" not in numbers_runs, \
            "the numbers job must not pay for a distribution install"

    def test_every_job_declares_its_own_ceiling(self):
        for job, spec_ in self.spec()["jobs"].items():
            assert "timeout-minutes" in spec_, job + " inherits the six-hour default"

    def test_the_paper_ceiling_clears_the_install_that_cancelled_it(self):
        """The failure this job was split to fix: 20m17s, cancelled mid-apt."""
        assert self.spec()["jobs"]["paper"]["timeout-minutes"] >= 40

    def test_pushes_cancel_the_previous_run(self):
        conc = self.spec().get("concurrency")
        assert isinstance(conc, dict) and conc.get("cancel-in-progress") is True, \
            "a series of pushes queues identical TeX Live installs"

    def test_the_numbers_job_is_a_build_and_test_cycle(self):
        runs = "\n".join(str(s.get("run", ""))
                         for s in self.spec()["jobs"]["numbers"]["steps"])
        assert runs.index("derive_stats.py --check") < runs.index("claims.py --check"), \
            "the ledger is checked before the statistics it cites are rebuilt"
        assert "doc_numbers.py" in runs and "manuscript_outline.py" in runs
        assert "tests/test_doc_numbers.py" in runs

    def test_the_documentation_audit_has_a_floor_in_ci(self):
        runs = "\n".join(str(s.get("run", ""))
                         for s in self.spec()["jobs"]["numbers"]["steps"])
        m = re.search(r"doc_numbers\.py.*?--min-claims (\d+)", runs, re.S)
        assert m, "the documentation audit runs in CI without a floor on its size"
        assert int(m.group(1)) >= 30

    def test_the_paper_job_uploads_what_it_built(self):
        steps = self.spec()["jobs"]["paper"]["steps"]
        upload = [s for s in steps
                  if "upload-artifact" in str(s.get("uses", ""))]
        assert len(upload) == 1
        with_ = upload[0]["with"]
        assert with_["if-no-files-found"] == "error", \
            "a build that produced nothing must not look like a pass"
        assert any("main.log" in p for p in str(with_["path"]).split()), \
            "the log is the only evidence about overfull boxes and references"

    def test_the_build_is_audited_not_only_compiled(self):
        runs = "\n".join(str(s.get("run", "")) for s in self.spec()["jobs"]["paper"]["steps"])
        assert "--pdf-text" in runs, "the built PDF's digits are never checked"
        assert "--strict-metadata" in runs
        assert "--compare-record" in runs, \
            "the tracked build record is never diffed against the real build"

    def test_step_summaries_carry_the_numbers_a_reviewer_wants(self):
        runs = "\n".join(str(s.get("run", "")) for s in
                         self.spec()["jobs"]["numbers"]["steps"] +
                         self.spec()["jobs"]["paper"]["steps"])
        assert runs.count("GITHUB_STEP_SUMMARY") >= 3
        assert "Unexplained" in runs and "fingerprint" not in runs

"""Pipeline writer and tool tests.

Tests pure functions from tools/*.py: flat_name, remap/old_key inverses,
word-boundary substitution round trip, brace matcher in strip_rev, the portable
array manifest, and the shape of the CI LaTeX gate in tools/check_pdf_build.sh.
"""
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

    def test_wrapped_title_is_found_after_flattening(self):
        """The shipped manuscript really does break its title, and the gate copes.

        ``" ".join(raw.split())`` is what the gate's ``tr`` pipeline does; the point
        is that the phrase exists in the PDF but not as one line of its text stream.
        """
        pdf = ROOT / "paper" / "main.pdf"
        if not pdf.is_file() or shutil.which("pdftotext") is None:
            pytest.skip("pdftotext or paper/main.pdf unavailable")
        raw = subprocess.run(["pdftotext", str(pdf), "-"],
                             stdout=subprocess.PIPE, text=True).stdout
        flat = " ".join(raw.split())
        assert raw.strip(), "the shipped PDF has no extractable text"
        for phrase in ("Solar Gravitational Lens", "Reconstruction Algorithms"):
            assert phrase in flat, phrase + " is missing from the manuscript"

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

"""Pipeline writer and tool tests.

Tests pure functions from tools/*.py: flat_name, remap/old_key inverses,
word-boundary substitution round trip, brace matcher in strip_rev.
"""
import sys
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from tests._data import TOOLS, RESULTS


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

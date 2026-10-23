"""Archive schema tests: method/component labels, version pattern, PART_PREFIX.

Anti-regression net for the single-version rename.
"""
import json
import re
import numpy as np
import pytest

from tests._data import load_audit, RESULTS, PARTS
import expcommon as E


# Version pattern: word-boundary v1/v2/v3 NOT preceded/followed by alnum
VERSION_RE = re.compile(r"(?<![a-z0-9])v[123](?![0-9a-z])")


class TestMethodLabels:
    """Assert every shipped archive's method/component label arrays
    equal E.RECON_METHODS / E.ABLATION_COMPONENTS / E.SIGCL_ESTIMATORS
    element-for-element in ORDER."""

    def test_clouds_methods(self):
        d = np.load(RESULTS / "clouds.npz", allow_pickle=True)
        stored = [str(x) for x in np.asarray(d["methods"]).ravel()]
        assert stored == list(E.RECON_METHODS)

    def test_component_ablation_methods(self):
        d = np.load(RESULTS / "component_ablation.npz", allow_pickle=True)
        stored = [str(x) for x in np.asarray(d["methods"]).ravel()]
        assert stored == list(E.ABLATION_COMPONENTS)

    def test_audit_clouds_methods(self):
        audit = load_audit()
        stored = audit["clouds"]["methods"]
        assert stored == list(E.RECON_METHODS)


class TestNoVersionTokens:
    """Assert no key or stored string label matches the version pattern."""

    def test_no_v123_in_npz_keys(self):
        """No npz archive key matches the version pattern."""
        for p in sorted(RESULTS.glob("*.npz")):
            d = np.load(p, allow_pickle=True)
            for k in d.files:
                assert not VERSION_RE.search(k), \
                    f"{p.name}: key '{k}' matches version pattern"

    def test_no_v123_in_npz_string_values(self):
        """No stored string label in npz archives matches the version pattern."""
        for p in sorted(RESULTS.glob("*.npz")):
            d = np.load(p, allow_pickle=True)
            for k in d.files:
                a = np.asarray(d[k])
                if a.dtype.kind in "OSU":
                    for v in a.ravel():
                        s = str(v)
                        assert not VERSION_RE.search(s), \
                            f"{p.name}:{k} value '{s}' matches version pattern"

    def test_no_v123_in_audit_json(self):
        """No key in audit.json matches the version pattern."""
        audit_text = (RESULTS / "audit.json").read_text()
        # Check keys only (not values like "dv30_face_on_kms")
        audit = json.loads(audit_text)
        self._check_keys(audit, "")

    def _check_keys(self, node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                full = f"{path}/{k}"
                assert not VERSION_RE.search(k), \
                    f"audit key '{full}' matches version pattern"
                self._check_keys(v, full)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                self._check_keys(v, f"{path}[{i}]")

    def test_dv30_not_flagged(self):
        """dv30_face_on_kms must NOT be flagged (it has digit after v3)."""
        assert not VERSION_RE.search("dv30_face_on_kms")

    def test_v2_alone_is_flagged(self):
        """Bare 'v2' should match."""
        assert VERSION_RE.search("v2_pearson")
        assert VERSION_RE.search("sigma_sensitivity_v2")


class TestPartsNoVersionPrefix:
    """Assert results/parts has no file name starting with v1_/v2_/v3_."""

    def test_no_version_prefix_in_parts(self):
        for p in PARTS.glob("*.npz"):
            name = p.name
            assert not name.startswith("v1_"), f"parts file {name} starts with v1_"
            assert not name.startswith("v2_"), f"parts file {name} starts with v2_"
            assert not name.startswith("v3_"), f"parts file {name} starts with v3_"


class TestPartPrefix:
    """PART_PREFIX must be empty string (single-version suite)."""

    def test_part_prefix_empty(self):
        assert E.PART_PREFIX == ""

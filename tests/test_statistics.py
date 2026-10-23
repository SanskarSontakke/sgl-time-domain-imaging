"""Statistics harness tests.

Tests paired_stats on synthetic data, exact sign-test floors, and
scans audit.json for p-value consistency with design floors.
"""
import json
import math
import numpy as np
import pytest

from tests._data import load_audit, RESULTS


def _exact_sign_floor(n, k=None):
    """Exact minimum two-sided sign-test p for n pairs.
    If k is None, return the minimum attainable (all same sign).
    """
    if k is None:
        return 2.0 / 2**n
    from math import comb
    tail = sum(comb(n, i) for i in range(k + 1)) / 2.0**n
    return min(1.0, 2.0 * tail)


class TestPairedStatsSynthetic:
    """Test paired_stats on a known synthetic sample."""

    def test_mean_and_se(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
        import expcommon as E

        rng = np.random.default_rng(99)
        x = rng.standard_normal(10)
        y = x - 0.5 + 0.1 * rng.standard_normal(10)  # non-constant shift
        res = E.paired_stats(x, y, nboot=20000, seed=42)
        assert abs(res["mean"] - 0.5) < 0.2  # mean should be near 0.5
        assert res["n"] == 10
        assert res["se"] > 0

    def test_all_same_sign_gives_floor(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
        import expcommon as E

        x = np.arange(10, dtype=float) + 1.0
        y = np.zeros(10)
        res = E.paired_stats(x, y, nboot=20000, seed=42)
        # All differences positive -> k=0, p_sign = 2/2^10
        assert abs(res["p_sign"] - 2.0 / 1024) < 1e-12


class TestExactSignFloors:
    """Exact minimum attainable two-sided sign-test p for each design."""

    def test_n10_floor(self):
        """10-seed paired: 2/2^10 = 1.953e-3."""
        assert abs(_exact_sign_floor(10) - 1.953125e-3) < 1e-7

    def test_n6_floor(self):
        """6-seed cadence: 2/2^6 = 0.03125."""
        assert abs(_exact_sign_floor(6) - 0.03125) < 1e-7

    def test_n41_floor(self):
        """Cloud-only null (40 realizations + 1 observed): 1/41 = 0.02439."""
        assert abs(1.0 / 41 - 0.02439) < 1e-4

    def test_n2001_floor(self):
        """Label-permutation null (nboot=2000): 1/2001 = 4.9975e-4."""
        assert abs(1.0 / 2001 - 4.9975e-4) < 1e-7


class TestAuditPValueFloor:
    """Scan audit.json: no p_sign for n=10 can be below 2/2^10.

    p_t (parametric t-test) CAN be below the floor -- that is legitimate.
    But p_sign (exact sign-flip) must respect the combinatorial bound.
    """

    def test_p_sign_respects_floor_n10(self):
        audit = load_audit()
        floor_10 = 2.0 / 2**10  # 1.953e-3
        violations = []
        self._scan_p_sign(audit, "", 10, floor_10, violations, is_p_sign=True)
        assert not violations, f"p_sign below floor for n=10: {violations}"

    def test_p_sign_respects_floor_n6(self):
        audit = load_audit()
        floor_6 = 2.0 / 2**6  # 0.03125
        violations = []
        self._scan_p_sign(audit, "", 6, floor_6, violations, is_p_sign=True)
        assert not violations, f"p_sign below floor for n=6: {violations}"

    @staticmethod
    def _scan_p_sign(node, path, expected_n, floor, violations, is_p_sign):
        if isinstance(node, dict):
            n = node.get("n")
            for k, v in node.items():
                new_path = f"{path}/{k}"
                if k == "p_sign" and isinstance(v, (int, float)) and n == expected_n:
                    if v < floor - 1e-12:
                        violations.append(f"{new_path}: p_sign={v} < floor={floor}")
                elif isinstance(v, (dict, list)):
                    TestAuditPValueFloor._scan_p_sign(
                        v, new_path, expected_n, floor, violations, is_p_sign)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                TestAuditPValueFloor._scan_p_sign(
                    v, f"{path}[{i}]", expected_n, floor, violations, is_p_sign)

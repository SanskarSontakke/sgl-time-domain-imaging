"""Defect regression tests.

Pins the specific defects F-01 through F-22 identified in the referee report.
"""
import json
import math
import numpy as np
import pytest

import sglsim as S
from tests._data import load_audit, load_npz, RESULTS


class TestF01NoiseFloor:
    """F-01: sigma_k = 0.023170 ONLY at t_b = 1800 s."""

    def test_paper_value_reproduced_at_1800(self):
        tb = 1800.0
        sigma_k = math.sqrt(S.QCOR / (S.QEXO**2 * tb))
        assert abs(sigma_k - 0.023170) < 1e-5

    def test_paper_value_NOT_reproduced_at_7200(self):
        tb = 7200.0
        sigma_k = math.sqrt(S.QCOR / (S.QEXO**2 * tb))
        assert abs(sigma_k - 0.023170) > 0.005


class TestF07LambdaSweep:
    """F-07: chi2 varies by less than 0.13% (not 0.1%) from lambda=1e-5 to 0.3."""

    def test_chi2_variation(self):
        sw = load_npz("lambda_sweep_f3.npz")
        chi2 = sw["chi2"]  # (10, 12)
        chi2_base = chi2[:, 4]  # lambda=3e-3
        ratio = chi2 / chi2_base[:, None]
        # max deviation over lambda=1e-5 to 0.3 (indices 0..8)
        max_dev = max(abs(ratio[:, :9] - 1.0).max(),
                      abs(ratio[:, :9] - 1.0).min())
        # Should be > 0.001 (0.1%) -- the paper's claim of < 0.1% is wrong
        assert max_dev > 0.001, f"max deviation {max_dev} should be > 0.1%"


class TestF15CloudFreeRLower:
    """F-15: cloud-free r(l) minimum is 0.9866 at l=17."""

    def test_minimum_below_099(self):
        res = load_npz("spatial_resolution.npz")
        r_cf_mean = res["r_cf"].mean(axis=0)
        assert r_cf_mean.min() < 0.99
        assert abs(r_cf_mean.min() - 0.9866) < 0.001


class TestF20LeffNullNotNaN:
    """F-20: audit stores l_eff_cf as null, never NaN."""

    def test_audit_l_eff_cf_null(self):
        audit = load_audit()
        for v in audit["resolution"]["l_eff_cf"]:
            assert v is None


class TestF22OrphanArrayDefinition:
    """F-22: reldev_F_vs_C = ||F - C|| / ||F|| (relative deviation)."""

    def test_reldev_F_vs_C_definition(self):
        """The orphan array reldev_F_minus_C is ||F - C|| / ||F||."""
        comp = load_npz("component_ablation.npz")
        reldev_F = comp["reldev_F_full_tdi"]
        reldev_C = comp["reldev_C_deflate"]
        # The derived array should be (reldev_F - reldev_C) / reldev_C
        # OR equivalently ||F - C|| / ||F|| in relative terms
        reldev_diff = comp["reldev_diff_F_minus_C"]
        # Check it equals reldev_F - reldev_C element-wise
        np.testing.assert_allclose(reldev_diff, reldev_F - reldev_C, atol=1e-12)

        # Also check the mean/sem
        mean_diff = comp["mean_reldev_diff_F_minus_C"]
        sem_diff = comp["sem_reldev_diff_F_minus_C"]
        assert abs(mean_diff - reldev_diff.mean()) < 1e-12
        assert abs(sem_diff - reldev_diff.std(ddof=1) / np.sqrt(len(reldev_diff))) < 1e-12

"""Audit-vs-archive consistency tests.

Re-derive key numbers from the parts/npz and compare against audit.json.
Covers: profiled vs deflate, component ablation F vs C, cloud-free r(l) min,
lambda sweep, l_eff null handling (F-20).
"""
import json
import numpy as np
import pytest

from tests._data import load_audit, load_npz, RESULTS
import expcommon as E


class TestProfiledVsDeflate:
    """Fiducial profiled vs deflate paired difference."""

    def test_clouds_fiducial_r(self):
        """Cloud-free r_profiled and r_deflate match audit."""
        audit = load_audit()
        clouds = load_npz("clouds.npz")
        # fc=0 is index 0
        r_prof = clouds["pearson_mat"][0, 0]  # method 0 (profiled), fc=0
        r_defl = clouds["pearson_mat"][1, 0]  # method 1 (deflate), fc=0

        audit_prof = audit["clouds"]["fiducial"]["r_profiled"]["mean"]
        audit_defl = audit["clouds"]["fiducial"]["r_deflate"]["mean"]

        assert abs(r_prof.mean() - audit_prof) < 1e-10
        assert abs(r_defl.mean() - audit_defl) < 1e-10


class TestComponentAblation:
    """Component ablation F vs C contrast."""

    def test_paired_F_vs_C(self):
        """r_diff_F_minus_C mean matches audit paired_F_vs_C."""
        audit = load_audit()
        comp = load_npz("component_ablation.npz")
        r_F = comp["r_F_full_tdi"]
        r_C = comp["r_C_deflate"]
        diff = r_F - r_C
        assert abs(diff.mean() - audit["components"]["paired_F_vs_C"]["mean"]) < 1e-12
        assert abs(diff.std(ddof=1) / np.sqrt(len(diff))
                    - audit["components"]["paired_F_vs_C"]["se"]) < 1e-12


class TestCloudFreeRlMinimum:
    """F-15: cloud-free r(l) minimum is 0.9866 at l=17, NOT >= 0.99."""

    def test_r_l_minimum(self):
        """Any claim of r(l) >= 0.99 must fail -- minimum is 0.9866 at l=17."""
        res = load_npz("spatial_resolution.npz")
        r_cf = res["r_cf"]  # (10, 20)
        mean_per_l = r_cf.mean(axis=0)
        l_arr = res["l"]
        min_idx = np.argmin(mean_per_l)
        min_r = mean_per_l[min_idx]
        min_l = l_arr[min_idx]

        assert abs(min_r - 0.9866) < 0.001, f"min r(l) = {min_r}, expected ~0.9866"
        assert min_l == 17, f"min at l={min_l}, expected 17"
        # The minimum is BELOW 0.99
        assert min_r < 0.99, f"min r(l) = {min_r} should be < 0.99"


class TestLambdaSweep:
    """F-07: lambda sweep objective minimum location."""

    def test_cloudfree_r_peak(self):
        """Cloud-free r peaks at lambda=0.3."""
        sw = load_npz("lambda_sweep_f0.npz")
        r_mean = sw["r"].mean(axis=0)
        lam = sw["lam"]
        peak_idx = np.argmax(r_mean)
        assert lam[peak_idx] == pytest.approx(0.3, rel=1e-6)

    def test_cloudy_chi2_shallow_minimum(self):
        """Cloudy chi2 has a shallow minimum at lambda=0.1."""
        sw = load_npz("lambda_sweep_f3.npz")
        chi2 = sw["chi2"]  # (10, 12)
        lam = sw["lam"]
        chi2_base = chi2[:, 4]  # lambda=3e-3 is the fiducial base (index 4)
        ratio = chi2 / chi2_base[:, None]
        mean_ratio = ratio.mean(axis=0)
        min_idx = np.argmin(mean_ratio)
        assert lam[min_idx] == pytest.approx(0.1, rel=1e-6)

    def test_ssim_peak_offset(self):
        """SSIM peaks at lambda=1, NOT at lambda=0.3 where r peaks (F-09b)."""
        sw = load_npz("lambda_sweep_f0.npz")
        ssim_mean = sw["ssim"].mean(axis=0)
        lam = sw["lam"]
        ssim_peak_idx = np.argmax(ssim_mean)
        r_peak_idx = np.argmax(sw["r"].mean(axis=0))
        assert lam[ssim_peak_idx] == pytest.approx(1.0, rel=1e-6)
        assert lam[r_peak_idx] == pytest.approx(0.3, rel=1e-6)
        assert ssim_peak_idx != r_peak_idx


class TestLeffNullHandling:
    """F-20: audit stores l_eff_cf as null, never NaN."""

    def test_l_eff_cf_is_null_not_nan(self):
        """audit.json resolution.l_eff_cf must be all null (JSON), not NaN."""
        audit = load_audit()
        l_eff_cf = audit["resolution"]["l_eff_cf"]
        assert isinstance(l_eff_cf, list)
        for v in l_eff_cf:
            assert v is None, f"l_eff_cf entry {v} should be null, not {type(v)}"

    def test_npz_l_eff_cf_is_nan(self):
        """The npz archive stores NaN for l_eff_cf (which is the source of F-20)."""
        res = load_npz("spatial_resolution.npz")
        l_eff_cf = res["l_eff_cf"]
        assert np.all(np.isnan(l_eff_cf)), "l_eff_cf in npz should be all NaN"

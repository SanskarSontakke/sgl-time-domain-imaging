"""Kernel tests: cellmean centre value and F-14 homogeneity defect.

The cellmean kernel centre = D*log(1+sqrt(2))/pitch.
F-14: offdiag_rel_err is constant (0.036558) for all n -- NOT convergent.
But energy_frac_3x3, energy_frac_r4, peak_to_offdiag_cm DO vary with n.
"""
import math
import numpy as np
import pytest

import sglsim as S
from tests._data import load_audit, RESULTS

import json


class TestCellmeanKernel:
    """Cell-mean kernel centre value."""

    def test_cellmean_formula(self):
        """K00_cellmean = D * log(1+sqrt(2)) / pitch."""
        kc = json.loads((RESULTS / "kernel_convergence.json").read_text())
        for n_str, entry in kc.items():
            n = int(n_str)
            pitch = S.DIMG / n
            expected = S.DTEL * math.log(1.0 + math.sqrt(2.0)) / pitch
            assert abs(entry["cellmean_formula"] - expected) < 1e-12, \
                f"n={n}: cellmean_formula {entry['cellmean_formula']} != {expected}"


class TestF14Homogeneity:
    """Defect F-14: offdiag_rel_err is constant in n (degree -1 homogeneity)."""

    def test_offdiag_rel_err_constant(self):
        """offdiag_rel_err is the SAME for all n and both cores."""
        kc = json.loads((RESULTS / "kernel_convergence.json").read_text())
        vals = set()
        for n_str, entry in kc.items():
            vals.add(round(entry["offdiag_rel_err_point"], 10))
            vals.add(round(entry["offdiag_rel_err_cellmean"], 10))
        assert len(vals) == 1, f"offdiag_rel_err should be constant, got {vals}"
        val = list(vals)[0]
        assert abs(val - 0.036558) < 1e-4

    def test_energy_frac_varies_with_n(self):
        """energy_frac_3x3 and energy_frac_r4 DO vary with n."""
        kc = json.loads((RESULTS / "kernel_convergence.json").read_text())
        e3x3_vals = [entry["energy_frac_3x3"] for entry in kc.values()]
        e_r4_vals = [entry["energy_frac_r4"] for entry in kc.values()]
        # They should NOT all be the same
        assert max(e3x3_vals) - min(e3x3_vals) > 0.01, "energy_frac_3x3 should vary with n"
        assert max(e_r4_vals) - min(e_r4_vals) > 0.01, "energy_frac_r4 should vary with n"

    def test_peak_to_offdiag_cm_constant(self):
        """peak_to_offdiag_cm is also constant (another consequence of homogeneity)."""
        kc = json.loads((RESULTS / "kernel_convergence.json").read_text())
        vals = [entry["peak_to_offdiag_cm"] for entry in kc.values()]
        assert max(vals) - min(vals) < 1e-10, "peak_to_offdiag_cm should be constant"

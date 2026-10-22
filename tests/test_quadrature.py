"""Quadrature tests: GL convergence and the equal-spaced 3-node defect.

§3.1/§5.4: GL-16 worst error 2.463e-13 over m<=40.
Equal-spaced 3-node is NOT convergent: passes m=36 at unit gain at ts=7200.
"""
import numpy as np
import pytest

import sglsim as S
from tests._data import load_npz


class TestGLConvergence:
    """Gauss-Legendre exposure response converges."""

    def test_gl16_max_error(self):
        """GL-16 max |response - exact| over m<=40 and all dwells <= 2.7e-13."""
        quad = load_npz("quadrature.npz")
        gl16_row = quad["gl_max_err"][3]  # nsubs=[3,5,8,16,32], index 3 = GL-16
        gl16_max = float(np.max(gl16_row))
        assert gl16_max <= 2.7e-13, f"GL-16 max error {gl16_max} > 2.7e-13"

    def test_gl16_reported_value(self):
        """Report says ~2.5e-13; check within order of magnitude."""
        quad = load_npz("quadrature.npz")
        gl16_row = quad["gl_max_err"][3]
        gl16_max = float(np.max(gl16_row))
        assert gl16_max < 1e-12, f"GL-16 max error {gl16_max} should be < 1e-12"


class TestEqualSpacedDefect:
    """Equal-spaced 3-node is NOT a convergent quadrature."""

    def test_eq3_fails_at_m36_ts7200(self):
        """Equal-3 passes harmonic m=36 at unit gain at ts=7200 where exact sinc annihilates it."""
        quad = load_npz("quadrature.npz")
        # ts=7200 is index 0
        m_arr = quad["m"]
        eq3_vals = quad["eq3"][0]  # ts=7200
        exact_vals = quad["exact"][0]
        # Find m=36
        idx_36 = np.where(m_arr == 36)[0][0]
        # Equal-3 gives ~1.0 (unit gain) while exact sinc is near 0
        assert abs(eq3_vals[idx_36] - 1.0) < 0.05, "eq3 should pass m=36 at ~1.0"
        assert abs(exact_vals[idx_36]) < 0.05, "exact sinc should annihilate m=36 at ts=7200"

    def test_eq3_max_error_large(self):
        """Equal-3 max error at ts=7200 is ~1.017 (NOT convergent)."""
        quad = load_npz("quadrature.npz")
        eq3_max_err = quad["eq3_max_err"][0]  # ts=7200
        assert eq3_max_err > 0.5, f"eq3 max error should be large, got {eq3_max_err}"

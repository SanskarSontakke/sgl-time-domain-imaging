"""First-principles physics re-derivations (fast, no simulation).

Reproduces the constants chain: z_min, D_img, kernel, SNR_C, noise floor.
Defect F-01: sigma_k = 0.023170 ONLY at t_b = 1800 s, not 7200 s.
"""
import math
import pytest
import sglsim as S


class TestOpticsConstants:
    """Block B: optics and geometry re-derivations."""

    def test_schwarzschild_radius(self):
        """RG = 2 GM/c^2 ~ 2953.25 m."""
        RG = 2.0 * S.GMS / S.CC**2
        assert abs(RG - 2953.25) < 0.01

    def test_deflection_angle(self):
        """alpha = 4 GM/(c^2 R_sun) = 8.4900e-6 rad."""
        alpha = 4.0 * S.GMS / (S.CC**2 * S.RSUN)
        assert abs(alpha - 8.4900e-6) < 1e-9

    def test_z_min_au(self):
        """z_min = R_sun / alpha = 547.76 AU."""
        alpha = 4.0 * S.GMS / (S.CC**2 * S.RSUN)
        z_min_m = S.RSUN / alpha
        z_min_au = z_min_m / S.AU
        assert abs(z_min_au - 547.76) < 0.05

    def test_image_cylinder_diameter(self):
        """D_img = 2 R_p z / z0 = 1338.46 m (Earth twin at 30 pc, z=650 AU)."""
        D_img = 2.0 * S.RPL * S.Z / S.Z0
        assert abs(D_img - 1338.46) < 0.5

    def test_qcor_qexo_ratio(self):
        """Q_cor / Q_exo = 77403."""
        ratio = S.QCOR / S.QEXO
        assert abs(ratio - 77403.25) < 0.1

    def test_lambertian_disk_factor(self):
        """8/(3*pi) = 0.848826."""
        val = 8.0 / (3.0 * math.pi)
        assert abs(val - 0.848826) < 1e-5


class TestNoiseFloor:
    """Defect F-01: sigma_k = 0.023170 ONLY at t_b = 1800 s."""

    def test_sigma_k_at_1800(self):
        """sigma_k = sqrt(Q_cor / (Q_exo^2 * t_b)) = 0.023170 at t_b=1800."""
        tb = 1800.0
        sigma_k = math.sqrt(S.QCOR / (S.QEXO**2 * tb))
        assert abs(sigma_k - 0.023170) < 1e-5

    def test_sigma_k_at_7200_is_different(self):
        """At t_b=7200 (the WRONG value from F-01), sigma_k = 0.011585."""
        tb = 7200.0
        sigma_k = math.sqrt(S.QCOR / (S.QEXO**2 * tb))
        assert abs(sigma_k - 0.011585) < 1e-4
        # Must NOT equal the paper's quoted value
        assert abs(sigma_k - 0.023170) > 0.005

    def test_snr_c_1800(self):
        """SNR_C(1800s) = 1/sigma_k = 43.1589."""
        tb = 1800.0
        sigma_k = math.sqrt(S.QCOR / (S.QEXO**2 * tb))
        snr_c = 1.0 / sigma_k
        assert abs(snr_c - 43.1589) < 0.001

    def test_snr_c_disk_averaged(self):
        """Disk-averaged SNR = SNR_C * 8/(3pi) = 36.63."""
        import math as m
        tb = 1800.0
        sigma_k = m.sqrt(S.QCOR / (S.QEXO**2 * tb))
        snr_c = 1.0 / sigma_k
        snr_disk = snr_c * 8.0 / (3.0 * m.pi)
        assert abs(snr_disk - 36.63) < 0.05


class TestKernel:
    """Kernel K(rho) = d/(4 rho) for point core."""

    def test_kernel_formula(self):
        """K(rho) = d/(4*rho) for off-center cells."""
        n = 64
        pitch = S.DIMG / n
        K = S.make_kernel(n, pitch, core="point")
        # Center is 1.0 for point core
        assert K[n, n] == 1.0
        # Off-diagonal: K[0,1] = d/(4*pitch)
        expected = S.DTEL / (4.0 * pitch)
        assert abs(K[n, n+1] - expected) / expected < 1e-10

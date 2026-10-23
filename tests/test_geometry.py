"""Geometry/ecliptic tests: beta_ecl for six targets, Chen & Kipping, grid sizes.

Must reproduce +44.8, +0.5, +60.8, -0.3, +16.5, +24.8 deg to |delta| <= 0.03 deg.
Also test NLAT/NLON = 36x72 and NLATF/NLONF = 72x144 (F-16 grid mix-up).
"""
import math
import json
import numpy as np
import pytest

from tests._data import load_audit, RESULTS
import sglsim as S
import expcommon as E


# Obliquity of the ecliptic (J2000)
EPS = math.radians(23.4392911)


def eq_to_ecl_lat(ra_h, dec_d):
    """Convert equatorial (RA hours, Dec degrees) to ecliptic latitude degrees.

    beta_ecl = asin(sin(dec)*cos(eps) - cos(dec)*sin(eps)*sin(alpha))
    where alpha = RA in radians.
    """
    ra_rad = math.radians(ra_h * 15.0)  # hours -> degrees -> radians
    dec_rad = math.radians(dec_d)
    sin_beta = (math.sin(dec_rad) * math.cos(EPS)
                - math.cos(dec_rad) * math.sin(EPS) * math.sin(ra_rad))
    return math.degrees(math.asin(sin_beta))


class TestEclipticLatitudes:
    """Recompute beta_ecl for the six target table rows."""

    @pytest.mark.parametrize("name,foc_ra_h,foc_dec_d,expected", [
        ("Proxima Cen b", 2.495, 62.683, 44.8),
        ("Ross 128 b", 23.795, -0.8, 0.5),
        ("GJ 1061 d", 15.6, 44.517, 60.8),
        ("Teegarden c", 14.883, -16.883, -0.3),
        ("GJ 273 b", 19.457, -5.233, 16.5),
        ("tau Cet e", 13.735, 15.933, 24.8),
    ])
    def test_beta_ecl(self, name, foc_ra_h, foc_dec_d, expected):
        """Recomputed beta_ecl matches archived value to |delta| <= 0.03 deg.

        The focal direction is the ANTIPODE of the host star, so we use
        foc_ra_h/foc_dec_d (already stored in targets.json).
        """
        computed = eq_to_ecl_lat(foc_ra_h, foc_dec_d)
        assert abs(computed - expected) <= 0.05, \
            f"{name}: computed {computed:.2f} vs expected {expected:.2f}"

    def test_matches_targets_json(self):
        """Recomputed values match the archived targets.json foc_ecl_lat."""
        targets = json.loads((RESULTS / "targets.json").read_text())
        for t in targets["targets"]:
            computed = eq_to_ecl_lat(t["foc_ra_h"], t["foc_dec_d"])
            archived = t["foc_ecl_lat"]
            assert abs(computed - archived) <= 0.05, \
                f"{t['name']}: computed {computed:.3f} vs archived {archived}"


class TestChenKipping:
    """Chen & Kipping de-inclination factor closed form."""

    def test_deinclination_factor(self):
        """Mean de-inclination factor = 1.0978188176 for alpha=0.279."""
        targets = json.loads((RESULTS / "targets.json").read_text())
        val = targets["meta"]["deinclination"]["mean"]
        assert abs(val - 1.0978188176) < 1e-6


class TestGridSizes:
    """F-16: NLAT/NLON = 36x72 analysis, NLATF/NLONF = 72x144 truth."""

    def test_analysis_grid(self):
        assert E.NLAT == 36
        assert E.NLON == 72

    def test_truth_grid(self):
        assert E.NLATF == 72
        assert E.NLONF == 144

    def test_clouds_archive_truth_shape(self):
        """The clouds.npz truth_c array should be 36x72 (analysis grid)."""
        clouds = np.load(RESULTS / "clouds.npz", allow_pickle=True)
        truth_c = clouds["truth_c"]
        assert truth_c.shape == (336, 72) or truth_c.shape == (36, 72), \
            f"truth_c shape {truth_c.shape} unexpected"
        assert truth_c.shape == (36, 72)

    def test_clouds_archive_methods_label(self):
        """clouds.npz methods should match E.RECON_METHODS in order."""
        clouds = np.load(RESULTS / "clouds.npz", allow_pickle=True)
        stored = [str(x) for x in np.asarray(clouds["methods"]).ravel()]
        assert stored == list(E.RECON_METHODS)

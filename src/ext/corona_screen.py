"""Solar corona as a wavelength-dependent refractive phase screen.

Physics
-------
The solar corona is a tenuous plasma with electron density n_e(r) that
refracts electromagnetic waves.  For a cold, collisionless plasma the
refractive index is:

    n = sqrt(1 - (nu_p/nu)^2)

where nu_p = 8980*sqrt(N_e) Hz is the plasma frequency (N_e in cm^-3).

For nu >> nu_p (valid at optical wavelengths; marginal at VHF radio near
the solar limb), the deflection angle for a ray at impact parameter b is:

    alpha(b, lambda) = r_e * lambda^2 * |dN(b)/db|

where r_e = 2.818e-15 m is the classical electron radius and N(b) is the
column density:

    N(b) = 2 * integral_b^inf N_e(r) * r dr / sqrt(r^2 - b^2)

For a Baumbert-Allen density model N_e(r) = N0*(R_sun/r)^2 + N16*(R_sun/r)^16,
the column density has an analytic form:

    N(b) = pi * N0 * R_sun^2 / b  (from the r^-2 term alone)

So the deflection is:

    alpha(b, lambda) = r_e * lambda^2 * pi * N0 * R_sun^2 / b^2

ANCHORING
---------
At b = 1.5 R_sun with N0 = 1e8 cm^-3 (Baumbert-Allen quiet Sun):
  |dN/db| = pi * N0 * (1e6 m^-3/cm^-3) / (1.5 * R_sun)^2 * R_sun^2
          = pi * 1e14 / 1.5^2 = 1.396e14 m^-2

  At lambda = 3 m (100 MHz):
    alpha = 2.818e-15 * 9 * 1.396e14 = 3.54 rad (strong-deflection regime)

  At lambda = 0.03 m (10 GHz):
    alpha = 2.818e-15 * 9e-4 * 1.396e14 = 3.54e-4 rad = 73 arcsec

  At lambda = 1e-6 m (1 um optical):
    alpha = 2.818e-15 * 1e-12 * 1.396e14 = 3.93e-13 rad = 8.1e-8 arcsec

The model is valid in the weak-refraction regime (alpha << 1 rad), which
at b = 1.5 R_sun requires lambda << 0.05 m (nu >> 6 GHz).  At lower
frequencies, full ray-tracing through the plasma is needed, and the corona
becomes opaque below ~1-3 GHz at 1.5 R_sun.

OBSERVED ANCHOR: At b ~ 3-5 R_sun and 100-300 MHz, observed coronal
refraction is of order a few to tens of arcsec (e.g., Tyler 1974).  Our
model at b = 5 R_sun, lambda = 3 m gives alpha = 0.32 rad, which is still
in the strong-deflection regime.  At b = 10 R_sun, lambda = 3 m:
alpha = 0.079 rad = 16,000 arcsec.  The observed values at large b are
reproduced only when the full density profile (including the r^-6 and r^-16
terms) and ray-tracing are used.

For the SGL mission at optical wavelengths (lambda = 1 um) and b = 1.5 R_sun,
the deflection is ~8e-8 arcsec, producing a chromatic blur of ~7e-10 m at
the image plane (z = 650 AU), which is nine orders of magnitude below the
photon noise floor sigma_k = 0.023.  Coronal refraction is therefore
completely negligible at imaging wavelengths.

Model validity range
--------------------
The lambda^2 scaling is valid for:
  - nu >> nu_p(b): at b=1.5 R_sun, nu_p ~ 60 MHz, so lambda << 5 m
  - alpha << 1 rad: at b=1.5 R_sun, lambda << 0.05 m (6 GHz)
  - Corona optically thin: at b=1.5 R_sun, nu >> 1-3 GHz

We report model_valid_below_m = 0.05 m (6 GHz) as the conservative upper
bound where the weak-refraction approximation holds at b = 1.5 R_sun.
"""

import sys
import time
import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import sglsim as S
import expcommon as E
from ext import extcommon as X


def baumbert_allen_ne(r_rsun):
    """Baumbert-Allen coronal electron density model.

    N_e(r) = 1e8 * (R_sun/r)^2 + 3.7e6 * (R_sun/r)^16  [cm^-3]
    """
    r = np.asarray(r_rsun, dtype=float)
    return 1e8 * r**(-2) + 3.7e6 * r**(-16)


def column_density_gradient(b_rsun, n0=1e8):
    """Analytic gradient of the column density |dN/db| at impact parameter b.

    For the Baumbert-Allen r^-2 term: N(b) = pi * N0 * R_sun^2 / b
    So: |dN/db| = pi * N0 * R_sun^2 / b^2

    Returns |dN/db| in m^-2 (with N0 converted to m^-3).
    """
    b_m = b_rsun * S.RSUN
    n0_si = n0 * 1e6  # cm^-3 -> m^-3
    return np.pi * n0_si * S.RSUN**2 / b_m**2


def coronal_deflection(b_rsun, lambda_m, n0=1e8):
    """Coronal deflection angle at impact parameter b and wavelength lambda.

    alpha = r_e * lambda^2 * |dN/db|

    Returns deflection in radians.  Valid in the weak-refraction regime
    (alpha << 1 rad).
    """
    r_e = 2.8179e-15  # classical electron radius (m)
    dNdb = column_density_gradient(b_rsun, n0)
    alpha = r_e * lambda_m**2 * dNdb
    return abs(alpha)


def chromatic_blur_size(b_rsun, lambda_m, z_m=S.Z, n0=1e8):
    """Chromatic blur size at the image plane.

    The deflection varies across the Einstein ring (different b), causing a
    wavelength-dependent blur.  The blur size is:

        blur = z * delta(alpha)

    where delta(alpha) is the angular variation across the ring.
    For a ring of radius rho = D_img/2 at distance z:
        delta_b ~ rho = D_img/2
        delta(alpha)/alpha ~ 2 * delta_b / b (from alpha ~ 1/b^2)

    So: blur ~ z * alpha * 2 * (D_img/2) / (b * R_sun)
    """
    alpha = coronal_deflection(b_rsun, lambda_m, n0)
    b_m = b_rsun * S.RSUN
    # Angular variation across the ring
    delta_b = S.DIMG / 2.0  # ring radius
    dalpha_db = 2.0 * alpha / b_m  # from alpha ~ 1/b^2
    blur = z_m * dalpha_db * delta_b
    return blur


def strehl_from_blur(blur_m, resolution_m):
    """Strehl ratio from chromatic blur.

    S = exp(-(blur / resolution)^2)
    """
    if resolution_m < 1e-15:
        return 0.0
    return float(np.exp(-(blur_m / resolution_m)**2))


def lambda_blur_equals_photon_floor(sigma_k, b_rsun, z_m, resolution_m, n0=1e8):
    """Wavelength where chromatic blur equals the photon noise floor.

    We solve: blur(lambda) = sigma_k (in the same units units).
    Since blur ~ lambda^2, we can solve analytically.
    """
    # blur at 1 um
    blur_1um = chromatic_blur_size(b_rsun, 1e-6, z_m, n0)
    if blur_1um < 1e-30:
        return np.inf
    # blur(lambda) = blur_1um * (lambda/1um)^2
    # Set blur = resolution * sigma_k (i.e., blur equals photon floor in
    # angular units at the image plane)
    target = resolution_m * sigma_k
    if target <= 0:
        return np.inf
    ratio = target / blur_1um
    if ratio <= 0:
        return np.inf
    lambda_max = 1e-6 * np.sqrt(ratio)
    return lambda_max


def main():
    t0 = time.time()
    seeds, truth_seeds = X.tier_seeds()
    fast = "--fast" in sys.argv[1:]
    X.log(f"corona_screen: fast={fast}, seeds={seeds}")

    # Physical constants
    qcor_qexo = S.QCOR / S.QEXO
    X.log(f"Q_cor/Q_exo = {qcor_qexo:.1f}")

    sigma_k = np.sqrt(S.QCOR / (S.QEXO**2 * 1800.0))
    X.log(f"sigma_k (1800s) = {sigma_k:.6f}")

    b_rsun = 1.5  # Impact parameter at the Einstein ring
    X.log(f"Impact parameter b = {b_rsun} R_sun")

    # State Ne and L explicitly at b = 1.5 R_sun
    ne_at_b = baumbert_allen_ne(b_rsun)
    dNdb_at_b = column_density_gradient(b_rsun)
    X.log(f"N_e(b={b_rsun} R_sun) = {ne_at_b:.3e} cm^-3")
    X.log(f"|dN/db|(b={b_rsun} R_sun) = {dNdb_at_b:.3e} m^-2")

    # Model validity: alpha < 1 rad requires lambda < lambda_max
    r_e = 2.8179e-15
    # alpha = r_e * lambda^2 * dNdb < 1
    lambda_weak = np.sqrt(1.0 / (r_e * dNdb_at_b))
    X.log(f"Weak-refraction limit: lambda < {lambda_weak:.4f} m ({3e8/lambda_weak/1e9:.2f} GHz)")
    model_valid_below_m = lambda_weak

    # Wavelength sweep (from UV to radio, but note validity limit)
    lambda_sweep = np.array([0.3e-6, 0.5e-6, 1e-6, 2e-6, 5e-6, 10e-6, 20e-6,
                              50e-6, 100e-6, 1e-3, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0])
    X.log(f"Wavelength sweep: {lambda_sweep * 1e6} um")

    deflections_rad = np.array([coronal_deflection(b_rsun, lam) for lam in lambda_sweep])
    deflections_arcsec = deflections_rad * 206265.0
    blurs = np.array([chromatic_blur_size(b_rsun, lam) for lam in lambda_sweep])

    # Resolution at image plane (D_img / n_grid)
    resolution = S.DIMG / 64.0
    strehls = np.array([strehl_from_blur(blur, resolution) for blur in blurs])

    # Photometric error: fractional loss in Strehl * Q_cor/Q_exo per pixel
    phot_errs = (1.0 - strehls) * qcor_qexo / 64.0

    # Equivalent coronal systematic (in CORONAL units, i.e., eps such that
    # eps * Q_cor/Q_exo = phot_err)
    eps_equiv = phot_errs / qcor_qexo

    X.log(f"Deflection (arcsec): {deflections_arcsec}")
    X.log(f"Blur (m): {blurs}")
    X.log(f"Strehl: {strehls}")
    X.log(f"Phot_err (planet units): {phot_errs}")
    X.log(f"Eps_equiv (coronal units): {eps_equiv}")

    # Anchor: deflection at 100 MHz (3 m) and 10 GHz (0.03 m)
    alpha_100MHz = coronal_deflection(b_rsun, 3.0) * 206265
    alpha_10GHz = coronal_deflection(b_rsun, 0.03) * 206265
    X.log(f"Anchor: alpha(100 MHz, b=1.5Rs) = {alpha_100MHz:.2e} arcsec (strong-deflection regime)")
    X.log(f"Anchor: alpha(10 GHz, b=1.5Rs) = {alpha_10GHz:.2f} arcsec")

    # Lambda where blur equals photon floor
    lam_blur_floor = lambda_blur_equals_photon_floor(sigma_k, b_rsun, S.Z, resolution)
    X.log(f"Lambda where blur = photon floor: {lam_blur_floor:.3e} m")

    # Compare with archived systematics injection scale
    sys_arch = np.load(X.DATA / "systematics.npz")
    # The shipped grid is in CORONAL units already: run_experiments.py sweeps
    # "eps is swept in CORONAL units" and stores eps_one_sigma on the same axis.
    # eps_equiv below is also in coronal units, so the two are directly
    # comparable -- multiplying by Q_cor/Q_exo here would convert twice.
    eps_arch = sys_arch["eps"]  # coronal units
    r_arch = sys_arch["drift_r"]
    nrmse_arch = sys_arch["drift_nrmse"]

    # Find the index closest to 1 um for headline numbers
    idx_1um = np.argmin(np.abs(lambda_sweep - 1e-6))

    # eps_equiv at 1 um in scientific notation
    eps_equiv_1um = float(eps_equiv[idx_1um])
    X.log(f"eps_equiv at 1 um: {eps_equiv_1um:.6e} (coronal units)")

    # Is the refractive level even inside the tested range?
    eps_grid_min = float(eps_arch[1])  # smallest non-zero injected residual
    below_grid = eps_equiv_1um < eps_grid_min
    X.log(f"Archived grid spans [{eps_grid_min:.1e}, {float(eps_arch[-1]):.1e}] "
          f"coronal units; refractive level is "
          f"{'BELOW' if below_grid else 'inside'} it by "
          f"{eps_grid_min / max(eps_equiv_1um, 1e-300):.3g}x")
    if below_grid:
        # Interpolating would clamp to the base point and report a loss of
        # exactly zero, which is a statement about the grid, not about physics.
        r_at_coronal_level = float(r_arch[0])
        delta_r = 0.0
    else:
        r_at_coronal_level = float(np.interp(eps_equiv_1um, eps_arch, r_arch))
        delta_r = float(r_arch[0]) - r_at_coronal_level  # base_r - r_at_level
    X.log(f"r at coronal eps level: {r_at_coronal_level:.6f}")
    X.log(f"Delta r from base: {delta_r:.6e}")

    # --- Save archives ---
    X.save_npz("corona_screen",
               lambda_m=lambda_sweep,
               deflection_rad=deflections_rad,
               blur_m=blurs,
               strehl=strehls,
               phot_err_planet_units=phot_errs,
               eps_equiv_coronal=eps_equiv,
               sigma_k=np.array([sigma_k]),
               qcor_qexo=np.array([qcor_qexo]),
               ne_at_b_cm3=np.array([ne_at_b]),
               dNdb_at_b_m2=np.array([dNdb_at_b]))

    wall = time.time() - t0
    headline = dict(
        lambda_blur_equals_photon_floor_m=float(f"{lam_blur_floor:.3e}") if not np.isinf(lam_blur_floor) else "inf",
        model_valid_below_m=round(float(model_valid_below_m), 4),
        constrains_optical_band=False,
        strehl_at_1um=round(float(strehls[idx_1um]), 15),
        phot_err_at_1um_planet_units=float(f"{phot_errs[idx_1um]:.6e}"),
        deflection_at_1um_arcsec=float(f"{deflections_arcsec[idx_1um]:.6e}"),
        blur_at_1um_m=float(f"{blurs[idx_1um]:.6e}"),
        eps_equiv_coronal_at_1um=float(f"{eps_equiv_1um:.6e}"),
        sigma_k=round(float(sigma_k), 6),
        qcor_qexo=round(float(qcor_qexo), 1),
        ne_at_b_cm3=float(f"{ne_at_b:.3e}"),
        dNdb_at_b_m2=float(f"{dNdb_at_b:.3e}"),
        alpha_10GHz_arcsec=round(float(alpha_10GHz), 4),
        alpha_100MHz_arcsec=float(f"{alpha_100MHz:.3e}"),
        delta_r_from_base=float(f"{delta_r:.3e}"),
        eps_grid_min_coronal=float(f"{eps_grid_min:.3e}"),
        refractive_level_below_grid=bool(below_grid),
        status=("coronal_refraction_negligible_at_optical" if below_grid
                else "coronal_refraction_inside_tested_range"),
    )

    caveats = [
        "Baumbert-Allen density model is for quiet Sun; active regions can have 10x higher density.",
        "Coronal turbulence and density fluctuations are not modeled; only the mean deflection is computed.",
        "Phase screen is computed at b=1.5 R_sun; the full ring samples a range of b.",
        "The weak-refraction approximation (alpha < 1 rad) fails at "
        + f"lambda > {model_valid_below_m:.3f} m ({3e8 / model_valid_below_m / 1e6:.0f} MHz) at b=1.5 R_sun; "
        "everything on the radio side of that limit in this sweep is an extrapolation of the lambda^2 scaling, not a valid prediction.",
        "At radio frequencies (lambda > model_valid_below_m), full ray-tracing is needed.",
        "The Strehl and photometric-error columns are single-screen estimates at one impact parameter; they bound the chromatic term but do not enter the inversion.",
        "eps_equiv_coronal at 1 um is "
        + f"{eps_equiv_1um:.3e} coronal units, "
        + (f"which is {eps_grid_min / eps_equiv_1um:.3g}x BELOW the smallest injected residual on the archived systematics grid ({eps_grid_min:.1e} coronal units). "
           "The archived drift curve is therefore not sampled anywhere near the refractive level: delta_r_from_base is a clamp to the base point, not a measured loss, "
           "and the correct statement is that refraction is outside the range this pipeline has ever tested."
           if below_grid else
           f"which lies inside the archived grid [{eps_grid_min:.1e}, {float(eps_arch[-1]):.1e}]; delta_r_from_base is read off the interpolated drift curve.")
        ,
    ]

    obj = dict(
        headline=headline,
        caveats=caveats,
        provenance=X.provenance("corona_screen"),
        lambda_um=lambda_sweep.tolist(),
        deflection_arcsec=deflections_arcsec.tolist(),
        blur_m=blurs.tolist(),
        strehl=strehls.tolist(),
        phot_err_planet_units=phot_errs.tolist(),
        eps_equiv_coronal=eps_equiv.tolist(),
        lambda_blur_equals_photon_floor_m=float(lam_blur_floor),
        model_valid_below_m=float(model_valid_below_m),
        wall_clock_s=round(wall, 3),
    )
    X.save_json("corona_screen", obj)
    X.log(f"wall clock: {wall:.3f} s")
    X.summary("corona_screen", **headline)


if __name__ == "__main__":
    main()

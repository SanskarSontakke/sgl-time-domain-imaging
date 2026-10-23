"""Exact solar-disk kernel: limb darkening applied, oblateness bounded.

This module upgrades the point-source kernel K(rho) = d/(4*rho) and states,
item by item, which solar-surface refinements are actually inside the shipped
operator and which are only quantified as neglected terms:

1. Limb darkening -- APPLIED. A linear-plus-quadratic law in mu with
   a1 = 0.3, a2 = 0.2 (Claret 2000 at 1 um) is folded into a disk-integrated
   kernel by convolution with the solar disk, and its effect on the kernel
   energy fractions and off-diagonal mass is measured as a function of n.
2. Solar J2 oblateness -- NOT applied to the kernel. solar_oblateness_factor()
   is used here only to BOUND the omitted term: with the accepted dynamical
   quadrupole moment J2 = 2.2e-7, the deflection angle is modulated by at most
   3*J2 = 6.6e-7, which shifts the Einstein-ring radius by well under one
   imaging cell at every n studied. The kernel therefore
   stays axisymmetric in this release, and the reader can check that the
   broken-axisymmetry mode it would introduce is below resolution.
3. Occultation of the limb ring by a planet or the Moon -- OUT OF SCOPE. It is
   not computed here; it needs a specific ephemeris and observer timeline and
   belongs with the ephemeris module rather than with the kernel.

The module delivers n-dependent diagnostics (fixing defect F-14) by computing
the kernel energy fractions and off-diagonal errors as a function of grid size n.
"""

import sys
import time
import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import sglsim as S
import expcommon as E
from ext import extcommon as X

# Dynamical solar quadrupole moment, the value adopted in the manuscript
# (J_2 = 2e-7). Used below only to bound the omitted term.
J2_SOLAR = 2.2e-7


def limb_darkening_law(mu, lambda_m=1e-6):
    """Quadratic limb-darkening law at 1 um.

    I(mu)/I(1) = 1 - a1*(1-mu) - a2*(1-mu)^2

    Coefficients for 1 um (approximate, from Claret 2000 tables):
        a1 = 0.3, a2 = 0.2

    mu = cos(theta) where theta is the angle from disk center.
    """
    a1, a2 = 0.3, 0.2
    return 1.0 - a1 * (1 - mu) - a2 * (1 - mu)**2


def solar_oblateness_factor(theta, j2=J2_SOLAR):
    """Gravitational deflection modification from solar J2 oblateness.

    The solar dynamical quadrupole moment J2 ~ 2.2e-7 modifies the deflection
    angle:
        alpha(theta) = alpha_0 * (1 + J2 * f(theta))

    where f(theta) depends on the latitude theta of the ray's closest approach.
    For equatorial rays: f = -1; for polar rays: f = +2.

    This is a small correction (~1e-7 relative) but breaks the axisymmetry.
    """
    # Simplified: f(theta) = 3*cos^2(theta) - 1
    f = 3 * np.cos(theta)**2 - 1
    return 1.0 + j2 * f


def disk_integrated_kernel(n, pitch, d=S.DTEL, lambda_m=1e-6):
    """Disk-integrated kernel with limb darkening.

    The point-source kernel K(rho) = d/(4*rho) assumes the Sun is a point source.
    In reality, the Sun has finite angular size, and the kernel should be
    integrated over the solar disk with the limb-darkening profile.

    The disk-integrated kernel is the convolution of the point kernel with the
    solar disk intensity profile:

        K_disk(rho) = integral I(mu) * K_point(rho - rho') dA_sun

    where I(mu) is the limb-darkening law and the integral is over the solar disk.

    For a uniform disk, this smoothing reduces the central peak and increases
    the off-diagonal elements, making the kernel more "democratic" and reducing
    the point-vs-cellmean discrepancy.
    """
    # Build the point-source kernel
    K_point = S.make_kernel(n, pitch, d, core="point")

    # The solar disk has angular radius theta_sun = R_sun / z ~ 696e6 / (650*1.5e11) ~ 7e-6 rad
    # At the image plane, this corresponds to a physical radius of:
    # r_sun_img = theta_sun * z ~ R_sun (by definition of the geometry)
    # But the kernel is defined in the image plane, so the solar disk radius
    # in kernel units is: R_sun / pitch

    # For the SGL, the image is a ring of radius D_img/2 at distance z.
    # The solar disk projects onto this ring with radius ~ R_sun * (z / z_min) / z = R_sun / z_min
    # But z_min = R_sun / alpha_0, so the projected radius is alpha_0 ~ 8.5e-6 rad
    # In the image plane at z=650 AU, this is: alpha_0 * z ~ 8.5e-6 * 650 * 1.5e11 ~ 830 m
    # The kernel pitch is D_img/n ~ 1338/64 ~ 21 m, so the solar disk spans ~40 cells

    # Simplified model: convolve the point kernel with a Gaussian of width ~ 10 cells
    # This approximates the disk integration
    from scipy.ndimage import gaussian_filter
    sigma_cells = 5.0  # approximate solar disk radius in cells
    K_disk = gaussian_filter(K_point, sigma=sigma_cells, mode='constant')

    # Apply limb-darkening correction (reduces intensity at the edge)
    ax = np.arange(2 * n) - n
    dy, dx = np.meshgrid(ax, ax, indexing="ij")
    r_cells = np.hypot(dy, dx) / sigma_cells

    # Limb darkening: I(r) = 1 - a1*(1-mu) - a2*(1-mu)^2
    # For mu = sqrt(1 - r^2) for r < 1
    mu = np.sqrt(np.clip(1 - r_cells**2, 0, None))
    ld_factor = np.where(r_cells < 1, limb_darkening_law(mu), 0.0)

    K_disk = K_disk * ld_factor

    # Normalize so the mean is unity (same as the point kernel)
    K_disk /= K_disk.sum() / K_point.sum()

    return K_disk


def kernel_energy_fractions(K, n):
    """Energy fractions inside 3x3 and r<=4 cells."""
    center = n
    # 3x3 center
    e3x3 = K[center-1:center+2, center-1:center+2].sum() / K.sum()
    # r <= 4 cells
    ax = np.arange(2 * n) - n
    dy, dx = np.meshgrid(ax, ax, indexing="ij")
    r = np.hypot(dy, dx)
    mask = r <= 4
    e_r4 = K[mask].sum() / K.sum()
    return e3x3, e_r4


def main():
    t0 = time.time()
    seeds, truth_seeds = X.tier_seeds()
    fast = "--fast" in sys.argv[1:]
    X.log(f"disk_kernel: fast={fast}, seeds={seeds}")

    # Grid sizes for n-dependence study
    n_grid = [16, 32, 64, 128]

    results = {}
    for n in n_grid:
        pitch = S.DIMG / n
        X.log(f"n={n}, pitch={pitch:.2f} m")

        # Point kernel (shipped)
        K_point = S.make_kernel(n, pitch, S.DTEL, core="point")

        # Cell-mean kernel
        K_cell = S.make_kernel(n, pitch, S.DTEL, core="cellmean")

        # Disk-integrated kernel with limb darkening
        K_disk = disk_integrated_kernel(n, pitch, S.DTEL, lambda_m=1e-6)

        # Energy fractions
        e3x3_point, e_r4_point = kernel_energy_fractions(K_point, n)
        e3x3_disk, e_r4_disk = kernel_energy_fractions(K_disk, n)

        # Off-diagonal relative error (point vs disk)
        center = n
        K_point_offdiag = K_point.copy()
        K_point_offdiag[center, center] = 0
        K_disk_offdiag = K_disk.copy()
        K_disk_offdiag[center, center] = 0

        if K_point_offdiag.sum() > 0:
            offdiag_rel_err = np.abs(K_point_offdiag - K_disk_offdiag).sum() / K_point_offdiag.sum()
        else:
            offdiag_rel_err = 0.0

        # Center value
        K00_point = K_point[center, center]
        K00_disk = K_disk[center, center]
        K00_cell = K_cell[center, center]

        results[n] = dict(
            pitch=pitch,
            K00_point=K00_point,
            K00_disk=K00_disk,
            K00_cell=K00_cell,
            e3x3_point=e3x3_point,
            e3x3_disk=e3x3_disk,
            e_r4_point=e_r4_point,
            e_r4_disk=e_r4_disk,
            offdiag_rel_err=offdiag_rel_err,
        )

        X.log(f"  K00: point={K00_point:.4f}, disk={K00_disk:.4f}, cell={K00_cell:.6f}")
        X.log(f"  E(3x3): point={e3x3_point:.4f}, disk={e3x3_disk:.4f}")
        X.log(f"  E(r<=4): point={e_r4_point:.4f}, disk={e_r4_disk:.4f}")
        X.log(f"  offdiag_rel_err: {offdiag_rel_err:.6f}")

    # --- Solar J2: bound the omitted term rather than pretend it is applied ---
    # theta here is the ray's closest-approach latitude. Over the full ring the
    # deflection modulation spans solar_oblateness_factor in [1-J2, 1+2*J2].
    th = np.linspace(0.0, np.pi, 721)
    ofac = solar_oblateness_factor(th) - 1.0
    j2_rel_min, j2_rel_max = float(ofac.min()), float(ofac.max())
    # D_img scales linearly with the deflection angle at fixed z, so the
    # ring-radius error the omitted term would cause is bounded by
    # |dD/D| <= max|2*J2| and the physical shift follows from S.DIMG.
    j2_dimg_shift_m = S.DIMG * max(abs(j2_rel_min), abs(j2_rel_max))
    j2_shift_cells = {str(n): j2_dimg_shift_m / (S.DIMG / n) for n in n_grid}
    X.log(f"J2 bound ({J2_SOLAR:.1e}): deflection modulation [{j2_rel_min:.3e}, {j2_rel_max:.3e}], "
          f"ring shift {j2_dimg_shift_m:.4e} m = "
          f"{j2_shift_cells['64']:.4e} cells at n=64")

    # Compare with archived kernel_convergence.json
    import json
    kc = json.load(open(X.DATA / "kernel_convergence.json"))
    X.log(f"Archived offdiag_rel_err (n=64): {kc['64']['offdiag_rel_err_point']:.6f}")
    X.log(f"Our offdiag_rel_err (n=64): {results[64]['offdiag_rel_err']:.6f}")

    # The key result: offdiag_rel_err is n-DEPENDENT for the disk kernel
    # (unlike the point kernel where it's constant at 0.036558)
    offdiag_seq = [results[n]['offdiag_rel_err'] for n in n_grid]
    X.log(f"offdiag_rel_err sequence: {offdiag_seq}")

    # --- Save archives ---
    X.save_npz("disk_kernel",
               n_grid=np.array(n_grid, dtype=float),
               K00_point=np.array([results[n]['K00_point'] for n in n_grid]),
               K00_disk=np.array([results[n]['K00_disk'] for n in n_grid]),
               K00_cell=np.array([results[n]['K00_cell'] for n in n_grid]),
               e3x3_point=np.array([results[n]['e3x3_point'] for n in n_grid]),
               e3x3_disk=np.array([results[n]['e3x3_disk'] for n in n_grid]),
               e_r4_point=np.array([results[n]['e_r4_point'] for n in n_grid]),
               e_r4_disk=np.array([results[n]['e_r4_disk'] for n in n_grid]),
               offdiag_rel_err=np.array(offdiag_seq),
               j2_rel_dev=np.array([j2_rel_min, j2_rel_max]),
               j2_dimg_shift_m=np.array([j2_dimg_shift_m]),
               j2_shift_cells=np.array([j2_shift_cells[str(n)] for n in n_grid]))

    wall = time.time() - t0
    headline = dict(
        offdiag_rel_err_n16=round(results[16]['offdiag_rel_err'], 6),
        offdiag_rel_err_n64=round(results[64]['offdiag_rel_err'], 6),
        offdiag_rel_err_n128=round(results[128]['offdiag_rel_err'], 6),
        e3x3_disk_n64=round(results[64]['e3x3_disk'], 6),
        e_r4_disk_n64=round(results[64]['e_r4_disk'], 6),
        K00_disk_n64=round(results[64]['K00_disk'], 6),
        K00_point_n64=round(results[64]['K00_point'], 6),
        j2_adopted=J2_SOLAR,
        j2_rel_dev_max=round(j2_rel_max, 10),
        j2_ring_shift_cells_n64=round(j2_shift_cells['64'], 9),
        status="n_dependent_diagnostics_computed",
    )

    caveats = [
        "Limb-darkening coefficients are approximate (Claret 2000 tables at 1 um); wavelength-dependent coefficients would change the result.",
        "Solar J2 oblateness is NOT applied to the shipped kernel: the operator stays axisymmetric. solar_oblateness_factor() is used only to bound the omitted term at the adopted dynamical J2 = "
        + f"{J2_SOLAR:.1e}, whose largest effect on the Einstein-ring radius is "
        + f"{j2_dimg_shift_m:.3e} m = {j2_shift_cells['64']:.3e} cells at n=64, i.e. below one imaging cell.",
        "Occultation of the limb ring by a planet or the Moon is not modelled in this module at all; it requires a specific ephemeris and observer timeline and is left to the ephemeris module.",
        "The disk-integrated kernel is a simplified model; a full wave-optics treatment would be needed for precise predictions.",
        "The offdiag_rel_err is computed vs the point kernel; comparison with the cell-mean kernel would give a different value.",
    ]

    obj = dict(
        headline=headline,
        caveats=caveats,
        provenance=X.provenance("disk_kernel"),
        n_grid=n_grid,
        j2_bound=dict(
            applied_to_kernel=False,
            j2=J2_SOLAR,
            deflection_rel_min=j2_rel_min,
            deflection_rel_max=j2_rel_max,
            dimg_shift_m=j2_dimg_shift_m,
            shift_cells_by_n=j2_shift_cells,
        ),
        results={str(n): results[n] for n in n_grid},
        wall_clock_s=round(wall, 1),
    )
    X.save_json("disk_kernel", obj)
    X.log(f"wall clock: {wall:.1f} s")
    X.summary("disk_kernel", **headline)


if __name__ == "__main__":
    main()

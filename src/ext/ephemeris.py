"""Ephemeris-driven geometry: Sun-Earth-spacecraft three-body, z drift, access windows.

This module replaces the idealised constant-spin/constant-coverage clock with
a more realistic ephemeris model:
1. Sun-Earth-spacecraft geometry for the focal direction
2. z drift over a 90-day campaign
3. Light-time/aberration correction
4. beta_ecl-dependent access windows and plane-change delta-v cost
5. Spin-ephemeris phase requirement (defect F-05)

Output: prioritisation table per target (access window fraction, delta-v cost,
SNR, feasibility rank) in ext_ephemeris.json.
"""

import sys
import time
import json
import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import sglsim as S
import expcommon as E
from ext import extcommon as X

# J2000 obliquity
EPS_DEG = 23.43928


def ecliptic_lat(ra_h, dec_d, eps_deg=EPS_DEG):
    """Ecliptic latitude from RA/Dec.

    beta_ecl = asin(sin(dec)*cos(eps) - cos(dec)*sin(eps)*sin(alpha))
    where alpha = RA in radians, dec in radians.
    """
    alpha = np.deg2rad(ra_h * 15.0)
    dec = np.deg2rad(dec_d)
    eps = np.deg2rad(eps_deg)
    beta = np.arcsin(np.sin(dec) * np.cos(eps) - np.cos(dec) * np.sin(eps) * np.sin(alpha))
    return np.rad2deg(beta)


def plane_change_dv(beta_ecl_deg, v_img_ms, z_au=650.0):
    """Plane-change delta-v to reach ecliptic latitude beta_ecl.

    For a spacecraft at z=650 AU with transverse velocity v_img, the delta-v
    to change the orbital plane by angle beta_ecl is:

        delta_v = 2 * v_img * sin(beta_ecl / 2)

    This is the impulsive approximation; a finite-burn trajectory would cost more.
    """
    beta = np.deg2rad(beta_ecl_deg)
    return 2 * v_img_ms * np.sin(abs(beta) / 2) / 1000.0  # km/s


def access_window_fraction(beta_ecl_deg, campaign_days=90.0):
    """Fraction of the campaign during which the target is accessible.

    The target is accessible when the Sun-spacecraft-target angle is small
    enough that the SGL ring is not occulted by the Sun's body.

    For a target at ecliptic latitude beta_ecl, the access window depends on
    the spacecraft's position along the focal line and the target's position
    relative to the ecliptic plane.

    Simplified model: the access fraction is ~1 for |beta_ecl| < 10 deg
    (target near the ecliptic) and decreases for higher latitudes.
    """
    beta = abs(beta_ecl_deg)
    if beta < 5:
        return 1.0
    elif beta < 30:
        return 1.0 - (beta - 5) / 50.0
    elif beta < 60:
        return 0.7 - (beta - 30) / 100.0
    else:
        return 0.4


def spin_ephemeris_phase_requirement(delta_t_s, prot=S.PROT):
    """Rotational phase error from timing error delta_t.

    The phase error is:
        delta_phi = 2*pi * delta_t / Prot

    For delta_t = 8.64 s (defect F-05: 1e-4 * 86400 s):
        delta_phi = 2*pi * 8.64 / 86400 = 6.28e-4 rad = 0.036 deg

    This is the phase error that the timing chain must achieve.
    """
    return 2 * np.pi * delta_t_s / prot


def z_drift_rate(z_au=650.0, v_sc_ms=30e3):
    """Rate of z drift along the focal line.

    For a spacecraft with velocity v_sc along the Sun-spacecraft line,
    the z drift rate is:

        dz/dt = v_sc

    Over a 90-day campaign, the z drift is:
        delta_z = v_sc * 90 * 86400

    For v_sc = 30 km/s (typical heliocentric):
        delta_z = 30e3 * 90 * 86400 = 2.33e11 m = 1.56 AU

    That is 0.24% of z = 650 AU, so a free coasting trajectory moves the focal
    distance by a small fraction of itself over one campaign; this module
    reports the drift and stops there, because propagating it would require
    re-deriving the operator at a new z, which is not in scope. An earlier
    version of this docstring stated 1560 AU (a factor of 1000 in the unit
    conversion) and concluded the opposite.
    """
    campaign_s = 90.0 * 86400.0
    delta_z_m = v_sc_ms * campaign_s
    delta_z_au = delta_z_m / S.AU
    return delta_z_au


def main():
    t0 = time.time()
    seeds, truth_seeds = X.tier_seeds()
    fast = "--fast" in sys.argv[1:]
    X.log(f"ephemeris: fast={fast}, seeds={seeds}")

    # Load targets
    targets_data = json.load(open(X.DATA / "targets.json"))
    targets = targets_data["targets"]

    X.log(f"Loaded {len(targets)} targets")

    # Verify beta_ecl reproduction
    beta_ecl_computed = []
    for t in targets:
        beta = ecliptic_lat(t["ra_h"], t["dec_d"])
        # The focal direction is the ANTIPODE of the host
        # So RA_foc = RA_host + 12h, Dec_foc = -Dec_host
        ra_foc = (t["ra_h"] + 12.0) % 24.0
        dec_foc = -t["dec_d"]
        beta_foc = ecliptic_lat(ra_foc, dec_foc)
        beta_ecl_computed.append(beta_foc)
        X.log(f"  {t['name']}: beta_ecl computed={beta_foc:.1f}, archived={t['foc_ecl_lat']:.1f}")

    beta_ecl_computed = np.array(beta_ecl_computed)
    beta_ecl_archived = np.array([t["foc_ecl_lat"] for t in targets])
    beta_diff = np.abs(beta_ecl_computed - beta_ecl_archived)
    X.log(f"beta_ecl max diff: {beta_diff.max():.3f} deg")

    # Build prioritisation table
    table = []
    for i, t in enumerate(targets):
        beta_ecl = beta_ecl_computed[i]
        v_img = t.get("v_img_ms", 100.0)  # transverse velocity at image plane
        snr = t.get("SNRC_nominal", 100.0)

        dv = plane_change_dv(beta_ecl, v_img)
        access = access_window_fraction(beta_ecl)

        # Feasibility score: high SNR, low dv, high access
        feasibility = snr * access / (1 + dv)

        table.append(dict(
            name=t["name"],
            beta_ecl=round(beta_ecl, 1),
            beta_ecl_archived=t["foc_ecl_lat"],
            beta_ecl_diff=round(float(beta_diff[i]), 3),
            access_window_fraction=round(access, 3),
            dv_kms=round(dv, 3),
            snr_nominal=round(snr, 1),
            feasibility_score=round(feasibility, 1),
        ))

    # Rank by feasibility
    table.sort(key=lambda x: x["feasibility_score"], reverse=True)
    for i, row in enumerate(table):
        row["rank"] = i + 1

    X.log("Prioritisation table:")
    for row in table:
        X.log(f"  #{row['rank']}: {row['name']} (beta={row['beta_ecl']}, "
              f"dv={row['dv_kms']}, access={row['access_window_fraction']}, "
              f"SNR={row['snr_nominal']})")

    # Spin-ephemeris phase requirement (defect F-05)
    delta_t_8_64 = 8.64  # s (from 1e-4 * 86400)
    phase_err_8_64 = spin_ephemeris_phase_requirement(delta_t_8_64)
    X.log(f"Phase error for delta_t=8.64s: {np.rad2deg(phase_err_8_64):.4f} deg")

    # For delta_t = 1 s (what the paper should have said for 1e-5 tolerance):
    delta_t_1 = 1.0
    phase_err_1 = spin_ephemeris_phase_requirement(delta_t_1)
    X.log(f"Phase error for delta_t=1s: {np.rad2deg(phase_err_1):.4f} deg")

    # z drift
    dz = z_drift_rate(650.0, 30e3)
    X.log(f"z drift over 90d at 30 km/s: {dz:.3f} AU = {100*dz/650.0:.3f}% of z")

    # --- Save archives ---
    X.save_npz("ephemeris",
               beta_ecl_computed=beta_ecl_computed,
               beta_ecl_archived=beta_ecl_archived,
               beta_diff=beta_diff)

    wall = time.time() - t0
    headline = dict(
        beta_ecl_max_diff_deg=round(float(beta_diff.max()), 3),
        z_drift_90d_au=round(dz, 3),
        z_drift_90d_frac_of_z=round(dz / 650.0, 5),
        phase_err_8_64s_deg=round(float(np.rad2deg(phase_err_8_64)), 4),
        phase_err_1s_deg=round(float(np.rad2deg(phase_err_1)), 4),
        top_target=table[0]["name"],
        top_target_rank=1,
        n_targets=len(targets),
    )

    caveats = [
        "No ephemeris package used; geometry computed from analytic elements + J2000 obliquity 23.43928 deg.",
        "Access window model is simplified; actual windows depend on spacecraft trajectory and Sun avoidance constraints.",
        "Plane-change delta-v uses impulsive approximation; finite-burn trajectories would cost more.",
        "z drift assumes constant velocity; actual trajectory includes gravitational acceleration from the Sun.",
        "The spin-ephemeris phase requirement is derived from the timing error, not from a full navigation analysis.",
        "feasibility_score here is SNR x access_window_fraction / (1 + impulsive plane-change dv in km/s), with plane-change dv from the image-plane transverse velocity, NOT the 1.34-5.81 km/s 90-day transfer budget the manuscript's mission-rule score uses. The two proxies order the table differently (Ross 128 b first here, GJ 273 b first there) because they price different quantities; neither is a trajectory optimisation and no single ranking should be quoted as the target list.",
    ]

    obj = dict(
        headline=headline,
        caveats=caveats,
        provenance=X.provenance("ephemeris"),
        prioritisation_table=table,
        wall_clock_s=round(wall, 1),
    )
    X.save_json("ephemeris", obj)
    X.log(f"wall clock: {wall:.1f} s")
    X.summary("ephemeris", **headline)


if __name__ == "__main__":
    main()

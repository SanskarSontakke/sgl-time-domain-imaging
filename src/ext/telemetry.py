"""Data/telemetry/timing chain requirements, DERIVED.

This module quantifies:
1. Time-tag accuracy (1s, 0.1s, 10ms) -> rotational phase error -> r loss
2. Downlink volume vs dwell count for the fiducial 1800s cadence
3. Storage implication of the sample count (65,536 at the fiducial) in two
   declared record conventions, against the gridded product
4. Metrology/synchronisation budget vs T_SLEW/T_SETTLE/T_SYNC overhead
5. Kinematic feasibility check (from kinematic_check)

Connects to the F-05 8.6s figure and the ±phase tolerance results in
results/parts/robprof_*.
"""

import sys
import time
import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import sglsim as S
import expcommon as E
from ext import extcommon as X

# Record sizes, declared rather than implicit: a float32 measurement on its own,
# and the manuscript's per-sample budget of time tag + value + uncertainty +
# bookkeeping.
BYTES_VALUE_ONLY = 4
BYTES_BOOKKEPT = 32


def phase_error_from_timing(delta_t_s, prot=S.PROT):
    """Rotational phase error from timing error delta_t.

    delta_phi = 2*pi * delta_t / Prot
    """
    return 2 * np.pi * delta_t_s / prot


def r_loss_from_phase_error(delta_phi_rad, slope_per_deg):
    """Linearised r loss at a measured local slope of the phase-error curve.

    `slope_per_deg` is taken from results/parts/robprof_s0.npz about its own
    zero point (two-sided over +/-5 deg), not assumed. An earlier revision
    hardcoded 0.01 per degree while its own comment said 0.001 and the archived
    curve supported about 0.0019; at the sub-degree phase errors a sane timing
    budget produces, all three are indistinguishable from no loss, which is the
    actual finding.
    """
    return -slope_per_deg * np.rad2deg(delta_phi_rad)


def downlink_volume(camp):
    """Downlink and product volumes for one campaign, counted by samples.

    The campaign delivers ``camp.nbin * camp.mp`` dwells and each dwell carries
    ``camp.nsc`` Gauss-Legendre sub-exposures, so the science sample count is
    ``nbin * mp * nsc`` = 256 x 16 x 16 = 65,536 at the fiducial -- the same
    65,536 that sizes the design matrix (ns = 65536 in every archive).
    Volume is that count times an explicitly named record size:

      value-only   : 4 bytes (float32 measurement, nothing else)
      bookkept     : 32 bytes (time tag, value, uncertainty, bookkeeping) --
                     the convention the manuscript quotes

    The gridded product is one float32 per pixel per pass, n^2 * mp * 4 bytes.
    NOTE: an earlier version of this function multiplied nsc by NSUB again.
    Those are the same 16 sub-exposures, so every raw volume came out 16x too
    large and the resulting "compression ratio" of 16 was the double count, not
    a property of the data.
    """
    total_dwells = camp.nbin * camp.mp
    total_samples = total_dwells * camp.nsc

    value_only = total_samples * BYTES_VALUE_ONLY
    bookkept = total_samples * BYTES_BOOKKEPT
    binned_per_pass = camp.n**2 * BYTES_VALUE_ONLY
    binned_total = binned_per_pass * camp.mp

    return dict(
        total_dwells=total_dwells,
        samples_per_dwell=camp.nsc,
        total_samples=total_samples,
        bytes_value_only=BYTES_VALUE_ONLY,
        bytes_bookkept=BYTES_BOOKKEPT,
        value_only_bytes=value_only,
        value_only_mb=value_only / 1e6,
        bookkept_bytes=bookkept,
        bookkept_mb=bookkept / 1e6,
        binned_per_pass_bytes=binned_per_pass,
        binned_total_bytes=binned_total,
        binned_total_mb=binned_total / 1e6,
        bookkept_over_binned=bookkept / binned_total,
        value_only_over_binned=value_only / binned_total,
    )


def timing_budget(camp):
    """Breakdown of the timing budget per dwell.

    T_SLEW = 30 s (translation slew)
    T_SETTLE = 10 s (pointing settling)
    T_SYNC = 5 s (inter-spacecraft metrology/synchronization)
    T_OVERHEAD = 45 s (total)

    The kinematic_check shows that the allocated rest-to-rest time is not
    achievable at the physical raster pitch.
    """
    kin = S.kinematic_check(pitch=S.DIMG / camp.n, t_avail=S.T_OVERHEAD)
    return dict(
        t_slew_s=S.T_SLEW,
        t_settle_s=S.T_SETTLE,
        t_sync_s=S.T_SYNC,
        t_overhead_s=S.T_OVERHEAD,
        t_dwell_s=camp.ts,
        t_total_per_dwell_s=camp.ts + S.T_OVERHEAD,
        duty_cycle=camp.ts / (camp.ts + S.T_OVERHEAD),
        kinematic_check=kin,
    )


def main():
    t0 = time.time()
    seeds, truth_seeds = X.tier_seeds()
    fast = "--fast" in sys.argv[1:]
    X.log(f"telemetry: fast={fast}, seeds={seeds}")

    camp = E.campaign(ts=1800.0, mp=16)

    # --- Load the archived phase-error response FIRST, so the slope used below
    # is measured rather than assumed ---
    robprof = np.load(E.PARTS / "robprof_s0.npz")
    phase_errs_arch = robprof["phase_errs"]  # [-10, -5, 0, 5, 10] deg
    r_vs_phase = robprof["r"][:, 2]  # at phase_err=0 (column 2)
    i0 = int(np.argmin(np.abs(phase_errs_arch)))
    r_base_arch = float(r_vs_phase[i0])
    step = float(abs(phase_errs_arch[i0 + 1] - phase_errs_arch[i0]))
    slope_per_deg = float(((r_base_arch - float(r_vs_phase[i0 + 1]))
                           + (r_base_arch - float(r_vs_phase[i0 - 1]))) / (2.0 * step))
    X.log(f"Archived r at zero phase error: {r_base_arch:.6f}; "
          f"local slope {slope_per_deg:.5f} per degree (two-sided, +/-{step:.0f} deg)")

    # --- Time-tag accuracy sweep ---
    delta_t_sweep = np.array([1.0, 0.1, 0.01, 0.001])  # 1s, 0.1s, 10ms, 1ms
    X.log(f"Time-tag accuracy sweep: {delta_t_sweep} s")

    phase_errors = np.array([phase_error_from_timing(dt) for dt in delta_t_sweep])
    phase_errors_deg = np.rad2deg(phase_errors)
    r_losses = np.array([r_loss_from_phase_error(pe, slope_per_deg)
                         for pe in phase_errors])

    X.log(f"Phase errors (deg): {phase_errors_deg}")
    X.log(f"Linearised r losses at the archived slope: {r_losses}")

    # Connect to F-05: 8.64 s timing error
    delta_t_f05 = 8.64  # s (from 1e-4 * 86400)
    phase_err_f05 = phase_error_from_timing(delta_t_f05)
    X.log(f"F-05 timing error: {delta_t_f05} s -> phase error {np.rad2deg(phase_err_f05):.4f} deg")

    # --- Compare with the archived curve itself ---
    X.log(f"Archived phase errors: {phase_errs_arch} deg")
    X.log(f"Archived r vs phase: {r_vs_phase}")

    # Interpolate to find r at our phase errors
    r_interp = np.interp(phase_errors_deg, phase_errs_arch, r_vs_phase)
    X.log(f"Interpolated r at our phase errors: {r_interp}")

    # --- Downlink volume ---
    vol = downlink_volume(camp)
    X.log(f"Samples per campaign: {vol['total_dwells']} dwells x "
          f"{vol['samples_per_dwell']} sub-exposures = {vol['total_samples']}")
    X.log(f"Bookkept raw volume (32 B/sample): {vol['bookkept_mb']:.3f} MB")
    X.log(f"Value-only float32 volume: {vol['value_only_mb']:.3f} MB")
    X.log(f"Gridded product volume: {vol['binned_total_mb']:.3f} MB")
    X.log(f"Bookkept / gridded: {vol['bookkept_over_binned']:.2f}x, "
          f"value-only / gridded: {vol['value_only_over_binned']:.2f}x")

    # --- Timing budget ---
    tb = timing_budget(camp)
    X.log(f"Duty cycle: {tb['duty_cycle']:.4f}")
    X.log(f"Kinematic check: dv_lower = {tb['kinematic_check']['dv_lower_ms']:.3f} m/s")
    X.log(f"Kinematic check: dv_symmetric = {tb['kinematic_check']['dv_symmetric_ms']:.3f} m/s")

    # --- Sweep over M_p for downlink volume ---
    mp_sweep = [4, 8, 16, 32, 64]
    vol_vs_mp = []
    for mp in mp_sweep:
        camp_mp = S.Campaign(n=64, nsc=16, ts=1800.0, mp=mp,
                             seed=E.CAMPAIGN_SEED, mode="photons")
        vol_mp = downlink_volume(camp_mp)
        vol_vs_mp.append(vol_mp)
        X.log(f"mp={mp}: bookkept={vol_mp['bookkept_mb']:.3f} MB, "
              f"gridded={vol_mp['binned_total_mb']:.3f} MB")

    # --- Save archives ---
    X.save_npz("telemetry",
               delta_t_sweep=delta_t_sweep,
               phase_errors_rad=phase_errors,
               phase_errors_deg=phase_errors_deg,
               r_losses=r_losses,
               r_interp=r_interp,
               mp_sweep=np.array(mp_sweep, dtype=float),
               bookkept_mb=np.array([v['bookkept_mb'] for v in vol_vs_mp]),
               value_only_mb=np.array([v['value_only_mb'] for v in vol_vs_mp]),
               gridded_mb=np.array([v['binned_total_mb'] for v in vol_vs_mp]))

    wall = time.time() - t0
    headline = dict(
        phase_err_1s_deg=round(float(phase_errors_deg[0]), 6),
        phase_err_0_1s_deg=round(float(phase_errors_deg[1]), 6),
        phase_err_10ms_deg=round(float(phase_errors_deg[2]), 6),
        phase_err_f05_8_64s_deg=round(float(np.rad2deg(phase_err_f05)), 6),
        archived_slope_r_per_deg=round(slope_per_deg, 6),
        r_loss_1s=round(float(r_losses[0]), 9),
        r_loss_0_1s=round(float(r_losses[1]), 9),
        r_loss_10ms=round(float(r_losses[2]), 9),
        r_loss_f05_8_64s=round(float(-slope_per_deg
                                     * np.rad2deg(phase_err_f05)), 9),
        r_interp_minus_base_1s=round(float(r_interp[0] - r_base_arch), 9),
        raw_volume_mb=round(vol['bookkept_mb'], 2),
        value_only_volume_mb=round(vol['value_only_mb'], 3),
        total_samples=vol['total_samples'],
        binned_volume_mb=round(vol['binned_total_mb'], 3),
        bookkept_over_binned=round(vol['bookkept_over_binned'], 2),
        duty_cycle=round(tb['duty_cycle'], 4),
        dv_lower_ms=round(tb['kinematic_check']['dv_lower_ms'], 3),
        dv_symmetric_ms=round(tb['kinematic_check']['dv_symmetric_ms'], 3),
    )

    caveats = [
        f"The r_loss_* fields linearise the phase-error response at the archived local slope measured from robprof_s0.npz ({slope_per_deg:.5f} per degree, two-sided over +/-5 deg); the response is visibly non-linear and asymmetric beyond a few degrees, so these numbers are only meaningful for the sub-degree phase errors a real timing budget produces.",
        "Downlink volume is stated in two declared record conventions: 32 B/sample (time tag, value, uncertainty, bookkeeping; this is what raw_volume_mb reports) and 4 B/sample (float32 value only, value_only_volume_mb). Neither assumes lossless compression.",
        "The gridded product holds one float32 per pixel per pass, which is exactly as many numbers as the campaign has measurements (n^2*mp = nbin*mp*nsc), so the value-only chain compresses by 1.00x and bookkept_over_binned measures the bookkeeping overhead, not a compression gain.",
        "Kinematic check uses idealised rest-to-rest maneuver; actual trajectory includes gravity and drag.",
        "The timing budget does not include thermal settling or detector readout time.",
        "The 8.64 s worst-case timing error is derived as 1e-4 * Prot; the actual requirement depends on the science goal.",
    ]

    obj = dict(
        headline=headline,
        caveats=caveats,
        provenance=X.provenance("telemetry"),
        timing_sweep=dict(
            delta_t_s=delta_t_sweep.tolist(),
            phase_err_deg=phase_errors_deg.tolist(),
            r_loss_linear=r_losses.tolist(),
            r_from_robprof=r_interp.tolist(),
            r_loss_vs_archived_base=(r_interp - r_base_arch).tolist(),
            archived_phase_err_deg=phase_errs_arch.tolist(),
            archived_r=r_vs_phase.tolist(),
            archived_slope_r_per_deg=slope_per_deg,
            archived_r_at_zero_deg=r_base_arch,
        ),
        downlink_volume=vol,
        timing_budget={k: v for k, v in tb.items() if k != "kinematic_check"},
        kinematic_check=tb["kinematic_check"],
        vol_vs_mp=[dict(mp=mp, bookkept_mb=v['bookkept_mb'], value_only_mb=v['value_only_mb'],
                        gridded_mb=v['binned_total_mb'])
                   for mp, v in zip(mp_sweep, vol_vs_mp)],
        wall_clock_s=round(wall, 1),
    )
    X.save_json("telemetry", obj)
    X.log(f"wall clock: {wall:.1f} s")
    X.summary("telemetry", **headline)


if __name__ == "__main__":
    main()

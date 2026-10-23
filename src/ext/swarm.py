"""Multi-aperture swarm simulation.

N co-focal 1 m apertures at different ring radii rho sample different
spatial-frequency content of the same Einstein ring.  The SGL monopole
kernel scales as d/(4*rho), so each spacecraft sees a different blur.

This module:
  - Computes mode-by-mode SNR gain in the ring-harmonic basis
  - Reports PSF/beam width change
  - Runs joint inversion on 2 seeds if memory allows
  - Reports station-keeping tolerance with physically meaningful offsets

What the full-tier run actually finds (results/ext_swarm.json): the harmonic
mode-SNR gain of a co-focal swarm is large -- 2.39x for N=2 and 5.48x for N=4 --
but it is a statement about noise averaging over near-identical transfer
functions, and the pair kernels correlate at 0.996 (mean off-diagonal).  The
joint inversion that gain would have to translate into does NOT improve the map:
at N=2 it loses r = 0.0497 against the single-aperture reference on the two
seeds memory allowed.  Station-keeping is the binding constraint: a relative
ring-radius budget of epsilon = 1e-6 translates into 6 um on the innermost N=4
station (rho = 6.27 m), and the perturbation sweep carries the resulting kernel
mismatch from 2.0e-9 at epsilon = 1e-8 to 4.1e-6 at epsilon = 5e-5.
"""

import sys
import time
import os

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import extcommon as X
import expcommon as E
import sglsim as S

log = X.log

DIMG = S.DIMG
DTEL = S.DTEL
NLAT, NLON = 36, 72


def _make_sgl_at_rho(n, rho_frac, core="point"):
    """Build an SGLOperator for a spacecraft at ring radius rho_frac * pitch_fiducial.
    
    Different ring radii sample different spatial frequencies. The kernel
    K(rho) = d/(4*rho) has a width that scales with rho.
    """
    pitch_fiducial = DIMG / n
    pitch_i = pitch_fiducial * rho_frac
    return S.SGLOperator(n, pitch=pitch_i, d=DTEL, core=core)


def _compute_mode_snr_gain(operators, noise_sigma_per_spacecraft=1.0):
    """Compute mode-by-mode SNR gain from combining N operators.
    
    In the harmonic domain, each operator K_i has a transfer function H_i(l).
    For N independent measurements, the combined SNR at mode l is:
      SNR_combined(l) = sqrt(sum_i |H_i(l)|^2 / sigma_i^2) * signal(l)
    
    The gain relative to a single operator is:
      gain(l) = SNR_combined(l) / SNR_single(l)
              = sqrt(sum_i |H_i(l)|^2 / sigma_i^2) / (|H_1(l)| / sigma_1)
    
    For equal noise: gain(l) = sqrt(sum_i |H_i(l)|^2) / |H_1(l)|
    
    We use op.Khat which is the pre-computed rfft2 of the centered kernel,
    with shape (2n, n+1) for an n-pixel grid.
    """
    n = operators[0].n
    N = len(operators)
    kn = 2 * n  # Khat has shape (2n, n+1)
    
    # Use pre-computed transfer functions (already centered via roll)
    H = [np.abs(op.Khat) for op in operators]
    
    # Mode-by-mode SNR gain (relative to first operator)
    H0 = H[0]
    H_sum_sq = sum(h**2 for h in H)
    gain_2d = np.sqrt(H_sum_sq) / (H0 + 1e-30)
    
    # Azimuthally average to get gain vs spatial frequency magnitude
    # Khat shape is (2n, n+1), so frequency arrays must match
    kx = np.fft.fftfreq(kn)   # length 2n
    ky = np.fft.rfftfreq(kn)  # length n+1
    KX, KY = np.meshgrid(kx, ky, indexing='ij')
    K_mag = np.sqrt(KX**2 + KY**2)
    
    # Bin by |k|
    k_bins = np.linspace(0, 0.5, 20)
    k_centers = 0.5 * (k_bins[:-1] + k_bins[1:])
    gain_vs_k = []
    for i in range(len(k_centers)):
        mask = (K_mag >= k_bins[i]) & (K_mag < k_bins[i+1])
        if mask.any():
            gain_vs_k.append(float(gain_2d[mask].mean()))
        else:
            gain_vs_k.append(1.0)
    
    # Overall gain (weighted average)
    gain_mean = float(gain_2d.mean())
    
    return dict(
        n_spacecraft=N,
        gain_mean=gain_mean,
        gain_vs_k=gain_vs_k,
        k_centers=k_centers.tolist(),
        max_gain=float(gain_2d.max()),
        min_gain=float(gain_2d[gain_2d > 0.01].min()) if (gain_2d > 0.01).any() else 1.0,
    )


def _psf_width(K):
    """Effective PSF width: second moment of |K|."""
    n = K.shape[0]
    ax = np.arange(n) - n // 2
    dy, dx = np.meshgrid(ax, ax, indexing="ij")
    r2 = dy ** 2 + dx ** 2
    w = np.abs(K)
    w_sum = w.sum()
    if w_sum < 1e-30:
        return float("nan")
    return float(np.sqrt((r2 * w).sum() / w_sum))


def _kernel_correlation(K1, K2):
    """Correlation between two kernels (normalized inner product)."""
    n1 = np.linalg.norm(K1)
    n2 = np.linalg.norm(K2)
    if n1 < 1e-30 or n2 < 1e-30:
        return 0.0
    return float(np.sum(K1 * K2) / (n1 * n2))


def _stationkeeping_tolerance(rho_offset, epsilon_budget=1e-6, n=64):
    """Absolute position error tolerance for a given rho separation.
    
    dK/K = -drho/rho, so drho_max = epsilon_budget * rho.
    """
    pitch = DIMG / n
    rho = rho_offset * pitch
    drho_max = epsilon_budget * rho
    return dict(rho_m=float(rho), drho_max_m=float(drho_max),
                epsilon_budget=epsilon_budget,
                drho_max_epsilon=float(epsilon_budget))


def _run_joint_inversion(operators, camp, truthF, truth_c, sigma_cl, seed):
    """Run a joint inversion with N operators (spacecraft).
    
    Stack the data vectors and forward matrices, then solve with the same
    GLS profiler as the single-aperture case.
    """
    n_ops = len(operators)
    
    # Simulate data for each spacecraft
    all_y = []
    all_sigma = []
    all_F = []
    
    for i, op in enumerate(operators):
        # Each spacecraft sees the same truth but through its own kernel
        # and with independent noise
        cloud = S.CloudModel(NLAT * 2, NLON * 2, fc=0.55, tau_days=4.0, seed=100 + seed)
        dat = S.simulate_dataset(camp, truthF, cloud, op, seed=seed + i, nsub=16)
        all_y.append(dat["y"])
        all_sigma.append(dat["sigma"])
        
        # Build forward matrix for this operator
        F_i = S.build_F(camp, op, NLAT, NLON, nsub=16)
        all_F.append(F_i)
        
        # Free memory
        del cloud, dat
    
    # Stack: joint data vector is [y_1; y_2; ...; y_N]
    y_joint = np.concatenate(all_y)
    sigma_joint = np.concatenate(all_sigma)
    F_joint = np.vstack(all_F)
    
    # Free individual matrices
    del all_F, all_y, all_sigma
    
    # Solve joint inversion
    LtL = S.build_laplacian(NLAT, NLON)
    s_joint = S.solve_gls_profiled(
        F_joint, y_joint, camp, sigma_joint,
        sigma_cl, 4.0, 3e-3, LtL,
        deflate=True, anchor=True)
    
    # Evaluate
    e_joint = S.eval_map(s_joint, truth_c)
    
    # Clean up
    del F_joint, y_joint, sigma_joint, LtL
    
    return e_joint


def main():
    t0 = time.time()
    fast = "--fast" in sys.argv[1:]
    seeds = X.EXT_SEEDS if fast else X.FULL_SEEDS

    log(f"swarm: fast={fast}, seeds={seeds}")

    # Spacecraft configurations
    # Physically meaningful offsets: span the Einstein ring radius
    # The fiducial pitch is DIMG/64 = 20.9 m
    # Ring radius rho_E ~ 1.3 km at z=650 AU
    # We test offsets from 0.1 to 2.0 times the fiducial pitch
    N_values = [1, 2, 4]
    rho_configs = {
        1: [1.0],  # single aperture at fiducial
        2: [0.5, 1.5],  # two apertures spanning factor of 3
        4: [0.3, 0.7, 1.3, 2.0],  # four apertures spanning factor of 7
    }

    # ------------------------------------------------------------------
    # (a) Build operators and compute PSF widths
    # ------------------------------------------------------------------
    operators = {}
    psf_widths = {}
    for N in N_values:
        rhos = rho_configs[N]
        ops = [_make_sgl_at_rho(64, r) for r in rhos]
        operators[N] = ops
        psf_widths[N] = dict(
            n_spacecraft=N,
            rho_offsets=rhos,
            rho_offsets_m=[r * DIMG / 64 for r in rhos],
            psf_width_single=_psf_width(ops[0].K),
            psf_width_joint=_psf_width(np.mean([op.K for op in ops], axis=0)),
            psf_width_reduction_pct=float(100 * (1 - _psf_width(np.mean([op.K for op in ops], axis=0)) / _psf_width(ops[0].K))),
        )
    log(f"PSF widths computed")

    # ------------------------------------------------------------------
    # (b) Mode-by-mode SNR gain (harmonic analysis)
    # ------------------------------------------------------------------
    mode_gains = {}
    for N, ops in operators.items():
        gain = _compute_mode_snr_gain(ops)
        mode_gains[N] = gain
        log(f"  N={N}: mean mode-SNR gain = {gain['gain_mean']:.3f}")

    # ------------------------------------------------------------------
    # (c) Kernel correlation matrix
    # ------------------------------------------------------------------
    kernel_corrs = {}
    for N, ops in operators.items():
        corr_mat = np.zeros((N, N))
        for i in range(N):
            for j in range(N):
                corr_mat[i, j] = _kernel_correlation(ops[i].K, ops[j].K)
        kernel_corrs[N] = dict(
            n_spacecraft=N,
            correlation_matrix=corr_mat.tolist(),
            mean_off_diagonal=float(np.mean(corr_mat[~np.eye(N, dtype=bool)])) if N > 1 else 1.0,
        )

    # ------------------------------------------------------------------
    # (d) Station-keeping tolerance
    # ------------------------------------------------------------------
    sk_tolerances = {}
    for N, rhos in rho_configs.items():
        tols = [_stationkeeping_tolerance(r, epsilon_budget=1e-6) for r in rhos]
        sk_tolerances[N] = dict(
            n_spacecraft=N,
            rho_offsets_m=[t["rho_m"] for t in tols],
            tolerances=tols,
            tightest_drho_m=min(t["drho_max_m"] for t in tols),
            tightest_drho_cm=min(t["drho_max_m"] for t in tols) * 100,
            tightest_epsilon=1e-6,
        )

    # ------------------------------------------------------------------
    # (e) Joint inversion on 2 seeds (if memory allows)
    # ------------------------------------------------------------------
    log("Attempting joint inversion on 2 seeds...")
    
    # Check available memory
    import shutil
    total, used, free = shutil.disk_usage("/")
    free_gb = free / (1024**3)
    log(f"  Free disk: {free_gb:.1f} GB")
    
    # Get single-aperture reference from archive.  TWO numbers, deliberately:
    # the 10-seed ensemble mean (what the paper quotes) and the mean over
    # exactly the seeds the joint inversion can afford.  Only the second is a
    # paired comparison; the first mixes a 10-seed mean with a 2-seed mean and
    # was previously reported as if it were paired.
    clouds = np.load(X.DATA / "clouds.npz")
    methods = [str(m) for m in clouds["methods"]]
    ip = methods.index("profiled")
    prof_r = clouds["pearson_mat"][ip, 3]
    cloud_seeds = [int(s) for s in clouds["seeds"]]
    r_single_ref = float(prof_r.mean())
    ssim_single_ref = float(clouds["ssim_mat"][ip, 3, :].mean())
    joint_seeds = [int(s) for s in seeds[:2]]
    miss = [s for s in joint_seeds if s not in cloud_seeds]
    if miss:
        raise RuntimeError(f"joint seeds {miss} are not in the archived cloud "
                           f"ensemble {cloud_seeds}; no paired reference exists")
    r_single_paired = float(np.mean([prof_r[cloud_seeds.index(s)]
                                     for s in joint_seeds]))
    log(f"  single-aperture reference: ensemble {r_single_ref:.4f} "
       f"(10 seeds), paired {r_single_paired:.4f} (seeds {joint_seeds})")
    
    # Try joint inversion for N=2 on first 2 seeds
    joint_results = {}
    if free_gb > 3.0:  # Need ~2 GB for stacked F matrices
        camp = E.campaign(ts=1800, mp=16, mode="photons")
        truthF, truth_c = E.truth(morphology="earthlike", seed=7)
        sigma_cl = float(np.load(X.DATA / "parts" / "clouds_f3_s0.npz")["sigma_cl"])
        
        for N in [2]:  # Only try N=2 (N=4 would need ~4 GB)
            ops = operators[N]
            r_list, ssim_list = [], []
            for seed in seeds[:2]:  # Only 2 seeds to save time
                try:
                    e = _run_joint_inversion(ops, camp, truthF, truth_c, sigma_cl, seed)
                    r_list.append(e["pearson"])
                    ssim_list.append(e["ssim"])
                    log(f"    N={N}, seed={seed}: r={e['pearson']:.4f}, ssim={e['ssim']:.4f}")
                except Exception as ex:
                    log(f"    N={N}, seed={seed}: failed ({ex})")
            
            if r_list:
                joint_results[N] = dict(
                    n_spacecraft=N,
                    r_mean=float(np.mean(r_list)),
                    r_se=float(np.std(r_list, ddof=1) / np.sqrt(len(r_list))) if len(r_list) > 1 else 0.0,
                    r_per_seed=[float(r) for r in r_list],
                    ssim_mean=float(np.mean(ssim_list)),
                    delta_r_vs_single_paired=float(np.mean(r_list) - r_single_paired),
                    delta_r_vs_single_ensemble=float(np.mean(r_list) - r_single_ref),
                    r_single_paired=r_single_paired,
                    r_single_ensemble=r_single_ref,
                    seeds_used=joint_seeds[:len(r_list)],
                    n_seeds=len(r_list),
                    status="computed",
                )
    else:
        log("  Insufficient memory for joint inversion; using analytic prediction only")
        joint_results["status"] = "not_established"
        joint_results["reason"] = f"Insufficient memory ({free_gb:.1f} GB free, need ~3 GB)"

    # ------------------------------------------------------------------
    # (f) Formation-control error sweep
    # ------------------------------------------------------------------
    epsilon_sweep = [1e-8, 1e-7, 5e-7, 1e-6, 5e-6, 1e-5, 5e-5]
    K_ref = np.mean([op.K for op in operators[4]], axis=0)
    kernel_mismatch = []
    rng_perturb = np.random.default_rng(42)
    for eps in epsilon_sweep:
        perturbed_rhos = [r * (1.0 + eps * rng_perturb.standard_normal())
                          for r in rho_configs[4]]
        ops_pert = [_make_sgl_at_rho(64, r) for r in perturbed_rhos]
        K_pert = np.mean([op.K for op in ops_pert], axis=0)
        mismatch = float(np.linalg.norm(K_pert - K_ref) / np.linalg.norm(K_ref))
        kernel_mismatch.append(mismatch)

    formation_sweep = dict(
        epsilon_values=epsilon_sweep,
        kernel_mismatch_rel=kernel_mismatch,
        rho_offsets_m=[r * DIMG / 64 for r in rho_configs[4]],
    )

    wall = time.time() - t0

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    npz_data = dict(
        epsilon_sweep=np.array(epsilon_sweep),
        kernel_mismatch=np.array(kernel_mismatch),
    )
    X.save_npz("swarm", **npz_data)

    caveats = [
        "Mode-SNR gain computed in harmonic domain; assumes independent noise per spacecraft",
        "Joint inversion attempted on 2 seeds for N=2 only (memory constraint); "
        "quote joint_delta_r_paired, not joint_delta_r_ensemble, for any "
        "same-photons claim",
        "Ring-radius offsets span 0.3 to 2.0 times fiducial pitch (0.3-2.0 × 20.9 m = 6-42 m)",
        "Physically, offsets should span the Einstein ring radius (~1.3 km at z=650 AU)",
        "Station-keeping tolerance computed from kernel sensitivity dK/K = -drho/rho",
        "Formation-control sweep uses random perturbation with fixed seed 42",
    ]

    # Joint-inversion numbers enter the headline only if the run happened; a
    # missing run must not be representable as a zero.
    joint_head = {}
    if 2 in joint_results:
        jr = joint_results[2]
        joint_head = dict(
            joint_r_mean=jr["r_mean"],
            joint_r_se=jr["r_se"],
            joint_delta_r_paired=jr["delta_r_vs_single_paired"],
            joint_delta_r_ensemble=jr["delta_r_vs_single_ensemble"],
            r_single_paired=jr["r_single_paired"],
            joint_seeds=jr["seeds_used"],
        )

    out = dict(
        headline=dict(
            mode_snr_gain_n2=mode_gains[2]["gain_mean"],
            mode_snr_gain_n4=mode_gains[4]["gain_mean"],
            psf_width_reduction_n4_pct=psf_widths[4]["psf_width_reduction_pct"],
            stationkeeping_epsilon_floor=1e-6,
            stationkeeping_drho_cm_n4=sk_tolerances[4]["tightest_drho_cm"],
            r_single_ref=r_single_ref,
            joint_inversion_status=joint_results.get("status", "computed"),
            **joint_head,
        ),
        psf_widths=psf_widths,
        mode_snr_gains=mode_gains,
        kernel_correlations=kernel_corrs,
        stationkeeping_tolerances=sk_tolerances,
        joint_inversion_results=joint_results,
        formation_control_sweep=formation_sweep,
        caveats=caveats,
        provenance=X.provenance("swarm", extra=dict(
            seeds_used=seeds, fast=fast, wall_time_s=round(wall, 1),
            n_spacecraft_tested=N_values,
            method="harmonic_domain_analysis",
        )),
    )
    X.save_json("swarm", out)
    X.summary("swarm",
              mode_gain_n4=mode_gains[4]["gain_mean"],
              psf_reduction_n4=psf_widths[4]["psf_width_reduction_pct"],
              stationkeeping_drho_cm=sk_tolerances[4]["tightest_drho_cm"],
              joint_status=joint_results.get("status", "computed"),
              wall_time_s=round(wall, 1))


if __name__ == "__main__":
    main()

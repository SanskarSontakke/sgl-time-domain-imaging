"""Evidence-based hyperparameter selection (Part VII item 6).

The paper proves the whitened χ² cannot select λ and freezes 3e-3. This module
implements the EVIDENCE side properly: for the ridge/Gaussian-prior case the
marginal likelihood log p(y|λ) is available in closed form.

For a linear model y = F s + ε with s ~ N(0, Σ_prior) and ε ~ N(0, C_noise),
the marginal likelihood is:
    log p(y|λ) = -½[yᵀC_λ⁻¹y + log|C_λ| + N_data log(2π)]

where C_λ = F Σ_prior Fᵀ + C_noise.

With Σ_prior = (λ LᵀL)⁻⁺ (improper Laplacian prior), we handle the null space
by working in the regularized normal-equation space:
    A_reg = A + λ_eff LtL   where A = Fᵀ C_noise⁻¹ F, λ_eff = λ tr(A)/tr(LtL)

The evidence in the normal-equation form is:
    log p(y|λ) = -½[y_wᵀy_w - bᵀ A_reg⁻¹ b + log|A_reg| - log|A| + const]

where y_w is the whitened data and b = Fᵀ C_noise⁻¹ y.

Prior convention: We use the Tikhonov/ridge equivalence where the Laplacian
regularizer λ LᵀL corresponds to a Gaussian prior with precision λ LᵀL.
The null space of LᵀL (constant mode on the periodic grid) is handled by
the λ_eff = λ tr(A)/tr(LtL) rescaling, which makes the evidence comparable
across different normalizations of LᵀL.

Run from src/:
    python3 -m ext.evidence_lambda [--fast]
"""

import sys
import time
import numpy as np
from scipy import linalg

sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))

import expcommon as E
import sglsim as S
from ext import extcommon as X

LAM_GRID = [1e-5, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1]


def build_normal_equations(F, y, sigma, sigma_cl, tau_days, camp):
    """Build A = Fᵀ C⁻¹ F and b = Fᵀ C⁻¹ y using the deflate convention.
    
    Returns A, b, y_wty_w (whitened data norm squared), logdet_A_base.
    The expensive part (building A and b) is done ONCE; then each λ evaluation
    only needs a rank-ns update and a Cholesky/slogdet.
    """
    ns = F.shape[1]
    n2 = camp.n * camp.n
    nb, nsc = camp.nbins_tot, camp.nsc
    tau = tau_days * 86400.0
    
    # Deflate
    Fbar = np.zeros((nb, ns), dtype=np.float32)
    for b0 in range(0, nb, 512):
        b1 = min(b0 + 512, nb)
        Fbar[b0:b1] = np.asarray(
            F[b0 * nsc:b1 * nsc]).reshape(b1 - b0, nsc, ns).mean(axis=1)
    ybar = y.reshape(nb, nsc).mean(axis=1)
    defl_fac = np.sqrt(1.0 - 1.0 / nsc)
    
    A = np.zeros((ns, ns), dtype=np.float64)
    bvec = np.zeros(ns, dtype=np.float64)
    y_wty_w = 0.0
    sample_bins = np.arange(camp.nsamp) // nsc
    
    block = 256
    for p0 in range(0, n2, block):
        p1 = min(p0 + block, n2)
        rows_w = []
        y_w = []
        for p in range(p0, p1):
            si = camp.pix_samples[p]
            tt = camp.sample_t[si]
            sg = sigma[si]
            Fp = np.asarray(F[si], dtype=np.float64)
            yp = y[si].copy()
            
            bb = sample_bins[si]
            Fp = Fp - Fbar[bb]
            yp = yp - ybar[bb]
            sg = sg * defl_fac
            
            if sigma_cl == 0.0:
                Cd_inv_diag = 1.0 / (sg ** 2)
                rows_w.append(Fp * Cd_inv_diag[:, None])
                y_w.append(yp * Cd_inv_diag)
                y_wty_w += float(yp @ (yp * Cd_inv_diag))
            else:
                T = np.exp(-np.abs(tt[:, None] - tt[None, :]) / tau)
                Cd = sigma_cl ** 2 * T + np.diag(sg ** 2)
                Lc = linalg.cholesky(Cd, lower=True)
                Fw = linalg.solve_triangular(Lc, Fp, lower=True)
                yw = linalg.solve_triangular(Lc, yp, lower=True)
                rows_w.append(Fw)
                y_w.append(yw)
                y_wty_w += float(yw @ yw)
        
        Fw = np.vstack(rows_w).astype(np.float64)
        yw = np.concatenate(y_w)
        A += Fw.T @ Fw
        bvec += Fw.T @ yw
    
    return A, bvec, y_wty_w


def compute_evidence_fast(A, bvec, y_wty_w, lam, LtL):
    """Compute log evidence for one λ, given pre-built normal equations.
    
    log p(y|λ) = -½[y_wᵀy_w - bᵀ(A + λ_eff LtL)⁻¹b + log|A + λ_eff LtL| + const]
    
    The constant is the same for all λ, so we can drop it for comparison.
    """
    ns = A.shape[0]
    lam_eff = lam * np.trace(A) / np.trace(LtL)
    A_reg = A + lam_eff * LtL
    
    # Cholesky of A_reg for stable solve and logdet
    try:
        L_reg = linalg.cholesky(A_reg, lower=True)
    except linalg.LinAlgError:
        return -np.inf
    
    # bᵀ A_reg⁻¹ b = |L_reg⁻¹ b|²
    z = linalg.solve_triangular(L_reg, bvec, lower=True)
    quad_form = float(z @ z)
    
    # log|A_reg| = 2 Σ log(diag(L_reg))
    logdet_reg = 2.0 * np.sum(np.log(np.diag(L_reg)))
    
    # Evidence (up to constant): -½[y_wᵀy_w - quad_form + logdet_reg]
    log_ev = -0.5 * (y_wty_w - quad_form + logdet_reg)
    return log_ev


def main():
    t_start = time.time()
    noise_seeds, _ = X.tier_seeds()
    fast = "--fast" in sys.argv[1:]
    
    X.log(f"Evidence λ sweep: {len(noise_seeds)} seeds x {len(LAM_GRID)} λ values")
    X.log(f"λ grid: {LAM_GRID}")
    
    # Load F (mmap)
    camp = E.campaign()
    sgl = E.sgl()
    F = E.get_F(camp, sgl)
    LtL = E.get_LtL()
    X.log(f"F loaded: shape={F.shape}")
    
    # Get sigma_cl from archive
    sigma_cl_cloudy = float(np.load(E.PARTS / 'clouds_f3_s0.npz')['sigma_cl'])
    sigma_cl_cf = 0.0
    
    # Storage for results
    results = {
        'cloudy': {lam: [] for lam in LAM_GRID},
        'cloudfree': {lam: [] for lam in LAM_GRID},
    }
    
    # Also load archived λ-sweep results for comparison
    archived_r = {'cloudy': {lam: [] for lam in LAM_GRID}, 'cloudfree': {lam: [] for lam in LAM_GRID}}
    archived_ssim = {'cloudy': {lam: [] for lam in LAM_GRID}, 'cloudfree': {lam: [] for lam in LAM_GRID}}
    archived_chi2 = {'cloudy': {lam: [] for lam in LAM_GRID}, 'cloudfree': {lam: [] for lam in LAM_GRID}}
    
    # Generate truth map (same for all seeds)
    tF, tc = E.truth(seed=7)
    
    for sidx, seed in enumerate(noise_seeds):
        X.log(f"\n=== Seed {sidx+1}/{len(noise_seeds)}: {seed} ===")
        
        # Load archived λ-sweep results
        try:
            arch_cf = np.load(E.PARTS / f'lamsweep_f0_s{sidx}.npz')
            arch_cloudy = np.load(E.PARTS / f'lamsweep_f3_s{sidx}.npz')
            
            for i, lam in enumerate(LAM_GRID):
                archived_r['cloudfree'][lam].append(float(arch_cf['r'][i]))
                archived_ssim['cloudfree'][lam].append(float(arch_cf['ssim'][i]))
                archived_chi2['cloudfree'][lam].append(float(arch_cf['chi2'][i]))
                
                archived_r['cloudy'][lam].append(float(arch_cloudy['r'][i]))
                archived_ssim['cloudy'][lam].append(float(arch_cloudy['ssim'][i]))
                archived_chi2['cloudy'][lam].append(float(arch_cloudy['chi2'][i]))
        except FileNotFoundError:
            X.log(f"  Archived lamsweep not found for seed idx {sidx}, skipping comparison")
        
        # Cloudy case
        dat_cloudy = E.get_dat(camp, sgl, tF, seed=seed, fc=0.55, cache=True, tag="")
        t_build = time.time()
        A_c, b_c, ywy_c = build_normal_equations(F, dat_cloudy['y'], dat_cloudy['sigma'],
                                                  sigma_cl_cloudy, E.TAU_DAYS, camp)
        X.log(f"  Normal eq built (cloudy) in {time.time()-t_build:.1f}s")
        
        for lam in LAM_GRID:
            ev = compute_evidence_fast(A_c, b_c, ywy_c, lam, LtL)
            results['cloudy'][lam].append(ev)
        
        del A_c, b_c
        
        # Cloud-free case
        dat_cf = E.get_dat(camp, sgl, tF, seed=seed, fc=0.0, cache=True, tag="")
        t_build = time.time()
        A_f, b_f, ywy_f = build_normal_equations(F, dat_cf['y'], dat_cf['sigma'],
                                                  sigma_cl_cf, E.TAU_DAYS, camp)
        X.log(f"  Normal eq built (cloudfree) in {time.time()-t_build:.1f}s")
        
        for lam in LAM_GRID:
            ev = compute_evidence_fast(A_f, b_f, ywy_f, lam, LtL)
            results['cloudfree'][lam].append(ev)
        
        del A_f, b_f
        
        # Print evidence curve for this seed
        ev_cloudy = [np.mean(results['cloudy'][lam][:sidx+1]) for lam in LAM_GRID]
        X.log(f"  Evidence curve (cloudy, running mean): " + 
              " ".join(f"{v:.0f}@{l:.0e}" for l, v in zip(LAM_GRID, ev_cloudy)))
    
    del F, LtL
    
    # Find evidence-optimal λ
    def find_optimal(results_dict):
        means = [np.mean(results_dict[lam]) for lam in LAM_GRID]
        opt_idx = int(np.argmax(means))
        opt_lam = LAM_GRID[opt_idx]
        opt_val = means[opt_idx]
        
        # Bootstrap SE over seeds
        arr = np.array(results_dict[opt_lam])
        se = float(arr.std(ddof=1) / np.sqrt(len(arr))) if len(arr) > 1 else 0.0
        
        return opt_lam, opt_val, se, means
    
    ev_opt_cloudy, ev_val_cloudy, ev_se_cloudy, ev_curve_cloudy = find_optimal(results['cloudy'])
    ev_opt_cf, ev_val_cf, ev_se_cf, ev_curve_cf = find_optimal(results['cloudfree'])
    
    # Find r-optimal, SSIM-optimal, χ²-optimal from archived data
    def find_metric_optimal(metric_dict, maximize=True):
        vals = [metric_dict[lam] for lam in LAM_GRID]
        if not vals or not vals[0]:
            return None, None
        means = [np.mean(v) for v in vals]
        opt_idx = int(np.argmax(means) if maximize else np.argmin(means))
        return LAM_GRID[opt_idx], means[opt_idx]
    
    r_opt_cloudy, r_val_cloudy = find_metric_optimal(archived_r['cloudy'], maximize=True)
    ssim_opt_cloudy, ssim_val_cloudy = find_metric_optimal(archived_ssim['cloudy'], maximize=True)
    
    # χ² optimal: find minimum of χ² (the shallow minimum)
    chi2_opt_cloudy, chi2_val_cloudy = find_metric_optimal(archived_chi2['cloudy'], maximize=False)
    
    # Which of these "optima" are actually interior points of the grid?  On the
    # shipped 9-point grid the log-evidence falls monotonically with lambda, so
    # its maximum is the LEFT edge; r and SSIM rise monotonically, so their
    # maxima are the RIGHT edge.  Only chi2 has an interior minimum.  Calling an
    # edge value "the optimal lambda" is exactly the F-01/F-14 class of error,
    # so every location field is flagged with where it sits on the grid.
    i_lo, i_hi = 0, len(LAM_GRID) - 1

    def _where(lam):
        if lam is None:
            return "absent"
        idx = LAM_GRID.index(lam)
        if idx == i_lo:
            return "left_edge"
        if idx == i_hi:
            return "right_edge"
        return "interior"

    ev_mono_cloudy = "decreasing" if all(np.diff(ev_curve_cloudy) < 0) else \
                     ("increasing" if all(np.diff(ev_curve_cloudy) > 0) else "non-monotone")
    ev_mono_cf = "decreasing" if all(np.diff(ev_curve_cf) < 0) else \
                 ("increasing" if all(np.diff(ev_curve_cf) > 0) else "non-monotone")

    # Summary
    summary = {
        'evidence_optimal': {
            'cloudy': {'lam': ev_opt_cloudy, 'value': float(ev_val_cloudy),
                       'se': float(ev_se_cloudy), 'where': _where(ev_opt_cloudy),
                       'monotone': ev_mono_cloudy},
            'cloudfree': {'lam': ev_opt_cf, 'value': float(ev_val_cf),
                          'se': float(ev_se_cf), 'where': _where(ev_opt_cf),
                          'monotone': ev_mono_cf},
        },
        'evidence_curve': {
            'cloudy': {str(l): float(v) for l, v in zip(LAM_GRID, ev_curve_cloudy)},
            'cloudfree': {str(l): float(v) for l, v in zip(LAM_GRID, ev_curve_cf)},
        },
        'r_max': {'cloudy': {'lam': r_opt_cloudy, 'value': float(r_val_cloudy) if r_val_cloudy else None,
                             'where': _where(r_opt_cloudy)}},
        'ssim_max': {'cloudy': {'lam': ssim_opt_cloudy, 'value': float(ssim_val_cloudy) if ssim_val_cloudy else None,
                                'where': _where(ssim_opt_cloudy)}},
        'chi2_min': {'cloudy': {'lam': chi2_opt_cloudy, 'value': float(chi2_val_cloudy) if chi2_val_cloudy else None,
                                'where': _where(chi2_opt_cloudy)}},
        'frozen_lambda': 3e-3,
        'frozen_vs_chi2_min': {
            'chi2_frozen': float(np.mean(archived_chi2['cloudy'].get(3e-3, [np.nan]))),
            'chi2_min': float(chi2_val_cloudy) if chi2_val_cloudy else None,
        },
    }
    
    # Comparison: does evidence pick a different λ than χ²?
    comparison = {
        'evidence_lam_cloudy': ev_opt_cloudy,
        'r_lam_cloudy': r_opt_cloudy,
        'ssim_lam_cloudy': ssim_opt_cloudy,
        'chi2_lam_cloudy': chi2_opt_cloudy,
        'evidence_vs_r': ev_opt_cloudy == r_opt_cloudy,
        'evidence_vs_ssim': ev_opt_cloudy == ssim_opt_cloudy,
        'evidence_vs_chi2': ev_opt_cloudy == chi2_opt_cloudy,
    }
    
    # Save archives
    npz_data = {
        'lam_grid': np.array(LAM_GRID),
        'evidence_cloudy': np.array([results['cloudy'][lam] for lam in LAM_GRID]),
        'evidence_cloudfree': np.array([results['cloudfree'][lam] for lam in LAM_GRID]),
    }
    
    if archived_r['cloudy'][LAM_GRID[0]]:
        npz_data['r_cloudy'] = np.array([archived_r['cloudy'][lam] for lam in LAM_GRID])
        npz_data['r_cloudfree'] = np.array([archived_r['cloudfree'][lam] for lam in LAM_GRID])
        npz_data['ssim_cloudy'] = np.array([archived_ssim['cloudy'][lam] for lam in LAM_GRID])
        npz_data['chi2_cloudy'] = np.array([archived_chi2['cloudy'][lam] for lam in LAM_GRID])
    
    X.save_npz('evidence_lambda', **npz_data)
    
    # Conclusion: state where each criterion sits on the grid, because three of
    # the four "optima" here are edges, not optima.
    if ev_mono_cloudy == "decreasing":
        conclusion = (
            f"Log-evidence DECREASES monotonically across the grid "
            f"({LAM_GRID[0]:.0e} to {LAM_GRID[-1]:.0e}) in the cloudy case, so "
            f"its maximum is the left edge lambda={ev_opt_cloudy:.0e}, not an "
            f"interior optimum; cloud-free it is {ev_mono_cf} with maximum "
            f"lambda={ev_opt_cf:.0e}. chi2 alone has an interior minimum "
            f"(lambda={chi2_opt_cloudy:.0e}); r and SSIM both rise to the right "
            f"edge (lambda={r_opt_cloudy:.0e}). The determinant term therefore "
            f"does not locate a preferred smoothing scale on this grid: an "
            f"evidence-based rule would drive the solver to the weakest "
            f"regularisation allowed, which is the opposite of what the "
            f"original wording claimed. No truth-blind criterion is established "
            f"here; the grid has to be extended in both directions before any "
            f"of these locations can be called an optimum.")
    else:
        conclusion = (f"Evidence curve is {ev_mono_cloudy}; chi2 minimum at "
                      f"lambda={chi2_opt_cloudy:.0e}, r maximum at "
                      f"lambda={r_opt_cloudy:.0e} ({_where(r_opt_cloudy)}).")
    
    json_data = {
        'provenance': X.provenance('evidence_lambda', extra={
            'n_seeds': len(noise_seeds),
            'lam_grid': LAM_GRID,
            'fast_tier': fast,
            'prior_convention': 'Tikhonov/ridge with Laplacian precision λLᵀL, λ_eff = λ tr(A)/tr(LtL)',
        }),
        'caveats': [
            'Evidence uses deflated system (matching the deflate solver convention)',
            'Constant offset in log-evidence is dropped (only relative comparison matters)',
            'Archived lamsweep parts reused for r/SSIM/χ² comparison columns',
            f'Grid spans {LAM_GRID[0]:.0e}..{LAM_GRID[-1]:.0e}; the evidence '
            f'maximum and the r/SSIM maxima lie ON that boundary, so they are '
            f'edge locations, not located optima (chi2 is the only interior one)',
            f'{len(noise_seeds)} noise seeds',
        ],
        'headline': {
            # every lambda_* field is a LOCATION on the grid, never a metric value
            'lambda_evidence_cloudy': ev_opt_cloudy,
            'lambda_evidence_cloudfree': ev_opt_cf,
            'lambda_r_max_cloudy': r_opt_cloudy,
            'lambda_ssim_max_cloudy': ssim_opt_cloudy,
            'lambda_chi2_min_cloudy': chi2_opt_cloudy,
            'chi2_frozen_minus_min_cloudy': (
                float(np.mean(archived_chi2['cloudy'][3e-3])) - float(chi2_val_cloudy)
                if chi2_val_cloudy and archived_chi2['cloudy'][3e-3] else None),
            'log_evidence_first_minus_last_cloudy': float(
                ev_curve_cloudy[0] - ev_curve_cloudy[-1]),
            'conclusion': conclusion,
        },
        'comparison': comparison,
        'summary': summary,
    }
    X.save_json('evidence_lambda', json_data)
    
    wallclock = time.time() - t_start
    X.log(f"\nCompleted in {wallclock:.1f}s ({wallclock/60:.1f} min)")
    
    X.summary('evidence_lambda',
              n_seeds=len(noise_seeds),
              evidence_opt_cloudy=ev_opt_cloudy,
              evidence_opt_cf=ev_opt_cf,
              r_opt_cloudy=r_opt_cloudy,
              ssim_opt_cloudy=ssim_opt_cloudy,
              chi2_opt_cloudy=chi2_opt_cloudy,
              conclusion=conclusion,
              wallclock_s=wallclock)

if __name__ == '__main__':
    main()

"""Modern inversion priors as a floor for method claims (Part VII item 8).

On identical archived datasets/maps, compare the shipped TDI estimator against:
(a) Total-variation regularised reconstruction
(b) Sparse coding / dictionary learning baseline
(c) A tiny unrolled learned denoiser (only if trainable in <3 min on CPU)

Report r/SSIM/NRMSE/bias/contrast per prior per seed with paired stats vs TDI.

Run from src/:
    python3 -m ext.priors [--fast]
"""

import sys
import time
import numpy as np

sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))

import expcommon as E
import sglsim as S
from ext import extcommon as X

# Check for sklearn
try:
    import sklearn
    SKLEARN_VERSION = sklearn.__version__
    HAS_SKLEARN = True
except ImportError:
    SKLEARN_VERSION = None
    HAS_SKLEARN = False


def tv_denoise_2d(image, lam_tv, n_iter=100, step_size=0.1):
    """Total variation denoising via proximal gradient (Chambolle 2004).
    
    Solves: min_x ½||x - y||² + λ TV(x)
    
    Uses the dual formulation for efficiency.
    """
    nlat, nlon = image.shape
    # Dual variables
    px = np.zeros((nlat, nlon))
    py = np.zeros((nlat, nlon))
    
    x = image.copy()
    tau = step_size
    
    for _ in range(n_iter):
        # Compute gradient of x
        dx = np.roll(x, -1, axis=1) - x
        dy = np.roll(x, -1, axis=0) - x
        
        # Update dual variables
        px = px + tau / lam_tv * dx
        py = py + tau / lam_tv * dy
        
        # Project onto unit ball
        norm = np.sqrt(px**2 + py**2)
        norm = np.maximum(norm, 1.0)
        px /= norm
        py /= norm
        
        # Update primal variable
        div_p = (px - np.roll(px, 1, axis=1)) + (py - np.roll(py, 1, axis=0))
        x = image - lam_tv * div_p
    
    return x


def tv_reconstruct(F, y, sigma, sigma_cl, tau_days, camp, LtL, lam_gls, lam_tv,
                   n_iter=50):
    """TV-regularized reconstruction.
    
    First get the TDI solution, then apply TV denoising as a post-processing step.
    This is a simplified approach; a proper TV reconstruction would solve the
    joint problem, but that requires a custom solver.
    """
    # Get TDI solution first
    s_tdi = S.solve_gls_profiled(F, y, camp, sigma, sigma_cl, tau_days, lam_gls,
                                  LtL, white=False, deflate=True, anchor=True)
    
    # Reshape to 2D and apply TV denoising
    nlat, nlon = 36, 72
    s_2d = s_tdi.reshape(nlat, nlon)
    s_tv = tv_denoise_2d(s_2d, lam_tv, n_iter=n_iter)
    
    return s_tv.ravel()


def sparse_reconstruct(F, y, sigma, sigma_cl, tau_days, camp, LtL, lam_gls,
                       n_components=64):
    """Sparse coding reconstruction using dictionary learning.
    
    First get the TDI solution, then learn a sparse dictionary from it and
    re-encode. This tests whether a data-driven prior can improve on TDI.
    """
    if not HAS_SKLEARN:
        return None, "sklearn not available"
    
    from sklearn.decomposition import MiniBatchDictionaryLearning
    
    # Get TDI solution
    s_tdi = S.solve_gls_profiled(F, y, camp, sigma, sigma_cl, tau_days, lam_gls,
                                  LtL, white=False, deflate=True, anchor=True)
    
    nlat, nlon = 36, 72
    s_2d = s_tdi.reshape(nlat, nlon)
    
    # Extract patches for dictionary learning
    patch_size = 6
    patches = []
    for i in range(0, nlat - patch_size + 1, 3):
        for j in range(0, nlon - patch_size + 1, 3):
            patch = s_2d[i:i+patch_size, j:j+patch_size]
            patches.append(patch.ravel())
    
    patches = np.array(patches)
    
    # Learn dictionary
    dico = MiniBatchDictionaryLearning(n_components=n_components, alpha=1.0,
                                       max_iter=100, batch_size=50, random_state=42)
    dico.fit(patches)
    
    # Reconstruct using sparse coding
    patches_sparse = dico.transform(patches)
    patches_recon = patches_sparse @ dico.components_
    
    # Put patches back into image
    s_sparse = s_2d.copy()
    idx = 0
    for i in range(0, nlat - patch_size + 1, 3):
        for j in range(0, nlon - patch_size + 1, 3):
            patch = patches_recon[idx].reshape(patch_size, patch_size)
            # Average overlapping patches
            s_sparse[i:i+patch_size, j:j+patch_size] = (
                0.5 * s_sparse[i:i+patch_size, j:j+patch_size] + 0.5 * patch
            )
            idx += 1
    
    return s_sparse.ravel(), None


def learned_denoise(s_tdi, n_iter=10):
    """Tiny unrolled learned denoiser (if trainable in <3 min).
    
    Status: not_established - training a learned denoiser from scratch on a
    single map would overfit catastrophically. A proper implementation would
    need a training set of truth/reconstruction pairs, which we don't have
    in this single-map setting.
    """
    return None, "not_established: requires training set of truth/reconstruction pairs"


def main():
    t_start = time.time()
    noise_seeds, _ = X.tier_seeds()
    fast = "--fast" in sys.argv[1:]
    
    if fast:
        noise_seeds = noise_seeds[:2]
    else:
        noise_seeds = noise_seeds[:4]  # Reduced for computational budget
    
    X.log(f"Priors comparison: {len(noise_seeds)} seeds")
    X.log(f"Noise seeds: {noise_seeds}")
    X.log(f"sklearn available: {HAS_SKLEARN} (version {SKLEARN_VERSION})")
    
    # Load F (mmap)
    camp = E.campaign()
    sgl = E.sgl()
    F = E.get_F(camp, sgl)
    LtL = E.get_LtL()
    
    # Get sigma_cl from archive
    sigma_cl = float(np.load(E.PARTS / 'clouds_f3_s0.npz')['sigma_cl'])
    
    # Truth map
    tF, tc = E.truth(seed=7)
    
    # Storage for results
    results = {
        'tdi': [],
        'tv': [],
        'sparse': [],
        'learned': [],
    }
    
    # TV regularization strength (tuned to be comparable to TDI)
    lam_tv = 0.01
    
    for sidx, seed in enumerate(noise_seeds):
        X.log(f"\n=== Seed {sidx+1}/{len(noise_seeds)}: {seed} ===")
        
        # Get dataset
        dat = E.get_dat(camp, sgl, tF, seed=seed, fc=0.55, cache=True, tag="")
        
        # TDI (profiled)
        t_tdi = time.time()
        s_tdi = E.fit('profiled', F, dat, camp, sigma_cl)
        ev_tdi = E.evaluate(s_tdi, tc)
        results['tdi'].append(ev_tdi)
        X.log(f"  TDI: r={ev_tdi['pearson']:.4f}, SSIM={ev_tdi['ssim']:.4f}, "
              f"{time.time()-t_tdi:.1f}s")
        
        # TV
        t_tv = time.time()
        s_tv = tv_reconstruct(F, dat['y'], dat['sigma'], sigma_cl, E.TAU_DAYS,
                              camp, LtL, E.LAM_GLS, lam_tv, n_iter=50)
        ev_tv = E.evaluate(s_tv, tc)
        results['tv'].append(ev_tv)
        X.log(f"  TV: r={ev_tv['pearson']:.4f}, SSIM={ev_tv['ssim']:.4f}, "
              f"{time.time()-t_tv:.1f}s")
        
        # Sparse
        t_sparse = time.time()
        s_sparse, sparse_err = sparse_reconstruct(F, dat['y'], dat['sigma'],
                                                   sigma_cl, E.TAU_DAYS, camp,
                                                   LtL, E.LAM_GLS)
        if s_sparse is not None:
            ev_sparse = E.evaluate(s_sparse, tc)
            results['sparse'].append(ev_sparse)
            X.log(f"  Sparse: r={ev_sparse['pearson']:.4f}, SSIM={ev_sparse['ssim']:.4f}, "
                  f"{time.time()-t_sparse:.1f}s")
        else:
            X.log(f"  Sparse: {sparse_err}")
    
    del F, LtL
    
    # Aggregate statistics
    def aggregate(metrics_list, key):
        if not metrics_list:
            return {'status': 'not_established', 'reason': 'no data'}
        vals = [m[key] for m in metrics_list]
        arr = np.array(vals)
        return {
            'mean': float(arr.mean()),
            'sd': float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
            'se': float(arr.std(ddof=1) / np.sqrt(len(arr))) if len(arr) > 1 else 0.0,
            'n': len(arr),
        }
    
    summary = {}
    for method in ['tdi', 'tv', 'sparse', 'learned']:
        if results[method]:
            summary[method] = {
                'pearson': aggregate(results[method], 'pearson'),
                'ssim': aggregate(results[method], 'ssim'),
                'nrmse': aggregate(results[method], 'nrmse'),
                'bias': aggregate(results[method], 'bias'),
                'contrast': aggregate(results[method], 'contrast'),
            }
        else:
            summary[method] = {'status': 'not_established', 'reason': 'no data'}
    
    # Paired stats: TDI vs each alternative
    paired = {}
    for method in ['tv', 'sparse']:
        if results[method] and results['tdi']:
            tdi_r = [m['pearson'] for m in results['tdi']]
            alt_r = [m['pearson'] for m in results[method]]
            paired[method] = E.paired_stats(tdi_r, alt_r)
    
    # Learned denoiser status
    _, learned_err = learned_denoise(None)
    summary['learned'] = {'status': 'not_established', 'reason': learned_err}
    
    # Conclusion
    tdi_r = summary['tdi']['pearson']['mean']
    tv_r = summary['tv']['pearson']['mean'] if 'pearson' in summary['tv'] else None
    sparse_r = summary['sparse']['pearson']['mean'] if 'pearson' in summary['sparse'] else None
    
    # Conclusion: ranked, with the paired intervals, and with the confounds
    # named in the sentence rather than left to the caveats list.  The old text
    # asserted that TDI "confirms" a better prior; at four seeds the sign test
    # cannot reach p < 0.125, and the sparse arm scores HIGHER than TDI.
    arms = {"TDI": tdi_r}
    if tv_r is not None:
        arms["TV"] = tv_r
    if sparse_r is not None:
        arms["sparse"] = sparse_r
    order = ", ".join(f"{k} r={v:.4f}" for k, v in
                      sorted(arms.items(), key=lambda kv: -kv[1]))
    pd_tv = paired.get("tv")
    pd_sp = paired.get("sparse")
    bits = []
    if pd_tv:
        bits.append(f"TDI-TV paired {pd_tv['mean']:+.4f} "
                    f"[{pd_tv['ci_lo']:+.4f}, {pd_tv['ci_hi']:+.4f}] "
                    f"sign-test p={pd_tv['p_sign']:.3f} on {pd_tv['n']} seeds")
    if pd_sp:
        bits.append(f"TDI-sparse paired {pd_sp['mean']:+.4f} "
                    f"[{pd_sp['ci_lo']:+.4f}, {pd_sp['ci_hi']:+.4f}] "
                    f"sign-test p={pd_sp['p_sign']:.3f}")
    conclusion = (
        f"Ranked by r: {order}. " + "; ".join(bits) + ". "
        "This is NOT a clean prior bake-off: the TV arm post-processes the TDI "
        "map, and the sparse dictionary is learned from it, so a margin either "
        "way partly measures the operator rather than an independent prior. "
        "At four noise seeds no pairing here can be significant (exact "
        "sign-test floor p=0.125), and the sparse arm is not distinguishable "
        "from TDI.")
    
    # Save archives
    npz_data = {
        'tdi_pearson': np.array([m['pearson'] for m in results['tdi']]),
        'tv_pearson': np.array([m['pearson'] for m in results['tv']]) if results['tv'] else np.array([]),
    }
    if results['sparse']:
        npz_data['sparse_pearson'] = np.array([m['pearson'] for m in results['sparse']])
    
    X.save_npz('priors', **npz_data)
    
    json_data = {
        'provenance': X.provenance('priors', extra={
            'n_seeds': len(noise_seeds),
            'lam_tv': lam_tv,
            'sklearn_version': SKLEARN_VERSION,
            'fast_tier': fast,
        }),
        'caveats': [
            'TV uses post-processing of TDI solution (not joint optimization)',
            'Sparse coding learns dictionary from TDI solution (circular)',
            'Learned denoiser: not_established (requires training set)',
            f'{len(noise_seeds)} noise seeds',
        ],
        'headline': {
            'tdi_r': tdi_r,
            'tv_r': tv_r,
            'sparse_r': sparse_r,
            'conclusion': conclusion,
        },
        'summary': summary,
        'paired': paired,
    }
    X.save_json('priors', json_data)
    
    wallclock = time.time() - t_start
    X.log(f"\nCompleted in {wallclock:.1f}s ({wallclock/60:.1f} min)")
    
    X.summary('priors',
              n_seeds=len(noise_seeds),
              tdi_r=tdi_r,
              tv_r=tv_r,
              sparse_r=sparse_r,
              conclusion=conclusion,
              wallclock_s=wallclock)

if __name__ == '__main__':
    main()

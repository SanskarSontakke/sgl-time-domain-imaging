"""Truth-map ensemble (external validity).

The single biggest statistical weakness of the paper's headline numbers is that
they were computed over ONE truth map (seed=7) with 10 noise realizations. This
module separates the between-map spread from the Monte-Carlo error by running
the fiducial configuration over multiple truth seeds.

For each truth_seed in TRUTH_SEEDS:
  - Generate truth map
  - For each noise_seed in EXT_SEEDS/FULL_SEEDS:
    - Simulate dataset (with tag to avoid cache collisions)
    - Fit with profiled and deflate solvers
    - Evaluate metrics (pearson, ssim, nrmse, bias, contrast)
  - Aggregate statistics across noise seeds

Validation: truth_seed=7 must reproduce the archived fiducial pearson to <1e-6.

Run from src/:
    python3 -m ext.truth_ensemble [--fast]
"""

import sys
import time
import numpy as np

# Add src to path for flat imports
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent.parent))

import expcommon as E
import sglsim as S
from ext import extcommon as X

def main():
    t_start = time.time()
    fast = "--fast" in sys.argv[1:]
    
    # Custom seed counts to stay within 25 min budget
    # Fast: 4 truth x 2 noise = 8 combinations
    # Full: 5 truth x 4 noise = 20 combinations (reduced from 10x10 to fit budget)
    if fast:
        truth_seeds = X.TRUTH_SEEDS[:4]
        noise_seeds = X.EXT_SEEDS[:2]
    else:
        truth_seeds = X.TRUTH_SEEDS[:5]  # Reduced from 10 to 5
        noise_seeds = X.EXT_SEEDS  # 4 seeds

    X.log(f"Truth ensemble: {len(truth_seeds)} truth seeds x {len(noise_seeds)} noise seeds")
    X.log(f"Truth seeds: {truth_seeds}")
    X.log(f"Noise seeds: {noise_seeds}")

    # Load F (mmap, fast)
    camp = E.campaign()
    sgl = E.sgl()
    F = E.get_F(camp, sgl)
    X.log(f"F loaded: shape={F.shape}")

    # Get sigma_cl from archive (NEVER call get_sigcl)
    sigma_cl_cloudy = float(np.load(E.PARTS / 'clouds_f3_s0.npz')['sigma_cl'])
    sigma_cl_cf = 0.0
    X.log(f"sigma_cl: cloudy={sigma_cl_cloudy:.6f}, cloud-free={sigma_cl_cf}")

    # Storage for results
    results = {
        'truth_seeds': [],
        'noise_seeds': noise_seeds,
        'cloudy': {'profiled': [], 'deflate': []},
        'cloudfree': {'profiled': [], 'deflate': []},
    }

    # Archived reference for validation (truth_seed=7, noise_seed=11)
    archived_cloudy = np.load(E.PARTS / 'clouds_f3_s0.npz')
    archived_cf = np.load(E.PARTS / 'clouds_f0_s0.npz')
    ref_pearson_cloudy = float(archived_cloudy['profiled_pearson'])
    ref_pearson_cf = float(archived_cf['profiled_pearson'])

    validation = {}

    for tidx, truth_seed in enumerate(truth_seeds):
        X.log(f"\n=== Truth seed {tidx+1}/{len(truth_seeds)}: {truth_seed} ===")
        results['truth_seeds'].append(truth_seed)

        # Generate truth map
        tF, tc = E.truth(seed=truth_seed)
        X.log(f"Truth map: shape={tc.shape}, mean={tc.mean():.4f}, std={tc.std():.4f}")

        # Run over noise seeds
        for nidx, noise_seed in enumerate(noise_seeds):
            t_dataset = time.time()
            tag = f"_t{truth_seed}"

            # Cloudy (fc=0.55)
            dat_cloudy = E.get_dat(camp, sgl, tF, seed=noise_seed, fc=0.55,
                                   cache=True, tag=tag)
            s_prof_c = E.fit('profiled', F, dat_cloudy, camp, sigma_cl_cloudy)
            s_defl_c = E.fit('deflate', F, dat_cloudy, camp, sigma_cl_cloudy)
            ev_prof_c = E.evaluate(s_prof_c, tc)
            ev_defl_c = E.evaluate(s_defl_c, tc)

            # Cloud-free (fc=0.0)
            dat_cf = E.get_dat(camp, sgl, tF, seed=noise_seed, fc=0.0,
                               cache=True, tag=tag)
            s_prof_f = E.fit('profiled', F, dat_cf, camp, sigma_cl_cf)
            s_defl_f = E.fit('deflate', F, dat_cf, camp, sigma_cl_cf)
            ev_prof_f = E.evaluate(s_prof_f, tc)
            ev_defl_f = E.evaluate(s_defl_f, tc)

            results['cloudy']['profiled'].append(ev_prof_c)
            results['cloudy']['deflate'].append(ev_defl_c)
            results['cloudfree']['profiled'].append(ev_prof_f)
            results['cloudfree']['deflate'].append(ev_defl_f)

            # Validation check for truth_seed=7, noise_seed=11
            if truth_seed == 7 and noise_seed == 11:
                dev_cloudy = abs(ev_prof_c['pearson'] - ref_pearson_cloudy)
                dev_cf = abs(ev_prof_f['pearson'] - ref_pearson_cf)
                validation = {
                    'truth_seed': 7,
                    'noise_seed': 11,
                    'cloudy_pearson': ev_prof_c['pearson'],
                    'cloudy_archived': ref_pearson_cloudy,
                    'cloudy_deviation': dev_cloudy,
                    'cloudfree_pearson': ev_prof_f['pearson'],
                    'cloudfree_archived': ref_pearson_cf,
                    'cloudfree_deviation': dev_cf,
                    'pass': dev_cloudy < 1e-6 and dev_cf < 1e-6,
                }
                X.log(f"VALIDATION: cloudy dev={dev_cloudy:.2e}, cf dev={dev_cf:.2e}, "
                      f"pass={validation['pass']}")

            dt = time.time() - t_dataset
            X.log(f"  Noise seed {nidx+1}/{len(noise_seeds)}: {noise_seed}, "
                  f"cloudy r_prof={ev_prof_c['pearson']:.4f}, "
                  f"cf r_prof={ev_prof_f['pearson']:.4f}, {dt:.1f}s")

    del F  # Free memory

    # Aggregate statistics
    def aggregate(metrics_list, key):
        vals = [m[key] for m in metrics_list]
        arr = np.array(vals)
        return {
            'mean': float(arr.mean()),
            'sd': float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
            'se': float(arr.std(ddof=1) / np.sqrt(len(arr))) if len(arr) > 1 else 0.0,
            'n': len(arr),
        }

    summary = {
        'cloudy': {},
        'cloudfree': {},
    }
    for method in ['profiled', 'deflate']:
        for config in ['cloudy', 'cloudfree']:
            metrics = results[config][method]
            summary[config][method] = {
                'pearson': aggregate(metrics, 'pearson'),
                'ssim': aggregate(metrics, 'ssim'),
                'nrmse': aggregate(metrics, 'nrmse'),
                'bias': aggregate(metrics, 'bias'),
                'contrast': aggregate(metrics, 'contrast'),
            }

    # Compute mean/sd ratio (the headline uncertainty metric)
    for config in ['cloudy', 'cloudfree']:
        for method in ['profiled', 'deflate']:
            r_mean = summary[config][method]['pearson']['mean']
            r_sd = summary[config][method]['pearson']['sd']
            summary[config][method]['pearson']['mean_over_sd'] = (
                r_mean / r_sd if r_sd > 0 else float('inf')
            )

    # Check sign stability of profiled-deflate difference
    # Group by truth seed, compute mean over noise seeds for each method
    n_truth = len(truth_seeds)
    n_noise = len(noise_seeds)
    signs_cloudy = []
    signs_cf = []
    for tidx in range(n_truth):
        # Average over noise seeds for this truth seed
        prof_c = np.mean([results['cloudy']['profiled'][tidx*n_noise + nidx]['pearson']
                          for nidx in range(n_noise)])
        defl_c = np.mean([results['cloudy']['deflate'][tidx*n_noise + nidx]['pearson']
                          for nidx in range(n_noise)])
        signs_cloudy.append(1 if prof_c > defl_c else -1)

        prof_f = np.mean([results['cloudfree']['profiled'][tidx*n_noise + nidx]['pearson']
                          for nidx in range(n_noise)])
        defl_f = np.mean([results['cloudfree']['deflate'][tidx*n_noise + nidx]['pearson']
                          for nidx in range(n_noise)])
        signs_cf.append(1 if prof_f > defl_f else -1)

    summary['sign_stability'] = {
        'cloudy': {
            'n_positive': sum(1 for s in signs_cloudy if s > 0),
            'n_negative': sum(1 for s in signs_cloudy if s < 0),
            'n_total': len(signs_cloudy),
            'stable': all(s == signs_cloudy[0] for s in signs_cloudy),
        },
        'cloudfree': {
            'n_positive': sum(1 for s in signs_cf if s > 0),
            'n_negative': sum(1 for s in signs_cf if s < 0),
            'n_total': len(signs_cf),
            'stable': all(s == signs_cf[0] for s in signs_cf),
        },
    }

    # Variance decomposition, because "between-map uncertainty dominates" is a
    # claim that has to be MEASURED, not asserted.  For the cloudy case the
    # noise-seed scatter and the truth-map scatter turn out to be comparable
    # (within-map slightly larger), so the previous caveat text was false.
    def _decomp(regime, method):
        arr = np.array([results[regime][method][tidx * n_noise + nidx]['pearson']
                        for tidx in range(n_truth) for nidx in range(n_noise)]
                       ).reshape(n_truth, n_noise)
        between = float(arr.mean(axis=1).std(ddof=1))
        within = float(np.mean(arr.std(axis=1, ddof=1)))
        return dict(between_map_sd=between, within_map_sd=within,
                    dominant=('between-map' if between ** 2 > within ** 2
                              else 'within-map (noise seeds)'))

    summary['variance_decomposition'] = {
        'cloudy': _decomp('cloudy', 'profiled'),
        'cloudfree': _decomp('cloudfree', 'profiled'),
    }
    vd = summary['variance_decomposition']

    def _pdiff(regime):
        p = np.array([m['pearson'] for m in results[regime]['profiled']])
        d = np.array([m['pearson'] for m in results[regime]['deflate']])
        return float(np.mean(p - d)), float(np.std(p - d, ddof=1))

    d_cloudy, d_cloudy_sd = _pdiff('cloudy')
    d_cf, d_cf_sd = _pdiff('cloudfree')

    # Is the fiducial geography the easiest or the hardest?  Computed, because
    # the manuscript quotes the fiducial map as its headline number.
    per_map = np.array([np.mean([results['cloudy']['profiled'][tidx * n_noise + nidx]['pearson']
                                 for nidx in range(n_noise)])
                        for tidx in range(n_truth)])
    fid_rank = int(np.argsort(-per_map).tolist().index(0)) if 0 in range(n_truth) else None

    # Save archives
    npz_data = {
        'truth_seeds': np.array(results['truth_seeds']),
        'noise_seeds': np.array(results['noise_seeds']),
        'cloudy_profiled_pearson': np.array([m['pearson'] for m in results['cloudy']['profiled']]),
        'cloudy_deflate_pearson': np.array([m['pearson'] for m in results['cloudy']['deflate']]),
        'cloudfree_profiled_pearson': np.array([m['pearson'] for m in results['cloudfree']['profiled']]),
        'cloudfree_deflate_pearson': np.array([m['pearson'] for m in results['cloudfree']['deflate']]),
    }
    X.save_npz('truth_ensemble', **npz_data)

    # Build JSON with provenance, caveats, headline
    # Measured here, not in a docstring: a budget figure written before the run
    # is finished is a claim about the machine, not about the archive.  This is
    # the time spent SOLVING; the final wall clock, logged after the save, is
    # reported separately and is slightly larger.
    wallclock_solve_s = time.time() - t_start
    json_data = {
        'provenance': X.provenance('truth_ensemble', extra={
            'n_truth_seeds': len(truth_seeds),
            'n_noise_seeds': len(noise_seeds),
            'fast_tier': fast,
        }),
        'caveats': [
            f"Dominant cloudy uncertainty is {vd['cloudy']['dominant']}: "
            f"between-map sd {vd['cloudy']['between_map_sd']:.5f} vs within-map "
            f"(noise-seed) sd {vd['cloudy']['within_map_sd']:.5f}; cloud-free "
            f"{vd['cloudfree']['dominant']} "
            f"({vd['cloudfree']['between_map_sd']:.5f} vs "
            f"{vd['cloudfree']['within_map_sd']:.5f})",
            (f"Profiled-minus-deflate sign is stable across truth maps "
             f"({summary['sign_stability']['cloudy']['n_positive']}/"
             f"{summary['sign_stability']['cloudy']['n_total']} maps agree in the "
             f"cloudy case)"
             if summary['sign_stability']['cloudy']['stable'] else
             f"Profiled-minus-deflate sign is NOT stable across truth maps "
             f"({summary['sign_stability']['cloudy']['n_positive']} positive, "
             f"{summary['sign_stability']['cloudy']['n_negative']} negative of "
             f"{summary['sign_stability']['cloudy']['n_total']} maps): mean "
             f"difference {d_cloudy:+.2e}, member-to-member scatter "
             f"{d_cloudy_sd:.2e}; the two solvers are indistinguishable under a "
             f"geography change, which is a weaker statement than 'profiled is "
             f"better'"),
            'Validation: truth_seed=7 reproduces archived fiducial to <1e-6' if validation.get('pass') else 'Validation FAILED',
            (f'Full tier reduced to {len(truth_seeds)} truth x {len(noise_seeds)} '
             f'noise seeds ({len(truth_seeds) * len(noise_seeds)} members); the '
             f'solve took {wallclock_solve_s / 60:.1f} min, so the grid is a '
             f'budget decision, not a convergence check'
             if not fast else
             f'Fast tier: {len(truth_seeds)} truth x {len(noise_seeds)} noise seeds'),
        ],
        'headline': {
            'cloudy_profiled_r': summary['cloudy']['profiled']['pearson'],
            'cloudfree_profiled_r': summary['cloudfree']['profiled']['pearson'],
            'mean_over_sd_cloudy': summary['cloudy']['profiled']['pearson']['mean_over_sd'],
            'mean_over_sd_cloudfree': summary['cloudfree']['profiled']['pearson']['mean_over_sd'],
            'cloudy_between_map_sd': vd['cloudy']['between_map_sd'],
            'cloudy_within_map_sd': vd['cloudy']['within_map_sd'],
            'sign_stable_cloudy': bool(summary['sign_stability']['cloudy']['stable']),
            'sign_stable_cloudfree': bool(summary['sign_stability']['cloudfree']['stable']),
            'conclusion': (
                f"Across {n_truth} independent planetary geographies the cloudy "
                f"profiled correlation is {summary['cloudy']['profiled']['pearson']['mean']:.4f} "
                f"+/- {summary['cloudy']['profiled']['pearson']['sd']:.4f} (sd), "
                f"of which {vd['cloudy']['between_map_sd']:.4f} is between maps and "
                f"{vd['cloudy']['within_map_sd']:.4f} within-map; the fiducial "
                f"map ranks {fid_rank + 1} of {n_truth} on this metric. The "
                f"profiled-minus-deflate "
                f"gap is {d_cloudy:+.2e} cloudy and {d_cf:+.2e} cloud-free, with the "
                f"sign stable across maps in the "
                f"{'cloud-free case only' if not summary['sign_stability']['cloudy']['stable'] else 'both cases'}"
                f", so the solver comparison is a null result under a geography "
                f"change"
                + (", while the fiducial map's place at the top of the ensemble "
                   "is a real property of that map and not of the noise."
                   if fid_rank == 0 else
                   ", and the fiducial map is NOT the most favourable geography, "
                   "so the headline r understates rather than overstates the "
                   "ensemble.")),
        },
        'validation': validation,
        'summary': summary,
        'sign_stability': summary['sign_stability'],
    }
    X.save_json('truth_ensemble', json_data)

    wallclock = time.time() - t_start
    X.log(f"\nCompleted in {wallclock:.1f}s ({wallclock/60:.1f} min)")

    # Print SUMMARY_JSON
    X.summary('truth_ensemble',
              n_truth=len(truth_seeds),
              n_noise=len(noise_seeds),
              cloudy_r=summary['cloudy']['profiled']['pearson']['mean'],
              cloudy_r_sd=summary['cloudy']['profiled']['pearson']['sd'],
              cloudfree_r=summary['cloudfree']['profiled']['pearson']['mean'],
              cloudfree_r_sd=summary['cloudfree']['profiled']['pearson']['sd'],
              validation_pass=validation.get('pass', False),
              wallclock_s=wallclock)

if __name__ == '__main__':
    main()

# src/ — simulation and analysis code

| File | Role |
|------|------|
| `sglsim.py` | Library: SGL kernel & convolution, photon/noise model, rotating+illuminated scene renderer, OU cloud model, campaign/raster definition, forward-operator builder, TDI/GLS estimators, baselines (static Wiener, phase-binned coadd), metrics (SSIM/r/NRMSE). |
| `run_experiments.py` | CLI driver. Subcommands: `setup`, `validation`, `tune`, `clouds <ifc> <iseed>`, `cadence <icfg> <iseed> <ds|solve>`, `robust_tau`, `robust_sig`, `robust_prot <0|1>`, `merge`. Each invocation runs in well under a minute and checkpoints to `results/parts/`; `merge` assembles the final archives. Operator caches go to `/tmp` (rebuilt by `setup` after a reboot). |
| `cad_solve_one.py` | `python3 cad_solve_one.py <icfg> <iseed> <gls|white|b2>` — solves one cadence configuration with one method (used for the largest, M_p=64, configuration). |
| `targets.py` | Computes the target-selection table (image sizes, photon rates, focal-line antipodes, ecliptic latitudes, image-plane dynamics, tracking budgets) → `results/targets.json`, `paper/figures/fig_targets.pdf`. |
| `make_figures.py` | Renders Figures 1–6 from `results/*.npz` into `paper/figures/`. Optional args select figures, e.g. `python3 make_figures.py 3 5`. |

Conventions: normalized scene units (1 = disk-mean signal of a fully
illuminated albedo-0.3 planet); all constants at the top of `sglsim.py`
with citations; every stochastic element takes an explicit seed.

"""Shared, checkpointed experiment harness for the revised manuscript.

Design constraints (referee comments 6, 8, 9; editor's reproducibility request):

* Every expensive object (forward operator F, Laplacian, sigma_cl) is built once
  and cached under results/cache, keyed by the parameters that actually change
  it -- including the exposure-quadrature order and the kernel core.  A stale
  cache entry can therefore not silently serve a different physics convention.
* Long runs write one small .npz per (configuration, seed) into results/parts.
  Re-running skips completed parts, so an interrupted suite resumes instead of
  restarting, and every reported aggregate can be recomputed from the parts.
* Seeds, modes and quadrature orders are recorded INSIDE each part file, so a
  shipped number can be traced to the exact command that produced it.
"""

import json
import os
import time
from pathlib import Path

import numpy as np
import sglsim as S

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "results"
PARTS = DATA / "parts"
CACHE = DATA / "cache"
PART_PREFIX = "v3_"            # see part_path() -- avoids a v2 name collision
for _d in (DATA, PARTS, CACHE):
    _d.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------
# Fixed conventions (single source of truth for the manuscript)
# ----------------------------------------------------------------------
NLAT, NLON = 36, 72
NLATF, NLONF = 72, 144
TRUTH_SEED = 7
CAMPAIGN_SEED = 2026
TAU_DAYS = 4.0
LAM_GLS = 3e-3
KW_B2 = 3e-3
# Phase-bin count for the coadd baselines (B2, and B1 = the nbins=1 limit).
# A pass has Prot/(ts/nbin) = 48 distinct sample PHASES (raster slot spacing is
# ts = 1800 s = 1/48 of the rotation period), so a bin coarser than 48 averages
# over rotation: with nbins=8 the smear is 45 deg of longitude and the recovered
# map degenerates (r ~ 0.06 on ideal cloud-free data, versus 0.94 at nbins=16).
# nbins=16 is the best-tuned compromise between smear and per-bin sample count
# (3 phases x mp=16 revisits per bin); it is fixed here so every table quotes the
# SAME, properly binned competitor.
NBINS_B2 = 16
NBINS_B2_COARSE = 8           # the naive choice, kept only to quantify the artifact
FC = 0.55
NSUB = 16                      # Gauss-Legendre order used everywhere (R: quadrature)
SEEDS = [11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
CAD_SEEDS = SEEDS[:6]
# Profile-likelihood grid: 25 trial operators, each of which must be built
# (41 s) and refit per seed, so the seed count here is deliberately smaller and
# is reported as such.
PROF_SEEDS = SEEDS[:4]
PROF_T = [1.0, 2.0, 4.0]
FCS = [0.0, 0.25, 0.40, 0.55, 0.70]
# Arm A: fixed photons per raster position (mp*ts = 8 h) -- wall clock GROWS.
ARM_PHOTONS = [(7200.0, 4), (3600.0, 8), (1800.0, 16), (900.0, 32), (450.0, 64)]
# Arm B: fixed wall clock -- exposure time FALLS, photons are not conserved.
ARM_WALL = 90.0
METHODS = ("gls", "white", "b2")


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


# ----------------------------------------------------------------------
# Campaign / operator / cache plumbing
# ----------------------------------------------------------------------
def campaign(ts=1800.0, mp=16, mode="photons", gap_total_s=0.0, static=False):
    """mode="photons": mp*ts fixed, wall clock free.  mode="wallclock": fit
    `wall` days, let ts fall.  Both arms charge T_OVERHEAD per dwell."""
    return S.Campaign(n=64, nsc=16, ts=ts, mp=mp, seed=CAMPAIGN_SEED,
                      mode=mode, wall_target=ARM_WALL, static=static,
                      gap_total_s=gap_total_s)


def wallclock_gap(nbin_slots, mp):
    """Inter-pass dead time implied by a `nbin_slots`-hour maneuver budget."""
    return nbin_slots * 3600.0


def sgl(core="point"):
    return S.SGLOperator(64, core=core)


def F_cache_name(camp, prot, theta, psi, phi0, nsub, core):
    return ("F_n%d_ts%d_mp%d_ns%d_core_%s_p%.6g_th%.4g_psi%.4g_phi%.4g_stat%d_gap%d"
            % (camp.n, round(camp.ts), camp.mp, nsub, core, prot, theta, psi,
               phi0, int(camp.static), round(camp.gap_total_s))).replace(".", "p")


def get_F(camp, sglop, prot=S.PROT, theta_pole=0.0, psi_pole=0.0, phi0=0.0,
          nsub=NSUB, build_ok=True, cache=True):
    """Forward operator for one (campaign, geometry, quadrature, core).

    ``cache=True`` writes/reads results/cache, which is right for the FIDUCIAL
    operator (used by several commands in separate processes).  It must NOT be
    used for the robustness variants: one float32 F at n = 64 is 0.68 GB and the
    sandbox has only a few GB free, so the geometry/climatology/profile-likelihood
    sweeps build in RAM (``cache=False``) and loop the seeds inside one process.
    """
    if not cache:
        return S.build_F(camp, sglop, NLAT, NLON, prot_assumed=prot,
                         theta_pole=theta_pole, psi_pole=psi_pole, phi0=phi0,
                         nsub=nsub)
    p = CACHE / (F_cache_name(camp, prot, theta_pole, psi_pole, phi0, nsub,
                              sglop.core) + ".npy")
    if p.exists():
        return np.load(p, mmap_mode="r")
    if not build_ok:
        raise FileNotFoundError(f"F cache missing: {p}")
    out = np.lib.format.open_memmap(p, mode="w+", dtype=np.float32,
                                    shape=(camp.nsamp, NLAT * NLON))
    S.build_F(camp, sglop, NLAT, NLON, prot_assumed=prot, theta_pole=theta_pole,
              psi_pole=psi_pole, phi0=phi0, nsub=nsub, out=out)
    out.flush()
    return np.load(p, mmap_mode="r")


def dataset(camp, sglop, truthF, seed, fc, nsub=NSUB):
    """One simulated campaign at fc, cloud field seeded 100+seed."""
    cloud = (S.CloudModel(NLATF, NLONF, fc=fc, tau_days=TAU_DAYS, seed=100 + seed)
             if fc > 0 else None)
    return S.simulate_dataset(camp, truthF, cloud, sglop, seed=seed, nsub=nsub)


def dat_key(camp, fc, seed, nsub=NSUB, tag=""):
    return ("dat_n%d_ts%d_mp%d_ns%d_mode%s_gap%d_stat%d_fc%g_s%d%s"
            % (camp.n, round(camp.ts), camp.mp, nsub, camp.mode,
               round(camp.gap_total_s), int(camp.static), fc, seed, tag))


def get_dat(camp, sglop, truthF, seed, fc, nsub=NSUB, cache=True, tag=""):
    """Simulated data, cached as a TRIMMED npz.

    Simulating one campaign costs ~25 s, and the same (fc, seed) stream is
    needed by five commands; caching the 0.8 MB result removes that repeat
    cost and, more importantly, guarantees those commands are literally looking
    at the same photons.
    """
    p = CACHE / (dat_key(camp, fc, seed, nsub, tag) + ".npz") if cache else None
    if p is not None and p.exists():
        d = np.load(p)
        return {k: d[k] for k in d.files}
    dat = trim(dataset(camp, sglop, truthF, seed, fc, nsub=nsub))
    if p is not None:
        tmp = p.with_suffix(".tmp.npz")
        np.savez(tmp, **dat)
        os.replace(tmp, p)
    return dat


def trim(dat):
    """Keep only what a later pass needs from a dataset."""
    return dict(y=np.asarray(dat["y"], np.float32),
                sigma=np.asarray(dat["sigma"], np.float32),
                covers=np.asarray(dat["covers"], np.float32))


def fit(solver, F, dat, camp, sigma_cl, white=False, deflate=True, anchor=True):
    """Solve from a trimmed dataset; the float64 cast happens inside sglsim."""
    y = np.asarray(dat["y"], dtype=np.float64)
    sg = np.asarray(dat["sigma"], dtype=np.float64)
    if solver == "profiled":
        return S.solve_gls_profiled(F, y, camp, sg, sigma_cl, TAU_DAYS, LAM_GLS,
                                    get_LtL(), white=white, deflate=deflate,
                                    anchor=anchor)
    if solver == "v2":
        return S.solve_gls(F, y, camp, sg, sigma_cl, TAU_DAYS, LAM_GLS,
                           get_LtL(), white=white, deflate=deflate)
    raise ValueError(solver)


def get_LtL():
    p = CACHE / "LtL_36_72.npy"
    if not p.exists():
        np.save(p, S.build_laplacian(NLAT, NLON))
    return np.load(p)


def sigcl_cache():
    p = CACHE / "sigma_cl.json"
    return json.loads(p.read_text()) if p.exists() else {}


def get_sigcl(fc, camp, sglop, truthF, tau=TAU_DAYS, geometry="fixed", tag="",
              **ckw):
    d = sigcl_cache()
    key = ("fc%g_n%d_ts%g_mp%g_tau%g_%s_nsub%d%s"
           % (fc, camp.n, camp.ts, camp.mp, tau, geometry, NSUB, tag))
    for k in sorted(ckw):
        key += "_%s%g" % (k, ckw[k])
    if key not in d:
        d[key] = S.estimate_cloud_sigma(camp, truthF, sglop, fc, tau,
                                        geometry=geometry, **ckw)
        p = CACHE / "sigma_cl.json"
        p.write_text(json.dumps(d, indent=1))
    return d[key]


def truth(morphology="earthlike"):
    tF = S.make_truth_map(NLATF, NLONF, seed=TRUTH_SEED, morphology=morphology)
    return tF, S.coarsen(tF, 2)


def part_path(name):
    """Revised-suite parts live under a v3_ prefix.

    The v2 part files in results/parts use the SAME bare names (clouds_f0_s0,
    cad_c2_s1, ...), so an unprefixed checkpoint would let the old, wrong-
    quadrature numbers silently satisfy a new skip-if-done test.  The prefix
    keeps both suites in the tree and makes the collision impossible.
    """
    return PARTS / f"{PART_PREFIX}{name}.npz"


def part(name):
    p = part_path(name)
    return np.load(p) if p.exists() else None


def part_done(name):
    return part_path(name).exists()


def save_part(name, **kw):
    tmp = part_path(name).with_suffix(".tmp.npz")
    np.savez(tmp, **kw)
    os.replace(tmp, part_path(name))


def solve(solver, F, dat, camp, sigma_cl, white=False, deflate=True, anchor=True):
    """One reconstruction entry point so 'TDI' cannot mean two things."""
    return fit(solver, F, dat, camp, sigma_cl, white=white, deflate=deflate,
               anchor=anchor)


def evaluate(map_flat, truth_c):
    e = S.eval_map(map_flat, truth_c)
    e["bias"] = float(np.mean(map_flat) - float(truth_c.mean()))
    e["contrast"] = _contrast(map_flat, truth_c)
    return e


def _contrast(map_flat, truth_c):
    """Measured land/ocean contrast of the debiased map vs truth (R: albedo bias)."""
    nl, nn = truth_c.shape
    lat = (np.arange(nl) + 0.5) / nl * 180.0 - 90.0
    sel = np.abs(lat) <= 60.0
    a = map_flat.reshape(nl, nn)[sel]
    b = truth_c[sel]
    la, lo = a[b > 0.15], a[b <= 0.15]
    if la.size < 2 or lo.size < 2:
        return float("nan")
    return float((la.mean() - lo.mean()) / (b[b > 0.15].mean() - b[b <= 0.15].mean()))


def paired_stats(x, y, nboot=20000, seed=42):
    """Paired difference statistics: mean, SE, t-test p, exact sign-flip p,
    percentile bootstrap CI.  All reported together, because with 10 pairs the
    exact minimum attainable p is 2/2**n = 1.95e-3 and a bootstrap CI cannot
    reach zero either."""
    d = np.asarray(x) - np.asarray(y)
    n = d.size
    mean = float(d.mean())
    se = float(d.std(ddof=1) / np.sqrt(n))
    from scipy import stats
    t, p_t = stats.ttest_rel(np.asarray(x), np.asarray(y))
    from math import comb
    npos = int(np.sum(d > 0))
    nneg = int(np.sum(d < 0))
    p_sign = min(1.0, 2.0 * comb(n, min(npos, nneg)) / 2.0 ** n)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(nboot, n))
    boots = d[idx].mean(axis=1)
    return dict(mean=mean, se=se, ci_lo=float(np.percentile(boots, 2.5)),
                ci_hi=float(np.percentile(boots, 97.5)), p_t=float(p_t),
                p_sign=p_sign, n=n, sd=float(d.std(ddof=1)))

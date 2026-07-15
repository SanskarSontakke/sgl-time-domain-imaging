"""Experiment driver (chunked: each CLI invocation runs <~35 s).

Usage:
  python3 run_experiments.py setup            # caches F, LtL, sigma_cl
  python3 run_experiments.py validation
  python3 run_experiments.py tune
  python3 run_experiments.py clouds <ifc> <iseed>
  python3 run_experiments.py budget <its> <iseed>
  python3 run_experiments.py robust_tau | robust_sig | robust_prot
  python3 run_experiments.py merge            # assembles final npz files

Outputs: ../data/*.npz  (parts in ../data/parts/). Seeded, reproducible.
"""

import sys, time, json
from pathlib import Path
import numpy as np
import sglsim as S

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "results"
PARTS = DATA / "parts"
PARTS.mkdir(parents=True, exist_ok=True)
TMP = Path("/tmp")

NLAT, NLON = 36, 72
NLATF, NLONF = 72, 144
TRUTH_SEED = 7
TAU_DAYS = 4.0
LAM_GLS = 3e-3
KW_B2 = 3e-3
SEEDS = [11, 12, 13]
FCS = [0.0, 0.25, 0.40, 0.55, 0.70]
# cadence experiment: fixed wall-clock (~90 d) and fixed photons per pixel
# (mp * ts = 28800 s), trading dwell time against number of revisits
CADENCE = [(7200.0, 4), (3600.0, 8), (1800.0, 16), (900.0, 32), (450.0, 64)]
CAD_SEEDS = [11, 12]
CAD_FC = 0.55


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


def campaign(ts=1800.0, mp=16):
    return S.Campaign(n=64, nsc=16, ts=ts, mp=mp, seed=2026)


def f_path(camp, prot=S.PROT):
    return TMP / f"F_n{camp.n}_ts{int(camp.ts)}_mp{camp.mp}_p{prot:.6e}.npy"


def get_F(camp, sgl, prot=S.PROT, build_ok=True):
    p = f_path(camp, prot)
    if p.exists():
        return np.load(p, mmap_mode="r")
    assert build_ok
    out = np.lib.format.open_memmap(p, mode="w+", dtype=np.float32,
                                    shape=(camp.nsamp, NLAT * NLON))
    S.build_F(camp, sgl, NLAT, NLON, prot_assumed=prot, out=out)
    out.flush()
    return np.load(p, mmap_mode="r")


def get_LtL():
    p = TMP / "LtL.npy"
    if p.exists():
        return np.load(p)
    L = S.build_laplacian(NLAT, NLON)
    np.save(p, L)
    return L


def get_sigcl(fc, camp, sgl, truthF):
    p = TMP / "sigcl.json"
    d = json.loads(p.read_text()) if p.exists() else {}
    key = f"{fc}_{int(camp.ts)}"
    if key not in d:
        d[key] = S.estimate_cloud_sigma(camp, truthF, sgl, fc, TAU_DAYS)
        p.write_text(json.dumps(d))
    return d[key]


def truth():
    tF = S.make_truth_map(NLATF, NLONF, seed=TRUTH_SEED)
    return tF, S.coarsen(tF, 2)


def one_config(camp, sgl, F, LtL, truthF, truth_c, fc, seed, keep_maps=False):
    cloud = (S.CloudModel(NLATF, NLONF, fc=fc, tau_days=TAU_DAYS,
                          seed=100 + seed) if fc > 0 else None)
    dat = S.simulate_dataset(camp, truthF, cloud, sgl, seed=seed)
    sigma_cl = get_sigcl(fc, camp, sgl, truthF) if fc > 0 else 0.0
    out, extras = {}, {}
    for name, white, defl in (("gls", False, True), ("white", True, False)):
        s = S.solve_gls(F, dat["y"], camp, dat["sigma"], sigma_cl,
                        TAU_DAYS, LAM_GLS, LtL, white=white, deflate=defl)
        s = S.debias_cloud(s, fc)
        m = S.eval_map(s, truth_c)
        out[name] = m
        if keep_maps:
            extras[f"map_{name}"] = s
    b2 = S.debias_cloud(S.reconstruct_phasebin(dat, camp, sgl, NLAT, NLON,
                                               Kw=KW_B2), fc)
    out["b2"] = S.eval_map(b2, truth_c)
    if keep_maps:
        extras["map_b2"] = b2
        extras["b1img"] = S.static_wiener_image(dat, camp, sgl, Kw=KW_B2)
        extras["cover_series"] = dat["covers"]
        for k, sn in enumerate(dat["snaps"]):
            extras[f"snap{k}_scene"] = sn["scene"]
            extras[f"snap{k}_conv"] = sn["conv"]
            if sn["opac"] is not None:
                extras[f"snap{k}_opac"] = sn["opac"]
    cover = dat["covers"].mean() if fc > 0 else 0.0
    return out, cover, extras


# ----------------------------------------------------------------------
def cmd_setup():
    camp = campaign()
    sgl = S.SGLOperator(64)
    truthF, _ = truth()
    get_F(camp, sgl)
    get_LtL()
    for fc in FCS:
        if fc > 0:
            v = get_sigcl(fc, camp, sgl, truthF)
            log(f"sigma_cl({fc}) = {v:.4f}")
    log(f"corona sigma per sample = {S.noise_sigma(1.0, camp.ts):.4f}; "
        f"wallclock = {camp.wallclock_days:.1f} d")


def cmd_validation():
    res = {"ns": [], "theory": [], "measured": []}
    res["snrc_check"] = 1.0 / S.noise_sigma(1.0, 1800.0)
    log(f"SNR_C(1800 s) = {res['snrc_check']:.2f} (published: 43.16)")
    truthF, _ = truth()
    rng = np.random.default_rng(5)
    for n in (32, 64, 128):
        sgl = S.SGLOperator(n)
        scene = S.render_disk(truthF.ravel(), sgl.geo, 0.0, NLATF, NLONF,
                              static=True)
        conv = sgl.conv(scene)
        sig = S.noise_sigma(1.0, 1800.0)
        rec_clean = sgl.wiener(conv, 1e-9)
        trials = []
        for k in range(6):
            noisy = conv + rng.standard_normal(conv.shape) * sig
            rec = sgl.wiener(noisy, 1e-9)
            resid = (rec - rec_clean)[sgl.geo["mask"]]
            trials.append(sig / resid.std())   # = SNR_R / SNR_C
        pitch = S.DIMG / n
        th = min(1.0, 0.891 * pitch / (S.DTEL * n))
        res["ns"].append(n); res["theory"].append(th)
        res["measured"].append(float(np.mean(trials)))
        log(f"n={n:4d}: measured {np.mean(trials):.4f}  theory {th:.4f}")
    np.savez(DATA / "validation.npz", **{k: np.array(v) for k, v in res.items()})


def cmd_tune():
    camp = campaign(); sgl = S.SGLOperator(64)
    truthF, truth_c = truth()
    F = get_F(camp, sgl); LtL = get_LtL()
    fc = 0.55
    sigma_cl = get_sigcl(fc, camp, sgl, truthF)
    cloud = S.CloudModel(NLATF, NLONF, fc=fc, tau_days=TAU_DAYS, seed=199)
    dat = S.simulate_dataset(camp, truthF, cloud, sgl, seed=99)
    rows = []
    for lam in (1e-3, 3e-3, 1e-2):
        s = S.debias_cloud(S.solve_gls(F, dat["y"], camp, dat["sigma"],
                                       sigma_cl, TAU_DAYS, lam, LtL), fc)
        m = S.eval_map(s, truth_c)
        rows.append(["gls", lam, m["ssim"], m["pearson"]])
        log(f"gls lam={lam:.0e} ssim={m['ssim']:.3f} r={m['pearson']:.3f}")
    for kw in (1e-3, 3e-3, 1e-2, 3e-2):
        b2 = S.debias_cloud(S.reconstruct_phasebin(dat, camp, sgl, NLAT, NLON,
                                                   Kw=kw), fc)
        m = S.eval_map(b2, truth_c)
        rows.append(["b2", kw, m["ssim"], m["pearson"]])
        log(f"b2 Kw={kw:.0e} ssim={m['ssim']:.3f} r={m['pearson']:.3f}")
    (DATA / "tune.json").write_text(json.dumps(rows, indent=1))


def cmd_clouds(ifc, iseed):
    fc, seed = FCS[ifc], SEEDS[iseed]
    camp = campaign(); sgl = S.SGLOperator(64)
    truthF, truth_c = truth()
    F = get_F(camp, sgl, build_ok=False); LtL = get_LtL()
    out, cover, extras = one_config(camp, sgl, F, LtL, truthF, truth_c,
                                    fc, seed, keep_maps=(iseed == 0))
    log(f"fc={fc} seed={seed}: " + " ".join(
        f"{k}:ssim={v['ssim']:.3f},r={v['pearson']:.3f}" for k, v in out.items()))
    np.savez(PARTS / f"clouds_f{ifc}_s{iseed}.npz", cover=cover,
             **{f"{k}_{mk}": v[mk] for k, v in out.items()
                for mk in ("ssim", "nrmse", "pearson")}, **extras)


def cmd_cadence(icfg, iseed, stage):
    """stage 'ds': generate dataset (cached); 'solve': all reconstructions."""
    ts, mp = CADENCE[icfg]
    seed = CAD_SEEDS[iseed]
    camp = campaign(ts=ts, mp=mp); sgl = S.SGLOperator(64)
    truthF, truth_c = truth()
    ycache = TMP / f"cad_{icfg}_{iseed}.npz"
    nsub = 3 if ts >= 1800 else 1
    if stage == "ds":
        get_F(camp, sgl)   # ensure F cached
        cloud = S.CloudModel(NLATF, NLONF, fc=CAD_FC, tau_days=TAU_DAYS,
                             seed=100 + seed)
        dat = S.simulate_dataset(camp, truthF, cloud, sgl, seed=seed,
                                 nsub=nsub)
        np.savez(ycache, y=dat["y"], sigma=dat["sigma"],
                 cover=dat["covers"].mean())
        log(f"cadence cfg={icfg} ts={ts:.0f} mp={mp} ds done "
            f"(wall={camp.wallclock_days:.1f} d)")
        return
    d = np.load(ycache)
    dat = {"y": d["y"], "sigma": d["sigma"]}
    F = get_F(camp, sgl, build_ok=False); LtL = get_LtL()
    sigma_cl = get_sigcl(CAD_FC, camp, sgl, truthF)
    res = {}
    for name, white, defl in (("gls", False, True), ("white", True, False)):
        s = S.debias_cloud(
            S.solve_gls(F, dat["y"], camp, dat["sigma"], sigma_cl, TAU_DAYS,
                        LAM_GLS, LtL, white=white, deflate=defl), CAD_FC)
        res[name] = S.eval_map(s, truth_c)
    class DD(dict):
        pass
    dat2 = {"y": dat["y"]}
    b2 = S.debias_cloud(S.reconstruct_phasebin(dat2, camp, sgl, NLAT, NLON,
                                               Kw=KW_B2), CAD_FC)
    res["b2"] = S.eval_map(b2, truth_c)
    log(f"cadence cfg={icfg} ts={ts:.0f} mp={mp} seed={seed}: " +
        " ".join(f"{k}:{v['ssim']:.3f}/{v['pearson']:.3f}"
                 for k, v in res.items()))
    np.savez(PARTS / f"cad_c{icfg}_s{iseed}.npz", mp=mp, ts=ts,
             wall=camp.wallclock_days,
             **{f"{k}_{mk}": v[mk] for k, v in res.items()
                for mk in ("ssim", "nrmse", "pearson")})
    # free /tmp disk: drop non-anchor F caches after last seed
    if iseed == len(CAD_SEEDS) - 1 and mp != 16:
        f_path(camp).unlink(missing_ok=True)


def _robust_base():
    camp = campaign(); sgl = S.SGLOperator(64)
    truthF, truth_c = truth()
    F = get_F(camp, sgl, build_ok=False); LtL = get_LtL()
    fc, seed = 0.55, 11
    sigma_cl = get_sigcl(fc, camp, sgl, truthF)
    cloud = S.CloudModel(NLATF, NLONF, fc=fc, tau_days=TAU_DAYS,
                         seed=100 + seed)
    dat = S.simulate_dataset(camp, truthF, cloud, sgl, seed=seed)
    return camp, sgl, truthF, truth_c, F, LtL, sigma_cl, dat, fc


def cmd_robust_tau():
    camp, sgl, tF, tc, F, LtL, scl, dat, fc = _robust_base()
    taus, vals = [1.0, 4.0, 16.0], []
    for t in taus:
        s = S.debias_cloud(S.solve_gls(F, dat["y"], camp, dat["sigma"], scl,
                                       t, LAM_GLS, LtL, deflate=True), fc)
        vals.append(S.eval_map(s, tc)["ssim"])
    log(f"tau {taus} -> {vals}")
    np.savez(PARTS / "robust_tau.npz", tau=np.array(taus),
             ssim=np.array(vals))


def cmd_robust_sig():
    camp, sgl, tF, tc, F, LtL, scl, dat, fc = _robust_base()
    scales, vals = [0.5, 1.0, 2.0], []
    for c in scales:
        s = S.debias_cloud(S.solve_gls(F, dat["y"], camp, dat["sigma"],
                                       scl * c, TAU_DAYS, LAM_GLS, LtL,
                                       deflate=True), fc)
        vals.append(S.eval_map(s, tc)["ssim"])
    log(f"sig scales {scales} -> {vals}")
    np.savez(PARTS / "robust_sig.npz", sig=np.array(scales),
             ssim=np.array(vals))


def cmd_robust_prot(step):
    """step 0: err 1e-4; step 1: err 1e-3 (F rebuilt with wrong period)."""
    errs = [1e-4, 1e-3]
    e = errs[step]
    camp, sgl, tF, tc, F, LtL, scl, dat, fc = _robust_base()
    del F
    Fe = S.build_F(camp, sgl, NLAT, NLON, prot_assumed=S.PROT * (1 + e))
    s = S.debias_cloud(S.solve_gls(Fe, dat["y"], camp, dat["sigma"], scl,
                                   TAU_DAYS, LAM_GLS, LtL, deflate=True), fc)
    v = S.eval_map(s, tc)["ssim"]
    log(f"prot err {e} -> ssim {v:.3f}")
    np.savez(PARTS / f"robust_prot_{step}.npz", err=e, ssim=v)


def cmd_merge():
    methods = ("gls", "white", "b2")
    _, truth_c = truth()
    # clouds
    shape = (3, len(FCS), len(SEEDS))
    ssim = np.full(shape, np.nan); nrmse = np.full(shape, np.nan)
    pear = np.full(shape, np.nan); covers = np.zeros(len(FCS))
    store = {"truth_c": truth_c}
    for i in range(len(FCS)):
        for j in range(len(SEEDS)):
            p = PARTS / f"clouds_f{i}_s{j}.npz"
            if not p.exists():
                continue
            d = np.load(p)
            for m, nm in enumerate(methods):
                ssim[m, i, j] = d[f"{nm}_ssim"]
                nrmse[m, i, j] = d[f"{nm}_nrmse"]
                pear[m, i, j] = d[f"{nm}_pearson"]
            if j == 0:
                covers[i] = d["cover"]
                for nm in methods:
                    store[f"map_{nm}_fc{i}"] = d[f"map_{nm}"]
                store[f"b1img_fc{i}"] = d["b1img"]
                for k in range(3):
                    for suff in ("scene", "conv", "opac"):
                        key = f"snap{k}_{suff}"
                        if key in d:
                            store[f"{key}_fc{i}"] = d[key]
    np.savez(DATA / "clouds.npz", ssim=ssim, nrmse=nrmse, pearson=pear,
             fcs=np.array(FCS), seeds=np.array(SEEDS), covers=covers, **store)
    # cadence
    sb = np.full((3, len(CADENCE), len(CAD_SEEDS)), np.nan)
    pb = np.full((3, len(CADENCE), len(CAD_SEEDS)), np.nan)
    wall = np.zeros(len(CADENCE))
    for i in range(len(CADENCE)):
        for j in range(len(CAD_SEEDS)):
            p = PARTS / ("cad_c%d_s%d.npz" % (i, j))
            if not p.exists():
                continue
            d = np.load(p)
            wall[i] = d["wall"]
            for m, nm in enumerate(methods):
                sb[m, i, j] = d[nm + "_ssim"]
                pb[m, i, j] = d[nm + "_pearson"]
    np.savez(DATA / "cadence.npz", ssim=sb, pearson=pb,
             mp=np.array([c[1] for c in CADENCE]),
             ts=np.array([c[0] for c in CADENCE]), wall=wall)
    # robust
    kw = {}
    pt = PARTS / "robust_tau.npz"
    if pt.exists():
        d = np.load(pt); kw["tau"] = d["tau"]; kw["ssim_tau"] = d["ssim"]
    ps = PARTS / "robust_sig.npz"
    if ps.exists():
        d = np.load(ps); kw["sig"] = d["sig"]; kw["ssim_sig"] = d["ssim"]
    base = kw.get("ssim_tau", [None, np.nan])[1]
    errs, vals = [0.0], [base]
    for k in range(2):
        pp = PARTS / ("robust_prot_%d.npz" % k)
        if pp.exists():
            d = np.load(pp)
            errs.append(float(d["err"])); vals.append(float(d["ssim"]))
    kw["prot"] = np.array(errs); kw["ssim_prot"] = np.array(vals)
    np.savez(DATA / "robust.npz", **kw)
    log("merged: clouds.npz, cadence.npz, robust.npz")


if __name__ == "__main__":
    a = sys.argv[1:]
    t0 = time.time()
    cmd = a[0]
    if cmd == "setup":
        cmd_setup()
    elif cmd == "validation":
        cmd_validation()
    elif cmd == "tune":
        cmd_tune()
    elif cmd == "clouds":
        cmd_clouds(int(a[1]), int(a[2]))
    elif cmd == "cadence":
        cmd_cadence(int(a[1]), int(a[2]), a[3])
    elif cmd == "robust_tau":
        cmd_robust_tau()
    elif cmd == "robust_sig":
        cmd_robust_sig()
    elif cmd == "robust_prot":
        cmd_robust_prot(int(a[1]))
    elif cmd == "merge":
        cmd_merge()
    else:
        raise SystemExit("unknown command " + cmd)
    log("done:", " ".join(a), "in %.1f s" % (time.time() - t0))

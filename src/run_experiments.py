"""Revised experiment driver (checkpointed, resumable, single-source conventions).

Usage:  python run_experiments.py <command> [args]

Commands
  setup                 cached operators + ledger + sigma_cl audit
  quadrature            exposure-quadrature convergence table (3-node smear)
  ledger                two resource-consistent cadence arms, analytic only
  validation            photometric budget + finite-cell kernel convergence
  clouds <i_fc>         cloud-fraction sweep, all seeds, one fraction
  cadence <arm> <i_cfg> cadence law, arm = photons | wallclock, all seeds
  components            solver/deflation ablation on identical data
  robust_debias         affine debiasing mis-specification (absolute errors)
  robust_clim           structured climatology variants
  robust_geom           spin-pole tilt and assumed-phase sensitivity
  robust_prof           profile-likelihood grid (period x phase)
  resolution            real-harmonic r(l) with quadrature error bound
  nulls_cloud           shared cloud-only physical null ensemble
  nulls                 land-ocean d' vs physical + label-permutation nulls
  systematics           quantitative coronal/instrumental injection
  diagnostics           deflation/information diagnostics (93.75% claim)
  precision             numerical precision audit
  merge                 parts -> shipped results/*.npz + audit.json

Why the commands loop seeds internally: a float32 forward operator at n = 64 is
0.68 GB and takes ~45 s to build, and one simulated campaign takes ~25 s.  The
operator is therefore built ONCE per process and reused for every seed, and the
simulations are cached in results/cache so that "the same photons" genuinely
means the same array for every command (referee C8/C9, editor reproducibility).
Every part file records the seed, campaign mode, quadrature order and solver.
"""

import json
import sys
import time

import numpy as np
import sglsim as S
import expcommon as E

log = E.log


# ----------------------------------------------------------------------
def cmd_setup():
    LtL = E.get_LtL()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    camp_p = E.campaign()
    camp_w = E.campaign(mode="wallclock")
    log(f"arm A (photons, mp*ts=8h/position): ts={camp_p.ts:.1f}s "
        f"wall={camp_p.wallclock_days:.2f}d duty={camp_p.duty_cycle:.4f} "
        f"exposure={camp_p.exposure_days:.2f}d overhead={camp_p.overhead_days:.2f}d")
    log(f"arm B (wallclock<=90d): ts={camp_w.ts:.1f}s wall={camp_w.wallclock_days:.2f}d "
        f"photons/position={camp_w.mp * camp_w.ts / 3600.0:.2f}h")
    t0 = time.time()
    F = E.get_F(camp_p, sglop)
    log(f"fiducial F {F.shape} {F.dtype} in {time.time() - t0:.1f}s")
    for geo in ("fixed", "varying"):
        v = E.get_sigcl(E.FC, camp_p, sglop, truthF, geometry=geo)
        log(f"sigma_cl [{geo}] = {v:.6f}  "
            f"({v / S.noise_sigma(1.0, camp_p.ts):.2f}x photon sigma)")
    log(f"laplacian {LtL.shape}, NSUB={E.NSUB}, seeds={E.SEEDS}")


# ----------------------------------------------------------------------
def cmd_quadrature():
    """Exact vs implemented exposure response: the v2 3-node equal-spaced
    sub-exposure average is not a convergent quadrature of the smear kernel."""
    ts_list = [7200.0, 3600.0, 1800.0, 900.0, 450.0]
    nsubs = (3, 5, 8, 16, 32)
    conv = S.exposure_quadrature_convergence(ts_list, mmax=40, nsubs=nsubs)
    m = np.arange(1, 41)
    exact = np.array([S.exposure_response(ts, mm) for ts in ts_list for mm in m],
                     float).reshape(len(ts_list), 40)
    impl = {ns_: np.array([S.exposure_response(ts, mm, nsub=ns_)
                           for ts in ts_list for mm in m], float
                          ).reshape(len(ts_list), 40) for ns_ in nsubs}
    nodes3 = (np.array([-1 / 3.0, 0.0, 1 / 3.0]) * 2.0)   # equal-spaced, +-ts/3

    def equal3(ts, mm):
        """The rule v2 actually used: three EQUAL-WEIGHT sub-exposures at
        -ts/3, 0, +ts/3.  Note this is NOT a Gauss-Legendre 3-node rule; its
        node spacing is ts/3, so at ts = 7200 s it samples every 2400 s = 10 deg
        of longitude, which is exactly the period of azimuthal harmonic m = 36.
        The exact sinc annihilates m = 36 there; this rule passes it at unit
        gain."""
        Om = 2.0 * np.pi / S.PROT
        return float(np.mean(np.cos(mm * Om * nodes3 * ts / 2.0)))

    eq3 = np.array([[equal3(ts, mm) for mm in m] for ts in ts_list])
    eq3_err = np.array([max(abs(eq3[i, j] - exact[i, j]) for j in range(len(m)))
                        for i in range(len(ts_list))])
    max_err = np.array([conv[ns_] for ns_ in nsubs])      # (nsub, ts)
    ex = dict(m=[20, 36],
              exact=[float(S.exposure_response(7200.0, 20)),
                     float(S.exposure_response(7200.0, 36))],
              equal3=[equal3(7200.0, mm) for mm in (20, 36)],
              gl3=[float(S.exposure_response(7200.0, mm, nsub=3)) for mm in (20, 36)],
              gl16=[float(S.exposure_response(7200.0, mm, nsub=16)) for mm in (20, 36)])
    np.savez(E.DATA / "quadrature.npz", ts=np.array(ts_list), m=m, exact=exact,
             nsubs=np.array(nsubs), eq3=eq3, eq3_max_err=eq3_err,
             gl_max_err=max_err,
             **{f"gl{ns_}": v for ns_, v in impl.items()})
    kc = S.kinematic_check()
    (E.DATA / "kinematics.json").write_text(json.dumps(kc, indent=2, default=float))
    # shapes: exact/gl* are (ts, m); eq3_max_err is (ts,); gl_max_err is (nsub, ts)
    log(f"equal-3 (v2 rule): max |response error| over m<=40, by dwell "
        + " ".join(f"{t:.0f}s:{e:.2e}" for t, e in zip(ts_list, eq3_err)))
    for i, ns_ in enumerate(nsubs):
        log(f"GL nsub={ns_:2d}: max |response error| by dwell "
            + " ".join(f"{t:.0f}s:{e:.2e}" for t, e in zip(ts_list, max_err[i])))
    log(f"P=24h ts=7200s: exact m=36 {ex['exact'][1]:+.6f} | equal-3 "
        f"{ex['equal3'][1]:+.6f} | GL-3 {ex['gl3'][1]:+.6f} | GL-16 "
        f"{ex['gl16'][1]:+.6f}")
    log(f"kinematics: {kc}")


# ----------------------------------------------------------------------
def cmd_ledger():
    rows = []
    for ts, mp in E.ARM_PHOTONS:
        c = E.campaign(ts=ts, mp=mp, mode="photons")
        rows.append(dict(arm="photons", mp=mp, ts=c.ts, exposure_days=c.exposure_days,
                         overhead_days=c.overhead_days, gap_days=c.gap_days,
                         wall=c.wallclock_days, photons_per_pixel_h=mp * c.ts / 3600.0,
                         duty=c.duty_cycle, fits_90d=bool(c.wallclock_days <= E.ARM_WALL)))
    for _, mp in E.ARM_PHOTONS:
        c = E.campaign(ts=1800.0, mp=mp, mode="wallclock")
        rows.append(dict(arm="wallclock", mp=mp, ts=c.ts, exposure_days=c.exposure_days,
                         overhead_days=c.overhead_days, gap_days=c.gap_days,
                         wall=c.wallclock_days, photons_per_pixel_h=mp * c.ts / 3600.0,
                         duty=c.duty_cycle, fits_90d=True))
    # effective number of INDEPENDENT cloud looks: the mp visits to one raster
    # position are spaced by the FULL pass time (nbin*slot_wall), not by ts.
    # Var(mean of mp correlated samples) = (sigma^2/mp^2) [mp + 2 sum_k (mp-k)
    # rho_k], so N_eff = mp^2 / (mp + 2 sum_k (mp-k) rho_k).  The (mp-k) pair
    # weight is essential: dropping it (an earlier version of this ledger did)
    # overstates N_eff by roughly a factor mp and would falsely suggest that the
    # mp revisits are independent even at mp = 64.
    taus = [4.0, 2.0, 1.0]

    def _neff(ts, mp, tau):
        d = S.effective_independent_looks(ts, mp, tau, camp=E.campaign(ts=ts, mp=mp))
        return d["n_eff"], d["spacing_days"], d["rho_lag1"]
    neff, spacing, rho1 = {}, {}, {}
    for tau in taus:
        neff[tau], spacing[tau], rho1[tau] = [], [], []
        for ts, mp in E.ARM_PHOTONS:
            n, dt, r = _neff(ts, mp, tau)
            neff[tau].append(n); spacing[tau].append(dt); rho1[tau].append(r)
    np.savez(E.DATA / "ledger.npz",
             arm=np.array([r["arm"] for r in rows]),
             mp=np.array([r["mp"] for r in rows]),
             ts=np.array([r["ts"] for r in rows]),
             exposure_days=np.array([r["exposure_days"] for r in rows]),
             overhead_days=np.array([r["overhead_days"] for r in rows]),
             gap_days=np.array([r["gap_days"] for r in rows]),
             wall=np.array([r["wall"] for r in rows]),
             photons=np.array([r["photons_per_pixel_h"] for r in rows]),
             duty=np.array([r["duty"] for r in rows]),
             fits90=np.array([r["fits_90d"] for r in rows]),
             neff_tau=np.array(sorted(taus)),
             neff_mp=np.array([r["mp"] for r in rows if r["arm"] == "photons"]),
             neff=np.array([neff[t] for t in sorted(taus)]),
             neff_spacing_d=np.array([spacing[t] for t in sorted(taus)]),
             neff_rho1=np.array([rho1[t] for t in sorted(taus)]))
    for r in rows:
        log(f"{r['arm']:9s} mp={r['mp']:3d} ts={r['ts']:8.1f}s photons={r['photons_per_pixel_h']:.2f}h "
            f"wall={r['wall']:.2f}d fits90={r['fits_90d']}")
    log(f"N_eff(tau) by mp: {neff}")
    log(f"inter-look spacing (d): {spacing}; lag-1 OU correlation: {rho1}")


# ----------------------------------------------------------------------
def cmd_validation():
    """Photometric budget, reconstruction-noise scaling, and the FINITE-CELL
    kernel test (R21): point sample vs cell average."""
    res = {"ns": [], "theory": [], "measured": [], "measured_sd": []}
    sig = S.noise_sigma(1.0, 1800.0)
    res["snr_c"] = 1.0 / sig
    res["sigma_1800"] = sig
    res["nexo"] = S.QEXO * 1800.0
    res["ncor"] = S.QCOR * 1800.0
    # Normalisation convention audit: the Lambert disk-integral factor
    # 8/(3*pi) = 0.8488 multiplies the sub-stellar-normalised signal.  Stating
    # SNR_C with and without it is the difference between 43.16 and 36.63.
    res["eight_over_3pi"] = 8.0 / (3.0 * np.pi)
    res["snr_c_no_mu_norm"] = float(res["snr_c"] * (8.0 / (3.0 * np.pi)))
    log(f"SNR_C(1800s, s=1) = {res['snr_c']:.4f} (published 43.16); sigma={sig:.7f}")
    log(f"8/(3*pi) = {8.0 / (3.0 * np.pi):.6f}; Q_exo={S.QEXO:.4g} Q_cor={S.QCOR:.4g} "
        f"ratio={S.QCOR / S.QEXO:.4g}")
    rng = np.random.default_rng(5)
    truthF, truth_c = E.truth()
    for n in (32, 64, 128):
        sgl = S.SGLOperator(n)
        scene = S.render_disk(truthF.ravel(), sgl.geo, 0.0, E.NLATF, E.NLONF, static=True)
        conv = sgl.conv(scene)
        rec_clean = sgl.wiener(conv, 1e-9)
        trials = []
        for _ in range(6):
            noisy = conv + rng.standard_normal(conv.shape) * sig
            resid = (sgl.wiener(noisy, 1e-9) - rec_clean)[sgl.geo["mask"]]
            trials.append(sig / resid.std())
        pitch = S.DIMG / n
        th = min(1.0, 0.891 * pitch / (S.DTEL * n))
        res["ns"].append(n); res["theory"].append(th)
        res["measured"].append(float(np.mean(trials)))
        res["measured_sd"].append(float(np.std(trials)))
        log(f"n={n:4d}: measured {res['measured'][-1]:.4f} theory {th:.4f} "
            f"(ratio {res['measured'][-1] / th:.3f}, sd {res['measured_sd'][-1]:.3f})")
    np.savez(E.DATA / "validation.npz",
             **{k: np.array(v) for k, v in res.items() if v})

    # --- finite-cell kernel convergence on the KERNEL ITSELF (referee R21)
    out = {}
    for n in (16, 32, 64, 128):
        pitch = S.DIMG / n
        K_pt = S.make_kernel(n, pitch, core="point")
        K_cm = S.make_kernel(n, pitch, core="cellmean")
        nq = 24
        u = (np.arange(nq) + 0.5) / nq - 0.5
        core_ref = np.zeros((5, 5))
        for iy in range(-2, 3):
            for ix in range(-2, 3):
                X = (np.array([ix]) + u[None, :]) * pitch
                Y = (iy + u[:, None]) * pitch
                R = np.hypot(Y[..., None], X[..., None])
                with np.errstate(divide="ignore", invalid="ignore"):
                    kk = np.where(R > 0, S.DTEL / (4.0 * R), 0.0)
                core_ref[iy + 2, ix + 2] = kk.mean()
        out[n] = dict(pitch=pitch, K00_point=float(K_pt[n, n]),
                      K00_cellmean=float(K_cm[n, n]), K00_ref=float(core_ref[2, 2]),
                      cellmean_formula=float(S.DTEL * np.log(1 + np.sqrt(2)) / pitch),
                      offdiag_rel_err_point=float(np.abs(K_pt[n, n + 1] / core_ref[2, 3] - 1)),
                      offdiag_rel_err_cellmean=float(np.abs(K_cm[n, n + 1] / core_ref[2, 3] - 1)),
                      point_over_cellmean=float(K_pt[n, n] / K_cm[n, n]))
        log(f"n={n:4d} pitch={pitch:8.2f} m: K00 point={K_pt[n, n]:.5f} "
            f"cellmean={K_cm[n, n]:.5f} brute={core_ref[2, 2]:.5f} "
            f"ratio={out[n]['point_over_cellmean']:.1f}x")
    (E.DATA / "kernel_convergence.json").write_text(json.dumps(out, indent=2, default=float))

    # --- both cores on a uniform disk, and the RECONSTRUCTION consequence
    disk = []
    for n in (16, 32, 64):
        sgl = S.SGLOperator(n)
        gl = S.SGLOperator(n, core="cellmean")
        img = np.ones((n, n)) * sgl.geo["mask"]
        disk.append(dict(n=n, point=float(sgl.conv(img)[n // 2, n // 2]),
                         cellmean=float(gl.conv(img)[n // 2, n // 2])))
        log(f"uniform disk centre sample n={n}: point {disk[-1]['point']:.4f} "
            f"cellmean {disk[-1]['cellmean']:.4f}")
    (E.DATA / "uniform_disk.json").write_text(json.dumps(disk, indent=2, default=float))

    # --- cloud-free reconstruction, point vs cellmean core (the audit that
    #     justifies KEEPING the point core rather than silently switching)
    camp = E.campaign()
    truthF, truth_c = E.truth()
    rows = {}
    for core in ("point", "cellmean"):
        sglop = E.sgl(core)
        dat = E.dataset(camp, sglop, truthF, 11, 0.0)
        F = E.get_F(camp, sglop, cache=False)
        s = E.fit("v2", F, dat, camp, 0.0, white=True, deflate=False)
        rows[core] = E.evaluate(s, truth_c)
        log(f"cloud-free n=64 core={core:8s}: r={rows[core]['pearson']:.4f} "
            f"ssim={rows[core]['ssim']:.4f} nrmse={rows[core]['nrmse']:.4f}")
    (E.DATA / "core_ablation.json").write_text(json.dumps(rows, indent=2, default=float))


# ----------------------------------------------------------------------
def _fits(F, dat, camp, sigma_cl, fc, truth_c, sglop, want=("profiled", "v2",
                                                            "white", "b2", "b1",
                                                            "b2coarse")):
    """All estimators on ONE dataset; returns (metrics-by-name, maps-by-name)."""
    out, maps = {}, {}
    for sv in ("profiled", "v2"):
        if sv not in want:
            continue
        s = E.fit(sv, F, dat, camp, sigma_cl)
        m = S.debias_cloud(s, fc)
        out[sv] = E.evaluate(m, truth_c); maps[sv] = m
    if "white" in want:
        s = E.fit("profiled", F, dat, camp, sigma_cl, white=True, deflate=False)
        m = S.debias_cloud(s, fc)
        out["white"] = E.evaluate(m, truth_c); maps["white"] = m
    if "b2" in want:
        # B2 = phase-registered coadds, NBINS_B2 bins (see expcommon for why the
        # bin count is not free: a coarse binning averages over rotation and the
        # baseline collapses for a reason that has nothing to do with TDI).
        b2 = S.reconstruct_phasebin(dat, camp, sglop, E.NLAT, E.NLON,
                                    nbins=E.NBINS_B2, Kw=E.KW_B2)
        m = S.debias_cloud(np.asarray(b2).ravel(), fc)
        out["b2"] = E.evaluate(m, truth_c); maps["b2"] = m
    if "b2coarse" in want:
        b2 = S.reconstruct_phasebin(dat, camp, sglop, E.NLAT, E.NLON,
                                    nbins=E.NBINS_B2_COARSE, Kw=E.KW_B2)
        m = S.debias_cloud(np.asarray(b2).ravel(), fc)
        out["b2coarse"] = E.evaluate(m, truth_c); maps["b2coarse"] = m
    if "b1" in want:
        # B1 = PHASE-BLIND coadd: the same registration-free pipeline as B2 with
        # a single phase bin.  This is the honest way to put a static image on
        # the surface grid -- S.static_wiener_image returns an n x n image-plane
        # map, which has no defined correlation against a lat/lon truth field.
        b1 = S.reconstruct_phasebin(dat, camp, sglop, E.NLAT, E.NLON, nbins=1,
                                    Kw=E.KW_B2)
        m = S.debias_cloud(np.asarray(b1).ravel(), fc)
        out["b1"] = E.evaluate(m, truth_c); maps["b1"] = m
    return out, maps


def _flat(d):
    return {f"{k}_{m}": v for k, r in d.items() for m, v in r.items()}


# ----------------------------------------------------------------------
def cmd_clouds(i_fc):
    """Cloud-fraction sweep on matched GL-16 data, all seeds, ONE operator."""
    i_fc = int(i_fc)
    fc = E.FCS[i_fc]
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    F = E.get_F(camp, sglop)
    sigma_cl = E.get_sigcl(fc, camp, sglop, truthF) if fc > 0 else 0.0
    for j, seed in enumerate(E.SEEDS):
        name = f"clouds_f{i_fc}_s{j}"
        if E.part_done(name):
            log(f"{name} exists, skipping"); continue
        dat = E.get_dat(camp, sglop, truthF, seed, fc)
        mets, maps = _fits(F, dat, camp, sigma_cl, fc, truth_c, sglop)
        E.save_part(name, fc=fc, cover=float(dat["covers"].mean()), seed=seed,
                    nsub=E.NSUB, sigma_cl=sigma_cl, mode=camp.mode, ts=camp.ts,
                    mp=camp.mp, solver="profiled(anchored R11)",
                    **_flat(mets), **{f"map_{k}": v for k, v in maps.items()})
        log(f"{name} fc={fc:g} cover={dat['covers'].mean():.3f} "
            f"profiled r={mets['profiled']['pearson']:.4f} "
            f"ssim={mets['profiled']['ssim']:.4f} | v2 {mets['v2']['pearson']:.4f} "
            f"| white {mets['white']['pearson']:.4f} | b2 {mets['b2']['pearson']:.4f}")


# ----------------------------------------------------------------------
def cmd_cadence(arm, i_cfg):
    """Cadence law for one arm and one configuration, all seeds.

    The forward operator is built IN RAM (cache=False): there are ten distinct
    (arm, config) operators and 10 x 0.68 GB does not fit the sandbox disk.
    """
    arm = arm if arm in ("photons", "wallclock") else "photons"
    i_cfg = int(i_cfg)
    ts, mp = E.ARM_PHOTONS[i_cfg]
    camp = E.campaign(ts=ts if arm == "photons" else 1800.0, mp=mp, mode=arm)
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    F = E.get_F(camp, sglop, cache=False)
    sigma_cl = E.get_sigcl(E.FC, camp, sglop, truthF)
    for j, seed in enumerate(E.CAD_SEEDS):
        name = f"cad_{arm}_c{i_cfg}_s{j}"
        if E.part_done(name):
            log(f"{name} exists, skipping"); continue
        dat = E.get_dat(camp, sglop, truthF, seed, E.FC)
        mets, maps = _fits(F, dat, camp, sigma_cl, E.FC, truth_c, sglop,
                           want=("profiled", "v2", "white", "b2", "b2coarse", "b1"))
        E.save_part(name, arm=arm, mp=mp, ts=camp.ts, seed=seed,
                    wall=camp.wallclock_days, duty=camp.duty_cycle,
                    photons_h=mp * camp.ts / 3600.0, exposure_days=camp.exposure_days,
                    overhead_days=camp.overhead_days, nsub=E.NSUB,
                    sigma_cl=sigma_cl, cover=float(dat["covers"].mean()),
                    **_flat(mets), **{f"map_{k}": v for k, v in maps.items()})
        log(f"{name} mp={mp:2d} ({arm}) ts={camp.ts:.1f}s "
            f"wall={camp.wallclock_days:.2f}d r: profiled "
            f"{mets['profiled']['pearson']:.4f} v2 {mets['v2']['pearson']:.4f} "
            f"white {mets['white']['pearson']:.4f} b2 {mets['b2']['pearson']:.4f} "
            f"b1 {mets['b1']['pearson']:.4f}")


# ----------------------------------------------------------------------
def cmd_cadence_control(arm, i_cfg, kind):
    """Causal controls for the cadence law, per arm (referee C6).

    v2 quoted r_cf and r_iid columns that were never produced by the shipped
    pipeline.  Here the two controls use the SAME campaign objects, the same
    seeds and the same estimator as cmd_cadence:

      cf   cloud-free scene  -> is the cadence trend a conditioning artifact?
      iid  per-pass independent clouds, scored with the OU covariance the
           estimator assumes -> does the trend need only INDEPENDENT weather
           sampling, or the OU correlation structure itself?

    sigma_cl is held at the OU value for the nominal fc in the iid arm, so the
    only thing that changes is the temporal structure of the weather, not the
    assumed noise level.
    """
    arm = arm if arm in ("photons", "wallclock") else "photons"
    i_cfg = int(i_cfg)
    kind = kind if kind in ("cf", "iid") else "cf"
    ts, mp = E.ARM_PHOTONS[i_cfg]
    camp = E.campaign(ts=ts if arm == "photons" else 1800.0, mp=mp, mode=arm)
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    F = E.get_F(camp, sglop, cache=False)
    sigma_cl = E.get_sigcl(E.FC, camp, sglop, truthF)
    for j, seed in enumerate(E.CAD_SEEDS):
        name = f"cadctl_{arm}_c{i_cfg}_{kind}_s{j}"
        if E.part_done(name):
            log(f"{name} exists, skipping"); continue
        if kind == "cf":
            dat = E.get_dat(camp, sglop, truthF, seed, 0.0)
            sc, fc_debias = 0.0, 0.0
        else:
            cl = S.ExtendedCloudModel(E.NLATF, E.NLONF, fc=E.FC,
                                      tau_days=E.TAU_DAYS, seed=100 + seed,
                                      iid_per_pass=True)
            dat = S.simulate_dataset(camp, truthF, cl, sglop, seed=seed,
                                     nsub=E.NSUB)
            dat = E.trim(dat)
            sc, fc_debias = sigma_cl, E.FC
        s = E.fit("profiled", F, dat, camp, sc)
        e = E.evaluate(S.debias_cloud(s, fc_debias), truth_c)
        E.save_part(name, arm=arm, kind=kind, mp=mp, ts=camp.ts, seed=seed,
                    wall=camp.wallclock_days, duty=camp.duty_cycle,
                    photons_h=mp * camp.ts / 3600.0, sigma_cl_used=sc,
                    cover=float(dat["covers"].mean()), **e)
        log(f"{name} mp={mp:2d} ({arm}/{kind}) cover={dat['covers'].mean():.3f} "
            f"r={e['pearson']:.4f} ssim={e['ssim']:.4f} bias={e['bias']:+.4f}")


# ----------------------------------------------------------------------
def cmd_components():
    """Solver-component ablation on identical data, all seeds (referee C4, C8):

      A  time-dependent F, white covariance, no slot handling
      B  time-dependent F, OU whitening, no slot handling
      C  v2 approximate deflation (per-slot mean + sqrt(1-1/Nsc) rescale)
      D  EXACT anchored nuisance profiling, white (referee eq. R11 + sum a=0)
      E  free (un-anchored) profiling  -> shows the constant-mode degeneracy
      F  full TDI = D with OU whitening
    """
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    F = E.get_F(camp, sglop)
    LtL = E.get_LtL()
    sigma_cl = E.get_sigcl(E.FC, camp, sglop, truthF)
    runs = {
        "A_white_nodefl": lambda y, sg: S.solve_gls(F, y, camp, sg, sigma_cl,
                                                    E.TAU_DAYS, E.LAM_GLS, LtL,
                                                    white=True),
        "B_ou_nodefl": lambda y, sg: S.solve_gls(F, y, camp, sg, sigma_cl,
                                                 E.TAU_DAYS, E.LAM_GLS, LtL),
        "C_v2_deflate": lambda y, sg: S.solve_gls(F, y, camp, sg, sigma_cl,
                                                  E.TAU_DAYS, E.LAM_GLS, LtL,
                                                  deflate=True),
        "D_profiled_anchor": lambda y, sg: S.solve_gls_profiled(F, y, camp, sg,
                                                                sigma_cl,
                                                                E.TAU_DAYS,
                                                                E.LAM_GLS, LtL,
                                                                white=True),
        "E_profiled_free": lambda y, sg: S.solve_gls_profiled(F, y, camp, sg,
                                                              sigma_cl, E.TAU_DAYS,
                                                              E.LAM_GLS, LtL,
                                                              white=True, anchor=False),
        "F_full_tdi": lambda y, sg: S.solve_gls_profiled(F, y, camp, sg, sigma_cl,
                                                         E.TAU_DAYS, E.LAM_GLS, LtL),
    }
    for j, seed in enumerate(E.SEEDS):
        name = f"comp_s{j}"
        if E.part_done(name):
            log(f"{name} exists, skipping"); continue
        dat = E.get_dat(camp, sglop, truthF, seed, E.FC)
        y = np.asarray(dat["y"], np.float64); sg = np.asarray(dat["sigma"], np.float64)
        out, maps = {}, {}
        for k, fn in runs.items():
            s = fn(y, sg)
            m = S.debias_cloud(s, E.FC)
            out[k] = E.evaluate(m, truth_c); maps[k] = m
            log(f"  {k:18s} r={out[k]['pearson']:+.4f} ssim={out[k]['ssim']:+.4f} "
                f"bias={out[k]['bias']:+.4f} |s|={np.linalg.norm(s):.4e}")
        ref = maps["D_profiled_anchor"]
        dev = {k: float(np.linalg.norm(v - ref) / np.linalg.norm(ref))
               for k, v in maps.items()}
        E.save_part(name, seed=seed, nsub=E.NSUB, sigma_cl=sigma_cl,
                    **_flat(out), **{f"reldev_{k}": v for k, v in dev.items()},
                    map_D=ref, map_C=maps["C_v2_deflate"],
                    map_F=maps["F_full_tdi"], map_E=maps["E_profiled_free"],
                    norm_D=float(np.linalg.norm(ref)),
                    **{f"norm_{k}": float(np.linalg.norm(v)) for k, v in maps.items()})
        log(f"{name}: reldev vs D " + " ".join(f"{k}={v:.3f}" for k, v in dev.items()))


# ----------------------------------------------------------------------
def cmd_robust_debias():
    """Affine debiasing mis-specification: ABSOLUTE albedo bias, RMSE and
    land/ocean contrast, because Pearson r is blind to exactly that error."""
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    F = E.get_F(camp, sglop)
    sigma_cl = E.get_sigcl(E.FC, camp, sglop, truthF)
    for j, seed in enumerate(E.SEEDS):
        name = f"robdebias_s{j}"
        if E.part_done(name):
            log(f"{name} exists, skipping"); continue
        dat = E.get_dat(camp, sglop, truthF, seed, E.FC)
        s = E.fit("profiled", F, dat, camp, sigma_cl)
        res = {}
        for dfc in (-0.15, -0.075, 0.0, 0.075, 0.15):
            for dac in (-0.15, -0.075, 0.0, 0.075, 0.15):
                m = S.debias_cloud_err(s, E.FC, delta_fc=dfc, delta_acl=dac)
                e = E.evaluate(m, truth_c)
                res[f"bias_dfc{dfc:+.2f}_dac{dac:+.2f}"] = e["bias"]
                res[f"rms_dfc{dfc:+.2f}_dac{dac:+.2f}"] = e["nrmse"]
                res[f"con_dfc{dfc:+.2f}_dac{dac:+.2f}"] = e["contrast"]
                res[f"r_dfc{dfc:+.2f}_dac{dac:+.2f}"] = e["pearson"]
        E.save_part(name, seed=seed, **res)
        log(f"{name}: bias@0 {res['bias_dfc+0.00_dac+0.00']:+.4f} "
            f"rms@0 {res['rms_dfc+0.00_dac+0.00']:.4f} "
            f"con@0 {res['con_dfc+0.00_dac+0.00']:.4f} "
            f"| worst |bias| {max(abs(v) for k, v in res.items() if k.startswith('bias')):.4f}")


def cmd_robust_clim():
    """Structured climatology variants (referee C5): ITCZ banding, surface
    coupling, multi-timescale clouds, per-pass iid clouds -- each calibrated
    against the cover it actually produces."""
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    F = E.get_F(camp, sglop)
    sigma_cl = E.get_sigcl(E.FC, camp, sglop, truthF)
    variants = {
        "itcz": dict(lat_profile=True),
        "surf": dict(surf_truth=truthF, surf_coupling=0.25),
        "multitau": dict(multi_tau=(1.0, 10.0, 0.7)),
        "iid": dict(iid_per_pass=True),
    }
    for tag, kw in variants.items():
        for j, seed in enumerate(E.SEEDS):
            name = f"robclim_{tag}_s{j}"
            if E.part_done(name):
                log(f"{name} exists, skipping"); continue
            cl = S.ExtendedCloudModel(E.NLATF, E.NLONF, fc=E.FC,
                                      tau_days=E.TAU_DAYS, seed=200 + seed, **kw)
            dat = S.simulate_dataset(camp, truthF, cl, sglop, seed=seed, nsub=E.NSUB)
            d = E.trim(dat)
            s = E.fit("profiled", F, d, camp, sigma_cl)
            e = E.evaluate(S.debias_cloud(s, E.FC), truth_c)
            E.save_part(name, seed=seed, cover=float(dat["covers"].mean()),
                        sigma_cl_used=sigma_cl, **e)
            log(f"{name}: cover={dat['covers'].mean():.3f} r={e['pearson']:.4f} "
                f"ssim={e['ssim']:.4f} bias={e['bias']:+.4f}")


def cmd_robust_geom():
    """Spin geometry: pole tilt and assumed-phase error, F per variant reused
    across all seeds."""
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    sigma_cl = E.get_sigcl(E.FC, camp, sglop, truthF)
    specs = [("tilt", pt, dict(theta_pole=np.deg2rad(pt))) for pt in (0.0, 5.0, 20.0)]
    specs += [("phase", ph, dict(phi0=np.deg2rad(ph))) for ph in (5.0, 15.0, 30.0, 60.0)]
    for tag, val, kw in specs:
        t0 = time.time()
        F = E.get_F(camp, sglop, cache=False, **kw)
        log(f"{tag}={val:g}: F built in {time.time() - t0:.1f}s")
        for j, seed in enumerate(E.SEEDS):
            name = f"robgeom_{tag}{val:g}_s{j}"
            if E.part_done(name):
                log(f"{name} exists, skipping"); continue
            dat = E.get_dat(camp, sglop, truthF, seed, E.FC)
            s = E.fit("profiled", F, dat, camp, sigma_cl)
            e = E.evaluate(S.debias_cloud(s, E.FC), truth_c)
            E.save_part(name, seed=seed, **e)
            log(f"  {name}: r={e['pearson']:.4f} ssim={e['ssim']:.4f}")
        del F


def cmd_robust_prof():
    """Profile likelihood over (assumed-period error, assumed-phase error).

    v2 quoted a 40% period shift from a coarse grid; here the objective is the
    WHITENED chi^2 evaluated in the same space the estimator is fitted in, the
    grid is centred on the true values, and both the anchored and the free
    profile are reported (the free profile has no mean-albedo mode, so its
    surface looks different -- that is a property of the estimator, not a
    numerical accident).
    """
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    sigma_cl = E.get_sigcl(E.FC, camp, sglop, truthF)
    prot_errs = [-2e-4, -1e-4, 0.0, 1e-4, 2e-4]
    phase_errs = [-10.0, -5.0, 0.0, 5.0, 10.0]
    acc = {j: dict(chi2=np.zeros((5, 5)), free=np.zeros((5, 5)),
                   r=np.zeros((5, 5))) for j in range(len(E.PROF_SEEDS))}
    todo = [j for j in range(len(E.PROF_SEEDS))
            if not E.part_done(f"robprof_s{j}")]
    if not todo:
        log("robprof parts complete"); return
    for i, pe in enumerate(prot_errs):
        for jj, phe in enumerate(phase_errs):
            F = E.get_F(camp, sglop, cache=False, prot=S.PROT * (1 + pe),
                        phi0=np.deg2rad(phe))
            for j in todo:
                seed = E.PROF_SEEDS[j]
                dat = E.get_dat(camp, sglop, truthF, seed, E.FC)
                s = E.fit("profiled", F, dat, camp, sigma_cl)
                acc[j]["chi2"][i, jj] = S.whitened_chi2(F, np.asarray(dat["y"], float),
                                                        camp, np.asarray(dat["sigma"], float),
                                                        sigma_cl, E.TAU_DAYS, s)
                sf = E.fit("profiled", F, dat, camp, sigma_cl, anchor=False)
                acc[j]["free"][i, jj] = S.whitened_chi2(F, np.asarray(dat["y"], float),
                                                        camp, np.asarray(dat["sigma"], float),
                                                        sigma_cl, E.TAU_DAYS, sf)
                acc[j]["r"][i, jj] = E.evaluate(S.debias_cloud(s, E.FC),
                                                truth_c)["pearson"]
            del F
            log(f"grid prot {pe:+.1e} phase {phe:+.0f} deg: min anchored chi2 "
                f"{min(acc[j]['chi2'][i, jj] for j in todo):.1f}")
    for j in todo:
        E.save_part(f"robprof_s{j}", seed=E.PROF_SEEDS[j],
                    prot_errs=np.array(prot_errs), phase_errs=np.array(phase_errs),
                    chi2=acc[j]["chi2"], free=acc[j]["free"], r=acc[j]["r"])
    log("robust_prof written")


# ----------------------------------------------------------------------
def cmd_resolution():
    """Real-harmonic scale-dependent correlation with an explicit quadrature
    error bound (v2 used a 2D-FFT r(l), which is not a spherical-harmonic
    decomposition on an equirectangular grid)."""
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    F = E.get_F(camp, sglop)
    sigma_cl = E.get_sigcl(E.FC, camp, sglop, truthF)
    basis, w = S.real_sphalm_basis(E.NLAT, E.NLON, 20)
    for j, seed in enumerate(E.SEEDS):
        name = f"res_s{j}"
        if E.part_done(name):
            log(f"{name} exists, skipping"); continue
        dcf = E.get_dat(camp, sglop, truthF, seed, 0.0)
        s_cf = E.fit("profiled", F, dcf, camp, 0.0, deflate=False)
        dcl = E.get_dat(camp, sglop, truthF, seed, E.FC)
        s_cl = E.fit("profiled", F, dcl, camp, sigma_cl)
        l_deg, r_cf = S.scale_dependent_correlation(s_cf, truth_c, E.NLAT, E.NLON,
                                                    20, basis, w)
        _, r_cl = S.scale_dependent_correlation(S.debias_cloud(s_cl, E.FC), truth_c,
                                                E.NLAT, E.NLON, 20, basis, w)
        qe = S.harmonic_quadrature_error(E.NLAT, E.NLON, 20)
        E.save_part(name, seed=seed, l=l_deg, r_cf=r_cf, r_cl=r_cl,
                    quadrature_err=np.array([qe[l] for l in range(21)]))
        log(f"{name}: l_eff(cf)={_first_below(l_deg, r_cf)} "
            f"l_eff(cl)={_first_below(l_deg, r_cl)} quad-err(l=20)={qe[20]:.4f}")


def _first_below(l, r, thr=0.5):
    for li, ri in zip(l, r):
        if np.isfinite(ri) and ri < thr:
            return int(li)
    return None


# ----------------------------------------------------------------------
def cmd_nulls_cloud(n_real=40):
    """Shared cloud-only physical null: uniform-albedo scenes through the SAME
    pipeline.  Computed ONCE and reused by every seed's observed d', so the
    null is a property of the estimator rather than a per-seed resample."""
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    F = E.get_F(camp, sglop)
    sigma_cl = E.get_sigcl(E.FC, camp, sglop, truthF)
    p = E.DATA / "nulls_cloud_ensemble.npz"
    if p.exists():
        log(f"cloud-null ensemble already at {p.name}"); return
    lab = truth_c > 0.15
    uni = np.full((E.NLATF, E.NLONF), float(truth_c.mean()))
    ds, maps = [], []
    for k in range(n_real):
        cloud = S.CloudModel(E.NLATF, E.NLONF, fc=E.FC, tau_days=E.TAU_DAYS,
                             seed=900 + k)
        dat = S.simulate_dataset(camp, uni, cloud, sglop, seed=3000 + k, nsub=E.NSUB)
        s = S.debias_cloud(E.fit("profiled", F, E.trim(dat), camp, sigma_cl), E.FC)
        ds.append(S.detection_dprime(s, truth_c)); maps.append(s)
        if k % 10 == 0:
            log(f"  cloud-null {k}/{n_real}: d'={ds[-1]:.4f}")
    np.savez(p, d=np.array(ds), lab=lab, maps=np.array(maps), n_real=n_real)
    log(f"cloud-null ensemble: mean {np.mean(ds):.4f} sd {np.std(ds, ddof=1):.4f} "
        f"95% {np.percentile(ds, 95):.4f}")


def cmd_nulls():
    """Land-ocean d' against (a) the shared cloud-only physical null and (b) a
    label permutation.  Replaces the v2 phase-scrambled equirectangular
    surrogate, which mixed a geometry transform into a photometric test."""
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    F = E.get_F(camp, sglop)
    sigma_cl = E.get_sigcl(E.FC, camp, sglop, truthF)
    lab = truth_c > 0.15
    null = np.load(E.DATA / "nulls_cloud_ensemble.npz")["d"]
    for j, seed in enumerate(E.SEEDS):
        name = f"null_s{j}"
        if E.part_done(name):
            log(f"{name} exists, skipping"); continue
        dat = E.get_dat(camp, sglop, truthF, seed, E.FC)
        s = S.debias_cloud(E.fit("profiled", F, dat, camp, sigma_cl), E.FC)
        obs = S.detection_dprime(s, truth_c)
        dp = S.label_permutation_dprime(s, lab, n_perm=2000, seed=seed)
        rank = (1.0 + float(np.sum(null >= obs))) / (null.size + 1.0)
        E.save_part(name, seed=seed, d_obs=obs, perm_null=dp["null"],
                    perm_p=dp["p_rank"], cloud_p=rank, n_null=null.size)
        log(f"{name}: d'={obs:.4f} perm p={dp['p_rank']:.4g} cloud-null p={rank:.4f} "
            f"(null mean {null.mean():.3f})")


# ----------------------------------------------------------------------
def cmd_systematics():
    """Quantitative systematic injection (referee C7: v2 asserted robustness but
    measured nothing).  A fractional coronal residual eps enters the light curve
    as delta_y = eps * (Qcor/Qexo) = 7.7403e4 * eps in planet-reference units
    (R22), so eps is swept in CORONAL units and the drift and streamer terms are
    varied separately, with the injection template and time scale recorded."""
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    F = E.get_F(camp, sglop)
    LtL = E.get_LtL()
    sigma_cl = E.get_sigcl(E.FC, camp, sglop, truthF)
    ratio = S.QCOR / S.QEXO
    eps_list = (0.0, 1e-8, 3e-8, 1e-7, 3e-7, 1e-6, 1e-5, 1e-4)
    bg = S.background_reference_snr(camp.ts)
    # single-dwell photon fluctuation in planet units -> eps that stays below it
    eps_one_sigma = float(np.mean(S.noise_sigma(1.0, camp.ts)) / ratio)
    for j, seed in enumerate(E.SEEDS):
        name = f"sys_s{j}"
        if E.part_done(name):
            log(f"{name} exists, skipping"); continue
        dat = E.get_dat(camp, sglop, truthF, seed, E.FC)
        base = E.fit("profiled", F, dat, camp, sigma_cl)
        e0 = E.evaluate(S.debias_cloud(base, E.FC), truth_c)
        rows = {}
        for kind in ("drift", "streamer", "both"):
            for eps in eps_list:
                kw = dict(drift_amp=eps if kind in ("drift", "both") else 0.0,
                          streamer_amp=eps if kind in ("streamer", "both") else 0.0,
                          units="coronal", seed=77)
                y2 = S.inject_systematics(np.asarray(dat["y"], float), camp, **kw)
                s2 = S.solve_gls_profiled(F, y2, camp, np.asarray(dat["sigma"], float),
                                          sigma_cl, E.TAU_DAYS, E.LAM_GLS, LtL)
                rows[(kind, eps)] = E.evaluate(S.debias_cloud(s2, E.FC), truth_c)
        kinds = ("drift", "streamer", "both")
        E.save_part(name, seed=seed, base_r=e0["pearson"], base_ssim=e0["ssim"],
                    base_bias=e0["bias"], qcor_over_qexo=ratio,
                    eps=np.array(eps_list),
                    **{f"{k}_r": np.array([rows[(k, e)]["pearson"] for e in eps_list])
                       for k in kinds},
                    **{f"{k}_ssim": np.array([rows[(k, e)]["ssim"] for e in eps_list])
                       for k in kinds},
                    **{f"{k}_bias": np.array([rows[(k, e)]["bias"] for e in eps_list])
                       for k in kinds},
                    **{f"{k}_nrmse": np.array([rows[(k, e)]["nrmse"] for e in eps_list])
                       for k in kinds},
                    eps_one_sigma=eps_one_sigma,
                    bg_extra_sigma=bg["extra_sigma"], bg_ref_snr=bg["ref_snr"],
                    bg_ratio_to_photon=bg["ratio_to_photon_sigma"])
        log(f"{name}: base r={e0['pearson']:.4f}; drift r @eps " +
            " ".join(f"{rows[('drift', k)]['pearson']:.3f}@{k:.0e}"
                     for k in eps_list[1:]))
        log(f"        streamer r @eps " +
            " ".join(f"{rows[('streamer', k)]['pearson']:.3f}@{k:.0e}"
                     for k in eps_list[1:]))


# ----------------------------------------------------------------------
LAM_GRID = [1e-5, 1e-4, 3e-4, 1e-3, 3e-3, 1e-2, 3e-2, 1e-1, 3e-1]


def cmd_lam_sweep(i_fc):
    """Regularization-parameter sweep (referee minor comment on lambda).

    v2 fixed lambda = 3e-3 and asserted the result was insensitive without
    measuring it; the v3 robustness text explicitly withdrew that.  Here the
    SAME cached campaign (fiducial ts/mp, seed set, GL-16 quadrature) is solved
    at nine lambda values spanning five decades, for one cloud fraction per
    invocation -- the cloud-free (i_fc=0) and fiducial-cloudy (i_fc=3) cases the
    referee asked for, plus the intermediate fractions if wanted.

    Note lambda enters through lam_eff = lambda * tr(A)/tr(LtL), so the abscissa
    is the dimensionless multiplier in the paper, not the absolute penalty
    weight.  Both the profiled GLS score and the whitened chi^2 are recorded, so
    the sweep also shows whether the objective could pick lambda in flight.
    """
    i_fc = int(i_fc)
    fc = E.FCS[i_fc]
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    F = E.get_F(camp, sglop)
    LtL = E.get_LtL()
    sigma_cl = E.get_sigcl(fc, camp, sglop, truthF) if fc > 0 else 0.0
    for j, seed in enumerate(E.SEEDS):
        name = f"lamsweep_f{i_fc}_s{j}"
        if E.part_done(name):
            log(f"{name} exists, skipping"); continue
        dat = E.get_dat(camp, sglop, truthF, seed, fc)
        y = np.asarray(dat["y"], dtype=np.float64)
        sg = np.asarray(dat["sigma"], dtype=np.float64)
        r, ssim, bias, chi2, con = [], [], [], [], []
        for lam in LAM_GRID:
            s = S.solve_gls_profiled(F, y, camp, sg, sigma_cl, E.TAU_DAYS, lam, LtL)
            e = E.evaluate(S.debias_cloud(s, fc), truth_c)
            r.append(e["pearson"]); ssim.append(e["ssim"]); bias.append(e["bias"])
            con.append(e["contrast"])
            chi2.append(S.whitened_chi2(F, y, camp, sg, sigma_cl, E.TAU_DAYS, s))
        E.save_part(name, fc=fc, seed=seed, lam=np.array(LAM_GRID),
                    r=np.array(r), ssim=np.array(ssim), bias=np.array(bias),
                    contrast=np.array(con), chi2=np.array(chi2),
                    sigma_cl=sigma_cl)
        log(f"{name} fc={fc:g} r @lam " +
            " ".join(f"{v:.3f}@{l:.0e}" for l, v in zip(LAM_GRID, r)))


# ----------------------------------------------------------------------
WEATHER_GRID = {
    "corr8": dict(corr_deg=8.0),
    "corr20": dict(corr_deg=20.0),
    "u3": dict(u_deg_day=3.0),
    "u12": dict(u_deg_day=12.0),
    "tau2": dict(tau_days=2.0),
    "tau8": dict(tau_days=8.0),
}


def cmd_robust_weather(i_var):
    """Weather-parameter sensitivity (referee major comment: 'at least two
    additional spatial correlation lengths, advection rates and decorrelation
    times').

    Each variant is a DIFFERENT true cloud field, scored two ways:
      misspecified -- the estimator keeps the fiducial OU tau = 4 d, corr = 12 deg
        and the sigma_cl calibrated to it, i.e. what happens if the observer's
        climatology is wrong;
      recalibrated -- sigma_cl (and tau in the covariance) are set to the variant
        itself, i.e. the best case where the climatology is known.
    The gap between the two columns is the cost of climatology error per se,
    which is what the referee's comment is really about.
    """
    tag = i_var
    if tag not in WEATHER_GRID:
        log(f"unknown variant {tag}; known: {sorted(WEATHER_GRID)}"); return
    kw = dict(WEATHER_GRID[tag])
    tau = float(kw.pop("tau_days", E.TAU_DAYS))
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    F = E.get_F(camp, sglop)
    LtL = E.get_LtL()
    sc_fid = E.get_sigcl(E.FC, camp, sglop, truthF)
    sc_var = E.get_sigcl(E.FC, camp, sglop, truthF, tau=tau, **kw)
    for j, seed in enumerate(E.SEEDS):
        name = f"robweather_{tag}_s{j}"
        if E.part_done(name):
            log(f"{name} exists, skipping"); continue
        cl = S.ExtendedCloudModel(E.NLATF, E.NLONF, fc=E.FC, tau_days=tau,
                                  seed=300 + seed, **kw)
        dat = E.trim(S.simulate_dataset(camp, truthF, cl, sglop, seed=seed,
                                        nsub=E.NSUB))
        y = np.asarray(dat["y"], dtype=np.float64)
        sg = np.asarray(dat["sigma"], dtype=np.float64)
        out = {}
        for mode, sc, tk in (("misspecified", sc_fid, E.TAU_DAYS),
                             ("recalibrated", sc_var, tau)):
            s = S.solve_gls_profiled(F, y, camp, sg, sc, tk, E.LAM_GLS, LtL)
            e = E.evaluate(S.debias_cloud(s, E.FC), truth_c)
            out[f"{mode}_r"] = e["pearson"]; out[f"{mode}_ssim"] = e["ssim"]
            out[f"{mode}_bias"] = e["bias"]
        E.save_part(name, variant=tag, seed=seed, tau=tau, cover=float(dat["covers"].mean()),
                    sigma_cl_fid=sc_fid, sigma_cl_var=sc_var,
                    **{k: float(v) for k, v in out.items()})
        log(f"{name} {tag} cover={dat['covers'].mean():.3f} "
            f"sigma_cl fid={sc_fid:.4f} var={sc_var:.4f} | "
            f"misspec r={out['misspecified_r']:.4f} recalc r={out['recalibrated_r']:.4f}")


# ----------------------------------------------------------------------
SIGCL_FACTORS = [0.0, 0.0625, 0.25, 0.5, 1.0, 2.0, 4.0, 16.0]


def cmd_sigma_sens():
    """How much does the ASSUMED cloud amplitude actually cost?

    Motivation: the weather-parameter sweep found the 'recalibrated' and
    'misspecified' columns identical, which is only possible if the reconstruction
    is insensitive to sigma_cl.  That is a substantive claim about the estimator
    and it needs its own measurement, so sigma_cl is multiplied by factors from 0
    (cloud structure entirely unmodelled) to 16 (grossly over-modelled) on the
    fiducial cloudy campaign.  Both the image-quality score and the whitened
    chi^2 are recorded: the point of the experiment is that these two things move
    on completely different scales, i.e. the misspecification is loud in the
    objective and nearly silent in the map.
    """
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    F = E.get_F(camp, sglop)
    LtL = E.get_LtL()
    sc = E.get_sigcl(E.FC, camp, sglop, truthF)
    for j, seed in enumerate(E.SEEDS):
        name = f"sigcl_s{j}"
        if E.part_done(name):
            log(f"{name} exists, skipping"); continue
        dat = E.get_dat(camp, sglop, truthF, seed, E.FC)
        y = np.asarray(dat["y"], dtype=np.float64)
        sg = np.asarray(dat["sigma"], dtype=np.float64)
        r, ssim, bias, chi2 = [], [], [], []
        for m in SIGCL_FACTORS:
            s = S.solve_gls_profiled(F, y, camp, sg, sc * m, E.TAU_DAYS,
                                     E.LAM_GLS, LtL)
            e = E.evaluate(S.debias_cloud(s, E.FC), truth_c)
            r.append(e["pearson"]); ssim.append(e["ssim"]); bias.append(e["bias"])
            chi2.append(S.whitened_chi2(F, y, camp, sg, sc * m, E.TAU_DAYS, s))
        r = np.array(r); chi2 = np.array(chi2)
        E.save_part(name, seed=seed, sigma_cl=sc, factors=np.array(SIGCL_FACTORS),
                    r=r, ssim=np.array(ssim), bias=np.array(bias), chi2=chi2,
                    nsamp=int(y.size),
                    r_spread=float(r.max() - r.min()),
                    chi2_ratio_max=float(chi2.max() / chi2.min()))
        log(f"{name}: r spread {r.max() - r.min():.4f} over {len(SIGCL_FACTORS)} "
            f"sigma_cl factors; chi2 spans x{chi2.max() / chi2.min():.1f}; "
            f"r(sc=0)={r[0]:.4f} r(sc=fid)={r[SIGCL_FACTORS.index(1.0)]:.4f}")


# ----------------------------------------------------------------------
SIGCL_ESTS = ("free", "v2")


def cmd_sigma_sens_est():
    """The sigma_cl insensitivity of cmd_sigma_sens, for the OTHER estimators.

    cmd_sigma_sens sweeps the ASSUMED cloud amplitude for the full TDI estimator
    (exact anchored profiling + OU whitening).  The claim that the reconstruction
    does not use sigma_cl is an estimator claim, so it has to be tested for the
    two variants the paper compares TDI against: the free (un-anchored) profiler
    and v2's approximate deflation.  Same fiducial cloudy data, same factor grid,
    same scoring; whitened chi2 is only defined for the profiled system, so the
    free/v2 arms record r/ssim/bias and the map-level conclusion only.
    """
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    F = E.get_F(camp, sglop)
    LtL = E.get_LtL()
    sc = E.get_sigcl(E.FC, camp, sglop, truthF)
    fac = [0.25, 1.0, 4.0, 16.0]
    for j, seed in enumerate(E.SEEDS):
        dat = E.get_dat(camp, sglop, truthF, seed, E.FC)
        y = np.asarray(dat["y"], dtype=np.float64)
        sg = np.asarray(dat["sigma"], dtype=np.float64)
        for est in SIGCL_ESTS:
            name = f"sigcl{est}_s{j}"
            if E.part_done(name):
                log(f"{name} exists, skipping"); continue
            r, ssim, bias = [], [], []
            for m in fac:
                if est == "free":
                    s = S.solve_gls_profiled(F, y, camp, sg, sc * m, E.TAU_DAYS,
                                             E.LAM_GLS, LtL, anchor=False)
                else:
                    s = S.solve_gls(F, y, camp, sg, sc * m, E.TAU_DAYS,
                                    E.LAM_GLS, LtL, deflate=True)
                e = E.evaluate(S.debias_cloud(s, E.FC), truth_c)
                r.append(e["pearson"]); ssim.append(e["ssim"])
                bias.append(e["bias"])
            r = np.array(r)
            E.save_part(name, seed=seed, estimator=est, sigma_cl=sc,
                        factors=np.array(fac), r=r, ssim=np.array(ssim),
                        bias=np.array(bias),
                        r_spread=float(r.max() - r.min()),
                        r_fid=float(r[fac.index(1.0)]))
            log(f"{name}: r spread {r.max() - r.min():.4f}; "
                + " ".join("f=%g r=%.4f" % (m, v) for m, v in zip(fac, r)))


# ----------------------------------------------------------------------
LAM_EXT = [1.0, 3.0, 10.0]
def cmd_lam_ext(i_fc):
    """High-lambda tail of the regularization sweep.

    The 1e-5..3e-1 grid is still RISING in r at its upper end for both the
    cloud-free and the cloudy case, so the sweep is incomplete without the
    turnover. These three points extend it; cmd_merge concatenates the two
    archives. The point of measuring the turnover is that r is NOT the only
    criterion: if r keeps improving while the whitened chi2 and the albedo
    contrast run away, the large-lambda solutions are over-smoothed and the
    held-out-lambda procedure has to be re-decided on a stated criterion.
    """
    i_fc = int(i_fc)
    fc = E.FCS[i_fc]
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    F = E.get_F(camp, sglop)
    LtL = E.get_LtL()
    sigma_cl = E.get_sigcl(fc, camp, sglop, truthF) if fc > 0 else 0.0
    for j, seed in enumerate(E.SEEDS):
        name = f"lamsweepxt_f{i_fc}_s{j}"
        if E.part_done(name):
            log(f"{name} exists, skipping"); continue
        dat = E.get_dat(camp, sglop, truthF, seed, fc)
        y = np.asarray(dat["y"], dtype=np.float64)
        sg = np.asarray(dat["sigma"], dtype=np.float64)
        r, ssim, bias, chi2, con = [], [], [], [], []
        for lam in LAM_EXT:
            s = S.solve_gls_profiled(F, y, camp, sg, sigma_cl, E.TAU_DAYS, lam, LtL)
            e = E.evaluate(S.debias_cloud(s, fc), truth_c)
            r.append(e["pearson"]); ssim.append(e["ssim"]); bias.append(e["bias"])
            con.append(e["contrast"])
            chi2.append(S.whitened_chi2(F, y, camp, sg, sigma_cl, E.TAU_DAYS, s))
        E.save_part(name, fc=fc, seed=seed, lam=np.array(LAM_EXT),
                    r=np.array(r), ssim=np.array(ssim), bias=np.array(bias),
                    contrast=np.array(con), chi2=np.array(chi2), sigma_cl=sigma_cl)
        log(f"{name} fc={fc:g} r @lam(ext) " +
            " ".join(f"{v:.3f}@{l:g}" for l, v in zip(LAM_EXT, r)) +
            " | contrast " + " ".join(f"{v:.3f}" for v in con))


# ----------------------------------------------------------------------
MORPHS = ("supercontinent", "archipelago")


def cmd_robust_morph(i_fc):
    """Surface-map morphology sensitivity (referee major comment 6: 'sensitivity
    to ... substantially different surface-map morphologies').

    v2's morphology scans are NOT inherited: they were produced with the
    superseded spherical quadrature and the approximate deflation estimator.
    This re-runs them on the corrected pipeline.  Three truth fields at the same
    quantile land fraction (30% of the fine grid above the albedo threshold, so
    mean albedo 0.235--0.237 and sd within 2% of each other) and the same truth
    seed -- 'earthlike' (already in the fiducial archive), a Pangaea-like
    supercontinent, and a fragmented
    archipelago -- each with its OWN weather realization (same cloud seeds) and
    its OWN calibrated sigma_cl, because the cloud-induced variance depends on
    the surface albedo pattern it modulates.

    Both fc = 0 and the fiducial fc = 0.55 are run so the morphology penalty
    can be separated from the weather penalty, and the earthlike value on the
    SAME seeds is the paired reference.
    """
    i_fc = int(i_fc)
    fc = E.FCS[i_fc]
    camp = E.campaign()
    sglop = E.sgl("point")
    F = E.get_F(camp, sglop)
    LtL = E.get_LtL()
    for morph in MORPHS:
        truthF, truth_c = E.truth(morphology=morph)
        sig_tag = "_morph%s" % morph
        sigma_cl = (E.get_sigcl(fc, camp, sglop, truthF, tag=sig_tag)
                    if fc > 0 else 0.0)
        for j, seed in enumerate(E.SEEDS):
            name = f"morph_{morph}_f{i_fc}_s{j}"
            if E.part_done(name):
                log(f"{name} exists, skipping"); continue
            dat = E.get_dat(camp, sglop, truthF, seed, fc, tag=sig_tag)
            s = S.solve_gls_profiled(F, np.asarray(dat["y"], float), camp,
                                     np.asarray(dat["sigma"], float), sigma_cl,
                                     E.TAU_DAYS, E.LAM_GLS, LtL)
            m = S.debias_cloud(s, fc)
            e = E.evaluate(m, truth_c)
            dp = S.detection_dprime(m.reshape(E.NLAT, E.NLON), truth_c)
            E.save_part(name, fc=fc, morph=morph, seed=seed, sigma_cl=sigma_cl,
                        cover=float(np.mean(dat["covers"])),
                        truth_land=float(np.mean(truth_c > 0.15)),
                        truth_mean=float(truth_c.mean()),
                        truth_sd=float(truth_c.std()),
                        r=e["pearson"], ssim=e["ssim"], nrmse=e["nrmse"],
                        bias=e["bias"], contrast=e["contrast"], dprime=dp)
            log(f"{name} fc={fc:g} land={np.mean(truth_c > 0.15):.3f} "
                f"cover={np.mean(dat['covers']):.3f} sigma_cl={sigma_cl:.4f} | "
                f"r={e['pearson']:.4f} ssim={e['ssim']:.4f} d'={dp:.3f}")


# ----------------------------------------------------------------------
LATBANDS = [(-90, -60), (-60, -30), (-30, 0), (0, 30), (30, 60), (60, 90)]


def cmd_latband():
    """Quality vs latitude and illumination coverage (referee major comment 6:
    'uncertainty or resolution maps, including the dependence on latitude and
    illumination coverage').

    No new inversions: the per-seed reconstructions of the cloudy (fc=0.55) and
    cloud-free campaigns are already archived, so this command scores them band
    by band and pairs each band with two coverage quantities that decide
    whether a band is illumination-limited or weather-limited:
      dayside  -- campaign-mean Lambert factor of the disk pixels in the band;
      weight   -- campaign-mean column energy ||F[:,i]||^2 of the grid cell,
                  i.e. the actual information the operator delivers there.
    The polar rows are reported too, but the weight column shows why they carry
    nothing: the circular raster never samples |lat| >= 85 deg (Section on the
    information audit).
    """
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    geo = sglop.geo
    lat_deg = (np.arange(E.NLAT) + 0.5) / E.NLAT * 180.0 - 90.0
    disk_lat = np.rad2deg(geo["lat"].ravel())
    # illumination coverage: campaign-mean Lambert factor per disk pixel
    cov = np.zeros((len(camp.bins_t), geo["lat"].size))
    for k, t in enumerate(camp.bins_t):
        cov[k] = illum_flat(geo, t)
    cov = cov.mean(0)
    inmask = geo["mask"].ravel()
    # operator information weight per grid cell, from the column energies of F
    F = E.get_F(camp, sglop)
    wcol = np.zeros(F.shape[1])
    step = 8192
    for k0 in range(0, F.shape[0], step):
        # keep the chunk in float32 (the accumulator is float64, so the column
        # energy is still summed in double precision) -- 4x less RAM
        blk = np.asarray(F[k0:k0 + step], dtype=np.float32)
        wcol += (blk * blk).sum(0, dtype=np.float64)
    wcol = wcol.reshape(E.NLAT, E.NLON)
    band_dayside, band_weight, band_npix = [], [], []
    band_tsd, band_dead = [], []
    wmax = float(np.nanmax(wcol)) if np.isfinite(wcol).any() else 1.0
    for lo, hi in LATBANDS:
        sel = (disk_lat >= lo) & (disk_lat < hi) & inmask
        band_dayside.append(float(cov[sel].mean()) if sel.any() else np.nan)
        band_npix.append(int(sel.sum()))
        g = (lat_deg >= lo) & (lat_deg < hi)
        band_weight.append(float(wcol[g].mean()) if g.any() else np.nan)
        band_tsd.append(float(truth_c[g].std()) if g.any() else np.nan)
        band_dead.append(float(np.mean(wcol[g] < 1e-3 * wmax)) if g.any()
                         else np.nan)
    rows = []
    tsd = np.array(band_tsd)
    # cells the operator actually illuminates (the same 1e-3 x wmax rule that
    # sets band_dead_frac below), used for the restricted-band r in Section 5.9
    alive = (wcol >= 1e-3 * wmax)
    for j, seed in enumerate(E.SEEDS):
        rec = dict(seed=int(seed))
        ok = False
        for fc_i, pre in ((3, "cloud"), (0, "clear")):
            p = E.part_path(f"clouds_f{fc_i}_s{j}")
            if not p.exists():
                continue
            ok = True
            d = np.load(p)
            m = np.asarray(d["map_profiled"], float).reshape(E.NLAT, E.NLON)
            rec[f"{pre}_cover"] = float(d["cover"])
            rng = float(truth_c.max() - truth_c.min())
            for bi, (lo, hi) in enumerate(LATBANDS):
                s = (lat_deg >= lo) & (lat_deg < hi)
                a = m[s]; b = truth_c[s]
                rec[f"{pre}_r{bi}"] = float(np.corrcoef(a.ravel(),
                                                        b.ravel())[0, 1])
                # restricted to illuminated cells only: rows of the band that the
                # circular raster actually samples, broadcast across longitude
                sel = np.zeros((E.NLAT, E.NLON), dtype=bool)
                sel[s, :] = True
                keep = sel & alive
                if keep.sum() > 2:
                    rec[f"{pre}_ralive{bi}"] = float(
                        np.corrcoef(m[keep], truth_c[keep])[0, 1])
                else:
                    rec[f"{pre}_ralive{bi}"] = float("nan")
                rec[f"{pre}_nrmse{bi}"] = float(np.sqrt(np.mean((a - b) ** 2))
                                                / rng)
                # band amplitude and band offset -- the two things Pearson r is
                # exactly blind to, reported alongside it
                rec[f"{pre}_gain{bi}"] = float(a.std() / max(b.std(), 1e-12))
                rec[f"{pre}_b_off{bi}"] = float(a.mean() - b.mean())
        if not ok:
            continue
        for bi in range(len(LATBANDS)):
            rec[f"dayside{bi}"] = band_dayside[bi]
            rec[f"weight{bi}"] = band_weight[bi]
            rec[f"tsd{bi}"] = tsd[bi]
            rec[f"dead{bi}"] = band_dead[bi]
        rows.append(rec)
    if not rows:
        log("no clouds parts yet"); return
    keys = sorted({k for r in rows for k in r})
    np.savez(E.DATA / "latband.npz",
             **{k: np.array([r[k] for r in rows], float) for k in keys},
             bands=np.array(["%+d:%+d" % b for b in LATBANDS]),
             lat_deg=lat_deg,
             band_dayside=np.array(band_dayside),
             band_weight=np.array(band_weight),
             band_truth_sd=np.array(band_tsd),
             band_dead_frac=np.array(band_dead),
             band_disk_pix=np.array(band_npix),
             n_grid_per_band=np.array([int(np.sum((lat_deg >= lo) &
                                                  (lat_deg < hi)) * E.NLON)
                                       for lo, hi in LATBANDS]))
    log(f"latband: {len(rows)} seeds; dayside "
        + " ".join(f"{v:.3f}" for v in band_dayside) + "; weight "
        + " ".join(f"{v:.2e}" for v in band_weight))


def illum_flat(geo, t):
    """Raw Lambert factor (0--1) per disk pixel at time t, flattened."""
    return S.illum(geo, t).ravel()


# ----------------------------------------------------------------------
LAM_RES = [3e-3, 0.1, 1.0, 10.0]


def cmd_lam_res(i_fc):
    """Is the large-lambda 'gain' in the cloudy case recovery or blur?

    The lambda sweep shows r INCREASING monotonically with the smoothing weight
    for cloudy data (up to lambda = 10, the largest tested), which is only a
    useful result if the extra correlation is not bought by throwing away the
    spatial information the claim is about.  This command therefore re-solves
    the fiducial campaign at four lambda and scores the scale-dependent
    correlation r(l) band by band, plus the land--ocean d' and the contrast:
    the three quantities that a low-passed map cannot fake.
    """
    i_fc = int(i_fc)
    fc = E.FCS[i_fc]
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    F = E.get_F(camp, sglop)
    LtL = E.get_LtL()
    sigma_cl = E.get_sigcl(fc, camp, sglop, truthF) if fc > 0 else 0.0
    basis, w = S.real_sphalm_basis(E.NLAT, E.NLON, 20)
    for j, seed in enumerate(E.SEEDS[:4]):
        name = f"lamres_f{i_fc}_s{j}"
        if E.part_done(name):
            log(f"{name} exists, skipping"); continue
        dat = E.get_dat(camp, sglop, truthF, seed, fc)
        R = np.zeros((len(LAM_RES), 20)); DP = np.zeros(len(LAM_RES))
        CO = np.zeros(len(LAM_RES)); PR = np.zeros(len(LAM_RES))
        SS = np.zeros(len(LAM_RES))
        for k, lam in enumerate(LAM_RES):
            s = S.solve_gls_profiled(F, np.asarray(dat["y"], float), camp,
                                     np.asarray(dat["sigma"], float), sigma_cl,
                                     E.TAU_DAYS, lam, LtL)
            m = S.debias_cloud(s, fc)
            e = E.evaluate(m, truth_c)
            _, rl = S.scale_dependent_correlation(m, truth_c, E.NLAT, E.NLON,
                                                  20, basis, w)
            R[k] = rl
            DP[k] = S.detection_dprime(m.reshape(E.NLAT, E.NLON), truth_c)
            CO[k] = e["contrast"]; SS[k] = e["ssim"]; PR[k] = e["pearson"]
        E.save_part(name, seed=seed, fc=fc, lam=np.array(LAM_RES), r_ell=R,
                    dprime=DP, contrast=CO, pearson=PR, ssim=SS,
                    l=np.arange(1, 21))
        log(f"{name} fc={fc:g} " + " ".join(
            f"lam={l:g} r={p:.3f} l<=4={np.nanmean(rr[:4]):.3f} "
            f"l>=13={np.nanmean(rr[12:]):.3f} d'={d:.2f} con={c:.3f}"
            for l, p, rr, d, c in zip(LAM_RES, PR, R, DP, CO)))


# ----------------------------------------------------------------------
def cmd_static_ref():
    """Static ideal-data reference at the SAME photon budget (referee major
    comment on image quality: 'compare the rotating solution with a static
    ideal-data reference under the same photon budget, and report the
    information or resolution loss attributable specifically to rotation').

    The reference campaign is the fiducial 64x64 raster, 16 revisits, 1800 s
    dwell -- so every raster position receives the same 8 h of integration --
    but with the planet frozen: render_disk and build_F are both called with
    static=True, so all mp passes see one identical pose and there is no weather
    (simulate_dataset ignores the cloud field in static mode).  The rows of the
    mp passes are then literally identical, which makes this the best case any
    observation of this planet could produce at this dose: no rotational smearing
    to model, no phase coverage to solve, no atmospheric variability.

    Both arms are scored on the SAME seeds and the same estimator so the
    difference is a paired quantity, not a comparison of two tables.
    """
    camp_r = E.campaign()
    camp_s = E.campaign(static=True)
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    Fs = E.get_F(camp_s, sglop, cache=False)
    Fr = E.get_F(camp_r, sglop)
    LtL = E.get_LtL()
    sigma_cl = E.get_sigcl(E.FC, camp_r, sglop, truthF)
    for j, seed in enumerate(E.SEEDS):
        name = f"staticref_s{j}"
        if E.part_done(name):
            log(f"{name} exists, skipping"); continue
        ds = E.trim(S.simulate_dataset(camp_s, truthF, None, sglop, seed=seed,
                                       nsub=E.NSUB))
        ys = np.asarray(ds["y"], dtype=np.float64)
        sgs = np.asarray(ds["sigma"], dtype=np.float64)
        s_stat = S.solve_gls_profiled(Fs, ys, camp_s, sgs, 0.0, E.TAU_DAYS,
                                      E.LAM_GLS, LtL, deflate=False)
        es = E.evaluate(s_stat, truth_c)
        # rotating, cloud-free, same estimator and same seeds
        dr = E.get_dat(camp_r, sglop, truthF, seed, 0.0)
        s_rot = S.solve_gls_profiled(Fr, np.asarray(dr["y"], float), camp_r,
                                     np.asarray(dr["sigma"], float), 0.0,
                                     E.TAU_DAYS, E.LAM_GLS, LtL, deflate=False)
        er = E.evaluate(s_rot, truth_c)
        # rotating, cloudy, fiducial
        dc = E.get_dat(camp_r, sglop, truthF, seed, E.FC)
        s_cl = S.solve_gls_profiled(Fr, np.asarray(dc["y"], float), camp_r,
                                    np.asarray(dc["sigma"], float), sigma_cl,
                                    E.TAU_DAYS, E.LAM_GLS, LtL)
        ec = E.evaluate(S.debias_cloud(s_cl, E.FC), truth_c)
        E.save_part(name, seed=seed, stat_r=es["pearson"], stat_ssim=es["ssim"],
                    stat_nrmse=es["nrmse"], stat_bias=es["bias"],
                    rot_r=er["pearson"], rot_ssim=er["ssim"],
                    rot_nrmse=er["nrmse"], rot_bias=er["bias"],
                    cloud_r=ec["pearson"], cloud_ssim=ec["ssim"],
                    cloud_nrmse=ec["nrmse"], cloud_bias=ec["bias"],
                    photons_per_pixel_h=camp_r.mp * camp_r.ts / 3600.0)
        log(f"{name}: static r={es['pearson']:.4f} ssim={es['ssim']:.4f} | "
            f"rot-cf r={er['pearson']:.4f} | rot-cloudy r={ec['pearson']:.4f}")


# ----------------------------------------------------------------------
def cmd_diagnostics():
    """Replace the '25% rank loss / 93.75% information retained' claim with
    diagnostics that are actually about the surface map (referee C4)."""
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, truth_c = E.truth()
    F = E.get_F(camp, sglop)
    LtL = E.get_LtL()
    sigma_cl = E.get_sigcl(E.FC, camp, sglop, truthF)
    sg = np.full(camp.nsamp, S.noise_sigma(1.0, camp.ts))
    out = {}
    for white in (True, False):
        d = S.deflation_diagnostics(F, camp, sg, sigma_cl, E.TAU_DAYS, white=white)
        out["slot_deflation_" + ("white" if white else "ou")] = d
        log(f"[{'white' if white else 'OU'}] removed={d['removed_directions']} "
            f"const-mode survival={d['constant_mode_survival']:.6f} rank "
            f"{d['rank_undef']}->{d['rank_defl']} trace ratio={d['frobenius_ratio']:.6f}")
    # exact profiling audit: un-profiled / free / anchored
    a = S.profiling_information_audit(F, camp, sg, sigma_cl, E.TAU_DAYS,
                                      E.LAM_GLS, LtL, nlon=E.NLON)
    out["profiling"] = a
    for tag in ("unprofiled", "free", "anchored"):
        d = a[tag]
        log(f"{tag:11s}: nullity={d['nullity']} eig=({d['eig_min']:.2e},"
            f"{d['eig_max']:.2e}) const-mode gain={d['constant_mode_gain']:.4e} "
            f"overlap(null,1)={d['null_const_overlap']:.4f}")
    log(f"constant-mode retained: free {a['retained_fraction_free']:.4f} "
        f"anchored {a['retained_fraction_anchored']:.4f} "
        f"(vs the '93.75% information' claim); dead basis columns "
        f"{a['zero_columns']} in latitude rows {a['zero_column_lat_rows']}")
    out["note"] = ("rank/93.75% framing replaced by (i) rank, which profiling "
                   "does not change, and (ii) the constant-mode gain ratio, "
                   "which is what profiling actually removes")
    (E.DATA / "deflation_diag.json").write_text(json.dumps(out, indent=2, default=float))


def cmd_precision():
    """Numerical-precision audit on a REDUCED campaign.

    The audit needs the full dense whitened design in memory twice (float64
    reference plus float32 variant).  At the fiducial n = 64 that is 65536 x
    2592 x 8 B = 1.4 GB per copy, so the test runs at n = 32 with the same
    nsc/mp/ts and states its own regime; the fiducial-size check is the
    block-order comparison inside solve_gls, which never forms the design.
    """
    camp = S.Campaign(n=32, nsc=16, ts=1800.0, mp=16, seed=E.CAMPAIGN_SEED)
    sglop = S.SGLOperator(32)
    truthF, truth_c = E.truth()
    # the SURFACE basis is 36x72 at every image-plane n, so LtL is unchanged
    LtL = E.get_LtL()
    F = E.get_F(camp, sglop, cache=False)
    sigma_cl = E.get_sigcl(E.FC, camp, sglop, truthF)
    dat = E.get_dat(camp, sglop, truthF, 11, E.FC)
    d = S.check_numerical_precision(F, np.asarray(dat["y"], float), camp,
                                    np.asarray(dat["sigma"], float), sigma_cl,
                                    E.TAU_DAYS, E.LAM_GLS, LtL)
    d["regime"] = dict(n=camp.n, nsc=camp.nsc, mp=camp.mp, ts=camp.ts,
                       nsamp=camp.nsamp, ns=F.shape[1],
                       note="reduced size; the fiducial n=64 design would need "
                            "~2.8 GB in two float64 copies")
    # fiducial-size companion test: does the BLOCKED profiler agree with a
    # different chunk size on the real n=64 problem?
    camp64 = E.campaign()
    sglop64 = E.sgl("point")
    F64 = E.get_F(camp64, sglop64)
    dat64 = E.get_dat(camp64, sglop64, truthF, 11, E.FC)
    sc64 = E.get_sigcl(E.FC, camp64, sglop64, truthF)
    LtL = E.get_LtL()
    s_ref = S.solve_gls_profiled(F64, np.asarray(dat64["y"], float), camp64,
                                 np.asarray(dat64["sigma"], float), sc64,
                                 E.TAU_DAYS, E.LAM_GLS, LtL, jchunk=8)
    s_alt = S.solve_gls_profiled(F64, np.asarray(dat64["y"], float), camp64,
                                 np.asarray(dat64["sigma"], float), sc64,
                                 E.TAU_DAYS, E.LAM_GLS, LtL, jchunk=256)
    s_v2 = S.solve_gls(F64, np.asarray(dat64["y"], float), camp64,
                       np.asarray(dat64["sigma"], float), sc64, E.TAU_DAYS,
                       E.LAM_GLS, LtL, deflate=True)
    d["fiducial_chunk_order_rel_diff"] = float(
        np.linalg.norm(s_ref - s_alt) / np.linalg.norm(s_ref))
    d["fiducial_profiled_vs_v2_rel_diff"] = float(
        np.linalg.norm(s_ref - s_v2) / np.linalg.norm(s_ref))
    d["fiducial_absmax"] = float(np.abs(s_ref).max())
    (E.DATA / "precision.json").write_text(json.dumps(d, indent=2, default=float))
    for k, v in d.items():
        log(f"{k}: {v}")


# ----------------------------------------------------------------------
def _ms(v):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    return dict(mean=float(v.mean()) if v.size else None,
                sd=float(v.std(ddof=1)) if v.size > 1 else None,
                se=float(v.std(ddof=1) / np.sqrt(v.size)) if v.size > 1 else None,
                n=int(v.size))


def nanmean(v):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    return float(v.mean()) if v.size else None


def _sd(v):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    return float(v.std(ddof=1)) if v.size > 1 else None


def cmd_merge():
    """Consolidate parts -> shipped archives + an audit JSON stating, for every
    headline number, how many seeds actually produced it."""
    audit = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
             "conventions": dict(
                 nsub=E.NSUB, truth_seed=E.TRUTH_SEED, campaign_seed=E.CAMPAIGN_SEED,
                 tau_days=E.TAU_DAYS, lam=E.LAM_GLS, fc=E.FC, seeds=E.SEEDS,
                 cad_seeds=E.CAD_SEEDS, kernel_core="point",
                 solver="solve_gls_profiled (exact anchored R11 profiling)",
                 overhead_s=S.T_OVERHEAD, snr_c_1800=float(1.0 / S.noise_sigma(1.0, 1800.0)),
                 qcor_over_qexo=float(S.QCOR / S.QEXO))}

    # --- clouds -------------------------------------------------------
    methods = ("profiled", "v2", "white", "b2", "b1", "b2coarse")
    shape = (len(methods), len(E.FCS), len(E.SEEDS))
    keys = ("pearson", "ssim", "nrmse", "bias", "contrast")
    stack = {k: np.full(shape, np.nan) for k in keys}
    # Land-ocean separation d' is scored from the per-seed reconstruction maps,
    # which the cloud parts store for every seed; archiving it here makes the
    # numbers quoted in Section 5.2 reproducible without re-running the solvers.
    dstack = np.full(shape, np.nan)
    truth_c_for_dp = E.truth()[1]
    covers = np.full((len(E.FCS), len(E.SEEDS)), np.nan)
    sigma_cl_by_fc = np.full(len(E.FCS), np.nan)
    maps = {}
    for i, fc in enumerate(E.FCS):
        for j in range(len(E.SEEDS)):
            p = E.part_path(f"clouds_f{i}_s{j}")
            if not p.exists():
                continue
            d = np.load(p)
            covers[i, j] = d["cover"]; sigma_cl_by_fc[i] = d["sigma_cl"]
            for mi, m in enumerate(methods):
                if f"{m}_pearson" not in d:
                    continue
                for k in keys:
                    stack[k][mi, i, j] = d.get(f"{m}_{k}", np.nan)
                if f"map_{m}" in d:
                    dstack[mi, i, j] = S.detection_dprime(
                        d[f"map_{m}"].reshape(E.NLAT, E.NLON), truth_c_for_dp)
            if j == 0:
                for k in d.files:
                    if k.startswith("map_"):
                        maps[f"{k}_fc{i}"] = d[k]
    ns_actual = int(np.sum(np.isfinite(stack["pearson"][0])))
    np.savez(E.DATA / "clouds.npz", fcs=np.array(E.FCS), seeds=np.array(E.SEEDS),
             covers=covers, sigma_cl=sigma_cl_by_fc, n_seeds_actual=ns_actual,
             methods=np.array(methods), truth_c=E.truth()[1],
             **{f"{k}_mat": v for k, v in stack.items()}, dprime_mat=dstack, **maps)
    fcbest = int(np.nanargmax(np.nanmean(stack["pearson"][0], axis=1)))
    audit["clouds"] = dict(
        methods=list(methods), n_seeds_claimed=len(E.SEEDS), n_seeds_actual=ns_actual,
        pearson_mean={m: _ms(stack["pearson"][mi]) for mi, m in enumerate(methods)},
        pearson_sd_pooled={m: _sd(stack["pearson"][mi])
                           for mi, m in enumerate(methods)},
        fiducial=dict(fc=E.FCS[fcbest], r_profiled=_ms(stack["pearson"][0, fcbest]),
                      r_v2=_ms(stack["pearson"][1, fcbest]),
                      r_white=_ms(stack["pearson"][2, fcbest]),
                      r_b2=_ms(stack["pearson"][3, fcbest]),
                      bias_profiled=_ms(stack["bias"][0, fcbest]),
                      contrast_profiled=_ms(stack["contrast"][0, fcbest]),
                      contrast_b2=_ms(stack["contrast"][3, fcbest]),
                      r_b1=_ms(stack["pearson"][4, fcbest]),
                      r_b2coarse=_ms(stack["pearson"][5, fcbest]),
                      nbins_b2=E.NBINS_B2, nbins_b2_coarse=E.NBINS_B2_COARSE),
        sigma_cl=sigma_cl_by_fc.tolist(),
        dprime_cloudfree={m: _ms(dstack[mi, 0]) for mi, m in enumerate(methods)},
        dprime_fiducial={m: _ms(dstack[mi, E.FCS.index(E.FC)])
                         for mi, m in enumerate(methods)},
        dprime_truth=float(S.detection_dprime(truth_c_for_dp, truth_c_for_dp)),
        variance_ratio_by_fc=[float((sigma_cl_by_fc[i] / S.noise_sigma(1.0, 1800.0)) ** 2)
                              for i in range(len(E.FCS))],
        sigma_ratio_by_fc=[float(sigma_cl_by_fc[i] / S.noise_sigma(1.0, 1800.0))
                           for i in range(len(E.FCS))])
    if ns_actual:
        a = stack["pearson"][0, fcbest]; b = stack["pearson"][3, fcbest]
        ok = np.isfinite(a) & np.isfinite(b)
        audit["clouds"]["paired_tdi_vs_b2"] = E.paired_stats(a[ok], b[ok])
        a = stack["pearson"][0, fcbest]; b = stack["pearson"][2, fcbest]
        ok = np.isfinite(a) & np.isfinite(b)
        audit["clouds"]["paired_tdi_vs_white"] = E.paired_stats(a[ok], b[ok])

    # --- cadence (both arms) -----------------------------------------
    mp_arr = np.array([c[1] for c in E.ARM_PHOTONS], float)
    tss_by_arm = {}
    for arm in ("photons", "wallclock"):
        r = {m: np.full((len(mp_arr), len(E.CAD_SEEDS)), np.nan)
             for m in ("profiled", "v2", "white", "b2", "b1", "b2coarse")}
        walls = np.full(len(mp_arr), np.nan); tss = np.full(len(mp_arr), np.nan)
        phot = np.full(len(mp_arr), np.nan); duty = np.full(len(mp_arr), np.nan)
        expd = np.full(len(mp_arr), np.nan); ovd = np.full(len(mp_arr), np.nan)
        for i in range(len(mp_arr)):
            for j in range(len(E.CAD_SEEDS)):
                p = E.part_path(f"cad_{arm}_c{i}_s{j}")
                if not p.exists():
                    continue
                d = np.load(p)
                walls[i] = d["wall"]; tss[i] = d["ts"]; phot[i] = d["photons_h"]
                duty[i] = d["duty"]; expd[i] = d["exposure_days"]; ovd[i] = d["overhead_days"]
                for m in r:
                    if f"{m}_pearson" in d:
                        r[m][i, j] = d[f"{m}_pearson"]
        np.savez(E.DATA / f"cadence_{arm}.npz", mp=mp_arr, ts=tss, wall=walls,
                 photons_h=phot, duty=duty, exposure_days=expd, overhead_days=ovd,
                 **{f"r_{m}": r[m] for m in r})
        tss_by_arm[arm] = tss.copy()
        audit[f"cadence_{arm}"] = dict(
            mp=mp_arr.tolist(), ts=tss.tolist(), wall_days=walls.tolist(),
            photons_h=phot.tolist(), duty=duty.tolist(),
            exposure_days=expd.tolist(), overhead_days=ovd.tolist(),
            fits_90d=[bool(x <= E.ARM_WALL + 1e-9) for x in walls],
            r_profiled=[_ms(r["profiled"][i]) for i in range(len(mp_arr))],
            r_v2=[_ms(r["v2"][i]) for i in range(len(mp_arr))],
            r_white=[_ms(r["white"][i]) for i in range(len(mp_arr))],
            r_b2=[_ms(r["b2"][i]) for i in range(len(mp_arr))],
            r_b1=[_ms(r["b1"][i]) for i in range(len(mp_arr))],
            n_seeds=int(np.sum(np.isfinite(r["profiled"][0]))))
    cad_note = ("arm A holds mp*ts = 8 h per raster position and lets the wall "
                "clock exceed 90 d; arm B holds wall <= 90 d and lets ts fall. "
                "They cannot both hold.")
    audit["cadence_note"] = cad_note

    # --- cadence causal controls (cf / iid), per arm (R6, R16) ---------
    def _ps(x, y):
        x = np.asarray(x, float); y = np.asarray(y, float)
        ok = np.isfinite(x) & np.isfinite(y)
        return E.paired_stats(x[ok], y[ok]) if ok.sum() >= 2 else None
    ctl = {}
    for arm in ("photons", "wallclock"):
        rows = {"cf": np.full((len(mp_arr), len(E.CAD_SEEDS)), np.nan),
                "iid": np.full((len(mp_arr), len(E.CAD_SEEDS)), np.nan),
                "ou": np.full((len(mp_arr), len(E.CAD_SEEDS)), np.nan)}
        cover = {k: np.full(len(mp_arr), np.nan) for k in rows}
        sc_used = np.full(len(mp_arr), np.nan)
        for i in range(len(mp_arr)):
            for j in range(len(E.CAD_SEEDS)):
                p = E.part_path(f"cad_{arm}_c{i}_s{j}")
                if p.exists():
                    rows["ou"][i, j] = np.load(p)["profiled_pearson"]
                for kind in ("cf", "iid"):
                    q = E.part_path(f"cadctl_{arm}_c{i}_{kind}_s{j}")
                    if q.exists():
                        d = np.load(q)
                        rows[kind][i, j] = d["pearson"]
                        cover[kind][i] = d["cover"]
                        sc_used[i] = d["sigma_cl_used"]
        if np.isfinite(rows["cf"]).any() or np.isfinite(rows["iid"]).any():
            np.savez(E.DATA / f"cadence_controls_{arm}.npz", mp=mp_arr,
                     ts=tss_by_arm[arm],
                     **{f"r_{k}": v for k, v in rows.items()},
                     cover_cf=cover["cf"], cover_iid=cover["iid"],
                     sigma_cl_iid=sc_used)
            ctl[arm] = dict(
                mp=mp_arr.tolist(),
                r_cf=[_ms(rows["cf"][i]) for i in range(len(mp_arr))],
                r_iid=[_ms(rows["iid"][i]) for i in range(len(mp_arr))],
                r_ou=[_ms(rows["ou"][i]) for i in range(len(mp_arr))],
                paired_cf_minus_ou=[_ps(rows["cf"][i], rows["ou"][i])
                                    for i in range(len(mp_arr))],
                paired_iid_minus_ou=[_ps(rows["iid"][i], rows["ou"][i])
                                     for i in range(len(mp_arr))],
                note=("cf = cloud-free scene at the same campaign and seeds; "
                      "iid = per-pass independent clouds scored with the OU "
                      "covariance (sigma_cl held at the OU fiducial value), so "
                      "only the temporal structure of the weather changes"))
    if ctl:
        audit["cadence_controls"] = ctl

    # --- resource ledger + effective independent looks (R13) ----------
    lp = E.DATA / "ledger.npz"
    if lp.exists():
        L = np.load(lp)
        ph = L["arm"] == "photons"
        audit["ledger"] = dict(
            photons=dict(mp=L["mp"][ph].tolist(), ts=L["ts"][ph].tolist(),
                         wall_days=L["wall"][ph].tolist(),
                         photons_h=L["photons"][ph].tolist(),
                         duty=L["duty"][ph].tolist(),
                         fits_90d=[bool(x) for x in L["fits90"][ph]]),
            wallclock=dict(mp=L["mp"][~ph].tolist(), ts=L["ts"][~ph].tolist(),
                           wall_days=L["wall"][~ph].tolist(),
                           photons_h=L["photons"][~ph].tolist(),
                           duty=L["duty"][~ph].tolist()),
            neff_tau_days=L["neff_tau"].tolist(),
            neff_mp=L["neff_mp"].tolist(),
            neff=L["neff"].tolist(),
            neff_fraction=[[L["neff"][t, i] / L["neff_mp"][i]
                            for i in range(len(L["neff_mp"]))]
                           for t in range(len(L["neff_tau"]))],
            inter_look_spacing_days=L["neff_spacing_d"][0].tolist(),
            ou_lag1_correlation=L["neff_rho1"].tolist(),
            note=("N_eff = mp^2/(mp + 2 sum_k (mp-k) exp(-k dt/tau)) with dt the "
                  "FULL pass time between revisits of one raster position; the "
                  "mp revisits of a pixel are 5.47 d apart at the fiducial "
                  "campaign, i.e. only ~1.4 cloud-correlation times, so they are "
                  "NOT independent looks and the gain from mp saturates."))

    # --- components ---------------------------------------------------
    comps = ("A_white_nodefl", "B_ou_nodefl", "C_v2_deflate", "D_profiled_anchor",
             "E_profiled_free", "F_full_tdi")
    cm = {c: np.full(len(E.SEEDS), np.nan) for c in comps}
    cs = {c: np.full(len(E.SEEDS), np.nan) for c in comps}
    cb = {c: np.full(len(E.SEEDS), np.nan) for c in comps}
    dev = {c: np.full(len(E.SEEDS), np.nan) for c in comps}
    nrm = {c: np.full(len(E.SEEDS), np.nan) for c in comps}
    for j in range(len(E.SEEDS)):
        p = E.part_path(f"comp_s{j}")
        if not p.exists():
            continue
        d = np.load(p)
        for c in comps:
            cm[c][j] = d.get(f"{c}_pearson", np.nan)
            cs[c][j] = d.get(f"{c}_ssim", np.nan)
            cb[c][j] = d.get(f"{c}_bias", np.nan)
            dev[c][j] = d.get(f"reldev_{c}", np.nan)
            nrm[c][j] = d.get(f"norm_{c}", np.nan)
    np.savez(E.DATA / "component_ablation.npz", methods=np.array(comps),
             seeds=np.array(E.SEEDS), **{f"r_{c}": v for c, v in cm.items()},
             **{f"ssim_{c}": v for c, v in cs.items()},
             **{f"bias_{c}": v for c, v in cb.items()},
             **{f"reldev_{c}": v for c, v in dev.items()},
             **{f"norm_{c}": v for c, v in nrm.items()})
    audit["components"] = {c: dict(r=_ms(cm[c]), ssim=_ms(cs[c]), bias=_ms(cb[c]),
                                  reldev_vs_D_mean=float(np.nanmean(dev[c])),
                                  norm_mean=float(np.nanmean(nrm[c])))
                           for c in comps}
    audit["components"]["paired_D_vs_C"] = E.paired_stats(cm["D_profiled_anchor"],
                                                          cm["C_v2_deflate"])
    audit["components"]["paired_F_vs_B"] = E.paired_stats(cm["F_full_tdi"],
                                                          cm["B_ou_nodefl"])
    audit["components"]["norm_ratio_C_vs_D"] = float(
        np.nanmean(nrm["C_v2_deflate"] / nrm["D_profiled_anchor"]))

    # --- robustness ---------------------------------------------------
    rob = {}
    seeds_have = []
    for j in range(len(E.SEEDS)):
        p = E.part_path(f"robdebias_s{j}")
        if not p.exists():
            continue
        seeds_have.append(E.SEEDS[j])
        d = np.load(p)
        for k in d.files:
            if k == "seed":
                continue
            rob.setdefault(k, []).append(float(d[k]))
    if seeds_have:
        flat = {k: float(np.mean(v)) for k, v in rob.items()}
        np.savez(E.DATA / "robust_debias.npz", seeds=np.array(seeds_have), **flat)
        audit["robust_debias"] = dict(n_seeds=len(seeds_have), seeds=seeds_have)
        for pre in ("bias", "rms", "con", "r"):
            rows = {k: flat[k] for k in flat if k.startswith(pre + "_")}
            audit["robust_debias"][pre] = {k.split("_", 1)[1]: v for k, v in rows.items()}
        audit["robust_debias"]["worst_abs_bias"] = max(
            abs(v) for k, v in flat.items() if k.startswith("bias_"))
        audit["robust_debias"]["r_range"] = [min(v for k, v in flat.items()
                                                 if k.startswith("r_")),
                                             max(v for k, v in flat.items()
                                                 if k.startswith("r_"))]
        audit["robust_debias"]["note"] = ("Pearson r is invariant to the affine "
                                          "debiasing error; bias/RMSE/contrast are "
                                          "what move")
    # climatology
    clim = {}
    for tag in ("itcz", "surf", "multitau", "iid"):
        vals = []
        for j in range(len(E.SEEDS)):
            p = E.part_path(f"robclim_{tag}_s{j}")
            if p.exists():
                vals.append(np.load(p))
        if vals:
            clim[tag] = dict(n_seeds=len(vals),
                             cover=_ms([d["cover"] for d in vals]),
                             pearson=_ms([d["pearson"] for d in vals]),
                             ssim=_ms([d["ssim"] for d in vals]),
                             bias=_ms([d["bias"] for d in vals]))
    if clim:
        audit["robust_clim"] = clim
    # geometry
    geom = {}
    for kind, fmt in (("tilt", (0.0, 5.0, 20.0)), ("phase", (5.0, 15.0, 30.0, 60.0))):
        for v in fmt:
            vals = []
            for j in range(len(E.SEEDS)):
                p = E.part_path(f"robgeom_{kind}{v:g}_s{j}")
                if p.exists():
                    vals.append(np.load(p)["pearson"])
            if vals:
                geom[f"{kind}{v:g}"] = _ms(vals)
    if geom:
        audit["robust_geom"] = geom
    # profile likelihood
    prof = []
    for j in range(len(E.PROF_SEEDS)):
        p = E.part_path(f"robprof_s{j}")
        if p.exists():
            prof.append(np.load(p))
    if prof:
        chi2 = np.mean([d["chi2"] for d in prof], axis=0)
        free = np.mean([d["free"] for d in prof], axis=0)
        rr = np.mean([d["r"] for d in prof], axis=0)
        pe = np.asarray(prof[0]["prot_errs"]); phe = np.asarray(prof[0]["phase_errs"])
        np.savez(E.DATA / "profile_likelihood.npz", prot_errs=pe, phase_errs=phe,
                 chi2=chi2, chi2_free=free, r=rr, n_seeds=len(prof))
        i, jj = np.unravel_index(np.argmin(chi2), chi2.shape)
        audit["profile_likelihood"] = dict(
            n_seeds=len(prof), chi2=chi2.tolist(), chi2_free=free.tolist(),
            r_at_grid=rr.tolist(), argmin_prot_err=float(pe[i]),
            argmin_phase_deg=float(phe[jj]), chi2_min=float(chi2[i, jj]),
            delta_across_phase_at_best_period=[float(x - chi2[i].min()) for x in chi2[i]],
            delta_across_period_at_best_phase=[float(x - chi2[:, jj].min()) for x in chi2[:, jj]])
        g = np.gradient(chi2[:, jj], pe, axis=0)
        audit["profile_likelihood"]["period_curvature_d2chi2_per_prot"] = float(
            np.nanmax(np.abs(g)))
        audit["profile_likelihood"]["phase_curvature_d2chi2_per_deg"] = float(
            np.nanmax(np.abs(np.gradient(chi2[i], phe * np.pi / 180.0, axis=0))))
    # resolution / nulls
    l = None; r_cf = []; r_cl = []; quad = []
    for j in range(len(E.SEEDS)):
        p = E.part_path(f"res_s{j}")
        if p.exists():
            d = np.load(p)
            l = d["l"]; r_cf.append(d["r_cf"]); r_cl.append(d["r_cl"])
            quad.append(d["quadrature_err"])
    if r_cf:
        r_cf = np.array(r_cf); r_cl = np.array(r_cl); quad = np.array(quad)
        np.savez(E.DATA / "spatial_resolution.npz", l=l, r_cf=r_cf, r_cl=r_cl,
                 quadrature_err=quad,
                 l_eff_cf=[_first_below(l, x) for x in r_cf],
                 l_eff_cl=[_first_below(l, x) for x in r_cl])
        leff = [x for x in [_first_below(l, y) for y in r_cl] if x is not None]
        audit["resolution"] = dict(
            n_seeds=len(r_cf), l=l.tolist(), r_cf_mean=r_cf.mean(0).tolist(),
            r_cl_mean=r_cl.mean(0).tolist(), r_cl_sd=r_cl.std(0, ddof=1).tolist(),
            quadrature_err_mean=quad.mean(0).tolist(),
            l_eff_cf=[x for x in [_first_below(l, y) for y in r_cf]],
            l_eff_cl=[x for x in [_first_below(l, y) for y in r_cl]],
            scale_km=[S.harmonic_l_to_scale_km(x) for x in (leff or [np.nan])])
    dp = []
    for j in range(len(E.SEEDS)):
        q = E.part_path(f"null_s{j}")
        if q.exists():
            d = np.load(q)
            dp.append(dict(seed=int(d["seed"]), d_obs=float(d["d_obs"]),
                           perm_p=float(d["perm_p"]), cloud_p=float(d["cloud_p"]),
                           perm_null_mean=float(np.mean(d["perm_null"])),
                           perm_null_95=float(np.percentile(d["perm_null"], 95))))
    if dp:
        np.savez(E.DATA / "nulls.npz",
                 **{k: np.array([x[k] for x in dp]) for k in dp[0]})
        cp = np.array([x["cloud_p"] for x in dp]); pp = np.array([x["perm_p"] for x in dp])
        ens = np.load(E.DATA / "nulls_cloud_ensemble.npz")
        audit["nulls"] = dict(
            n_seeds=len(dp), d_observed=[x["d_obs"] for x in dp],
            cloud_null_p=cp.tolist(), perm_null_p=pp.tolist(),
            cloud_null_p_min=float(cp.min()), perm_null_p_min=float(pp.min()),
            cloud_null_ensemble=dict(mean=float(ens["d"].mean()),
                                     sd=float(ens["d"].std(ddof=1)),
                                     p95=float(np.percentile(ens["d"], 95)),
                                     n_real=int(ens["n_real"])),
            note=("with 10 paired seeds the exact minimum two-sided sign-flip p is "
                  "1.95e-3; the cloud-only null has n=40 realizations so its "
                  "smallest attainable rank p is 1/41"))
    # systematics
    sysrows = [np.load(E.part_path(f"sys_s{j}")) for j in range(len(E.SEEDS))
               if (E.part_path(f"sys_s{j}")).exists()]
    if sysrows:
        eps = sysrows[0]["eps"]
        kinds = ("drift", "streamer", "both")
        agg = {(k, m): np.array([d[f"{k}_{m}"] for d in sysrows])
               for k in kinds for m in ("r", "ssim", "bias", "nrmse")}
        np.savez(E.DATA / "systematics.npz", eps=eps,
                 **{f"{k}_{m}": v.mean(0) for (k, m), v in agg.items()},
                 **{f"{k}_{m}_sd": v.std(0, ddof=1) for (k, m), v in agg.items()},
                 base_r=np.array([d["base_r"] for d in sysrows]).mean(),
                 qcor_over_qexo=float(sysrows[0]["qcor_over_qexo"]),
                 eps_one_sigma=float(np.mean([d["eps_one_sigma"] for d in sysrows])),
                 bg_ref_snr=float(np.mean([d["bg_ref_snr"] for d in sysrows])),
                 bg_extra_sigma=float(np.mean([d["bg_extra_sigma"] for d in sysrows])),
                 n_seeds=len(sysrows))
        audit["systematics"] = dict(
            n_seeds=len(sysrows), eps=eps.tolist(),
            qcor_over_qexo=float(sysrows[0]["qcor_over_qexo"]),
            base_r=float(np.mean([d["base_r"] for d in sysrows])),
            epsilon_below_one_photon_sigma=float(
                np.mean([d["eps_one_sigma"] for d in sysrows])),
            background_reference=dict(
                ref_snr_equal_tb=float(np.mean([d["bg_ref_snr"] for d in sysrows])),
                extra_sigma=float(np.mean([d["bg_extra_sigma"] for d in sysrows]))),
            by_kind={k: dict(r=agg[(k, "r")].mean(0).tolist(),
                             r_sd=agg[(k, "r")].std(0, ddof=1).tolist(),
                             ssim=agg[(k, "ssim")].mean(0).tolist(),
                             bias=agg[(k, "bias")].mean(0).tolist(),
                             nrmse=agg[(k, "nrmse")].mean(0).tolist())
                      for k in kinds},
            note=("amplitudes are fractional residuals OF THE CORONAL BACKGROUND; "
                  "multiply by Qcor/Qexo = 7.7403e4 to get planet-reference units"))
    # lambda sweep
    lamrows = {}
    for i_fc in range(len(E.FCS)):
        rows = [np.load(E.part_path(f"lamsweep_f{i_fc}_s{j}"))
                for j in range(len(E.SEEDS))
                if (E.part_path(f"lamsweep_f{i_fc}_s{j}")).exists()]
        xt = [np.load(E.part_path(f"lamsweepxt_f{i_fc}_s{j}"))
              for j in range(len(E.SEEDS))
              if (E.part_path(f"lamsweepxt_f{i_fc}_s{j}")).exists()]
        if rows:
            lamrows[i_fc] = (rows, xt)
    if lamrows:
        audit["lambda_sweep"] = {}
        for i_fc, (rows, xt) in lamrows.items():
            lam = np.concatenate([rows[0]["lam"]] +
                                 ([xt[0]["lam"]] if len(xt) == len(rows) else []))
            same = len(xt) == len(rows)
            def col(key, part):
                n = len(part[0]["lam"]) if "lam" in part[0] else 0
                return np.array([[float(d[key][k]) if key in d else np.nan
                                  for k in range(n)] for d in part])
            def cat(key):
                a = col(key, rows)
                return np.concatenate([a, col(key, xt)], axis=1) if same else a
            R, C = cat("r"), cat("chi2")
            np.savez(E.DATA / f"lambda_sweep_f{i_fc}.npz", lam=lam, r=R, chi2=C,
                     ssim=cat("ssim"), bias=cat("bias"),
                     contrast=col("contrast", xt) if same else np.zeros((0, 0)),
                     n_lam_base=int(rows[0]["lam"].size),
                     seeds=np.array([d["seed"] for d in rows]),
                     fc=float(rows[0]["fc"]), sigma_cl=float(rows[0]["sigma_cl"]))
            rel = C / C[:, int(np.argmin(np.abs(np.asarray(lam, float)
                                                - E.LAM_GLS)))][:, None]
            audit["lambda_sweep"][f"fc{E.FCS[i_fc]:g}"] = dict(
                lam=lam.tolist(), r=[_ms(R[:, k]) for k in range(len(lam))],
                r_sd=[_sd(R[:, k]) for k in range(len(lam))],
                chi2_relative_to_fiducial=[_ms(rel[:, k]) for k in range(len(lam))],
                extended=same, n_seeds=len(rows))
    # is the large-lambda r gain recovery or blur?
    lr = {}
    for i_fc in range(len(E.FCS)):
        rows = [np.load(E.part_path(f"lamres_f{i_fc}_s{j}"))
                for j in range(4)
                if (E.part_path(f"lamres_f{i_fc}_s{j}")).exists()]
        if rows:
            lr[i_fc] = rows
    if lr:
        bands = [(0, 4), (4, 8), (8, 12), (12, 16), (16, 20)]
        out = {}
        allr = {}
        for i_fc, rows in lr.items():
            lamv = rows[0]["lam"]
            Re = np.array([d["r_ell"] for d in rows])          # (seed, lam, ell)
            # mean over seeds AND harmonics within the band, per lambda
            bb = np.array([[Re[:, k, a:b].mean() for a, b in bands]
                           for k in range(len(lamv))])           # (lam, band)
            # SE across seeds of that band's per-seed mean
            sd = np.array([[Re[:, k, a:b].mean(1).std(ddof=1) / np.sqrt(len(rows))
                            for a, b in bands]
                           for k in range(len(lamv))])
            out[f"fc{E.FCS[i_fc]:g}"] = dict(
                lam=lamv.tolist(), n_seeds=len(rows),
                band_r=[[float(x) for x in row] for row in bb],
                band_r_sd=[[float(x) for x in row] for row in sd],
                pearson=[_ms(np.array([d["pearson"][k] for d in rows]))
                         for k in range(len(lamv))],
                ssim=[_ms(np.array([d["ssim"][k] for d in rows]))
                      for k in range(len(lamv))],
                dprime=[_ms(np.array([d["dprime"][k] for d in rows]))
                        for k in range(len(lamv))],
                contrast=[_ms(np.array([d["contrast"][k] for d in rows]))
                          for k in range(len(lamv))])
            allr[f"fc{E.FCS[i_fc]:g}"] = Re
        np.savez(E.DATA / "lambda_resolution.npz",
                 lam=np.array(lr[3][0]["lam"]), l=np.arange(1, 21),
                 bands=np.array(["%d-%d" % (a + 1, b) for a, b in bands]),
                 **{f"r_ell_{k}": v for k, v in allr.items()})
        audit["lambda_resolution"] = dict(bands=["%d-%d" % (a + 1, b)
                                                 for a, b in bands], **out)
    # weather-parameter sensitivity
    wrows = {}
    for tag in WEATHER_GRID:
        rows = [np.load(E.part_path(f"robweather_{tag}_s{j}"))
                for j in range(len(E.SEEDS))
                if (E.part_path(f"robweather_{tag}_s{j}")).exists()]
        if rows:
            wrows[tag] = rows
    if wrows:
        tags = sorted(wrows)
        nw = len(E.SEEDS)
        def _col(tag, key):
            v = np.full(nw, np.nan)
            for d in wrows[tag]:
                v[E.SEEDS.index(int(d["seed"]))] = float(d[key])
            return v
        ws = {}
        for mode in ("misspecified", "recalibrated"):
            Mm = np.column_stack([_col(t, f"{mode}_r") for t in tags])
            ws[mode] = dict(r=[_ms(Mm[:, k]) for k in range(len(tags))],
                            r_sd=[_sd(Mm[:, k]) for k in range(len(tags))],
                            ssim=[_ms([d[f"{mode}_ssim"] for d in wrows[t]]) for t in tags],
                            bias=[_ms([d[f"{mode}_bias"] for d in wrows[t]]) for t in tags])
            np.savez(E.DATA / f"weather_{mode}.npz", variants=np.array(tags), r=Mm)
        paired = [_ps(_col(t, "recalibrated_r"), _col(t, "misspecified_r"))
                  for t in tags]
        np.savez(E.DATA / "weather_sensitivity.npz", variants=np.array(tags),
                 cover=[_ms([d["cover"] for d in wrows[t]]) for t in tags],
                 sigma_cl_fid=[float(wrows[t][0]["sigma_cl_fid"]) for t in tags],
                 sigma_cl_var=[float(wrows[t][0]["sigma_cl_var"]) for t in tags],
                 r_misspec=np.array(ws["misspecified"]["r"]),
                 r_recalc=np.array(ws["recalibrated"]["r"]))
        audit["weather"] = dict(
            variants=tags, grid={k: v for k, v in WEATHER_GRID.items()},
            cover=[float(np.mean([d["cover"] for d in wrows[t]])) for t in tags],
            sigma_cl_fid=[float(wrows[t][0]["sigma_cl_fid"]) for t in tags],
            sigma_cl_var=[float(wrows[t][0]["sigma_cl_var"]) for t in tags],
            r_misspec=ws["misspecified"]["r"], r_misspec_sd=ws["misspecified"]["r_sd"],
            r_recalc=ws["recalibrated"]["r"], r_recalc_sd=ws["recalibrated"]["r_sd"],
            ssim_misspec=ws["misspecified"]["ssim"], ssim_recalc=ws["recalibrated"]["ssim"],
            bias_misspec=ws["misspecified"]["bias"], bias_recalc=ws["recalibrated"]["bias"],
            paired_recalc_minus_misspec=paired,
            n_seeds={t: len(wrows[t]) for t in tags},
            note=("true weather field varied in spatial correlation length, advection "
                  "rate and decorrelation time; each variant scored with the fiducial "
                  "OU climatology (misspecified) and with its own (recalibrated)"))
    # sigma_cl sensitivity of the reconstruction
    sgrows = [np.load(E.part_path(f"sigcl_s{j}")) for j in range(len(E.SEEDS))
              if (E.part_path(f"sigcl_s{j}")).exists()]
    if sgrows:
        fac = sgrows[0]["factors"]
        R = np.array([d["r"] for d in sgrows]); C = np.array([d["chi2"] for d in sgrows])
        np.savez(E.DATA / "sigma_sensitivity.npz", factors=fac, r=R, chi2=C,
                 ssim=np.array([d["ssim"] for d in sgrows]),
                 sigma_cl=float(sgrows[0]["sigma_cl"]),
                 seeds=np.array([d["seed"] for d in sgrows]))
        i1 = int(np.argmin(np.abs(fac - 1.0)))
        rel = C / C[:, i1][:, None]
        # Section 5.14 quotes the per-seed max-minus-min over the factors at or
        # above 0.25x (the full-range spread is inflated by the sigma_cl = 0
        # corner, where the whitening is degenerate), so archive both.
        keep = fac >= 0.25
        spread_hi = R[:, keep].max(1) - R[:, keep].min(1)
        audit["sigma_sensitivity"] = dict(
            factors=fac.tolist(), r=[_ms(R[:, k]) for k in range(len(fac))],
            r_sd=[_sd(R[:, k]) for k in range(len(fac))],
            r_spread=[_ms([d["r_spread"] for d in sgrows])],
            r_spread_ge_0p25=_ms(spread_hi),
            chi2_ratio_vs_fiducial=[_ms(rel[:, k]) for k in range(len(fac))],
            sigma_cl=float(sgrows[0]["sigma_cl"]), n_seeds=len(sgrows),
            note=("sigma_cl is the ASSUMED cloud amplitude; r is scored against "
                  "truth while chi2 is the whitened objective under that same "
                  "assumed covariance"))
    # sigma_cl sensitivity for the other two estimators (free, v2 deflation)
    sge = {}
    for est in SIGCL_ESTS:
        rws = [np.load(E.part_path(f"sigcl{est}_s{j}"))
               for j in range(len(E.SEEDS))
               if (E.part_path(f"sigcl{est}_s{j}")).exists()]
        if rws:
            sge[est] = rws
    if sge:
        est_out = {}
        for est, rws in sge.items():
            fac = rws[0]["factors"]
            R = np.array([d["r"] for d in rws])
            est_out[est] = dict(
                factors=fac.tolist(), n_seeds=len(rws),
                r=[_ms(R[:, k]) for k in range(len(fac))],
                r_sd=[_sd(R[:, k]) for k in range(len(fac))],
                r_spread=[_ms([d["r_spread"] for d in rws])],
                r_spread_ge_0p25=_ms(R[:, fac >= 0.25].max(1)
                                      - R[:, fac >= 0.25].min(1)))
            np.savez(E.DATA / f"sigma_sensitivity_{est}.npz", factors=fac, r=R,
                     ssim=np.array([d["ssim"] for d in rws]),
                     sigma_cl=float(rws[0]["sigma_cl"]),
                     seeds=np.array([d["seed"] for d in rws]))
        audit["sigma_sensitivity_estimators"] = est_out
    # static ideal-data reference
    strows = [np.load(E.part_path(f"staticref_s{j}")) for j in range(len(E.SEEDS))
              if (E.part_path(f"staticref_s{j}")).exists()]
    if strows:
        keys = ("stat", "rot", "cloud")
        st = {k: np.array([d[f"{k}_r"] for d in strows]) for k in keys}
        np.savez(E.DATA / "static_reference.npz",
                 seeds=np.array([d["seed"] for d in strows]),
                 **{f"{k}_r": st[k] for k in keys},
                 **{f"{k}_{m}": np.array([d[f"{k}_{m}"] for d in strows])
                    for k in keys for m in ("ssim", "nrmse", "bias")})
        audit["static_reference"] = dict(
            r={k: _ms(v) for k, v in st.items()},
            r_sd={k: _sd(v) for k, v in st.items()},
            paired_rot_minus_stat=_ps(st["rot"], st["stat"]),
            paired_cloud_minus_rot=_ps(st["cloud"], st["rot"]),
            photons_per_pixel_h=float(strows[0]["photons_per_pixel_h"]),
            n_seeds=len(strows),
            note=("stat = frozen planet, no weather, identical dose per raster "
                  "position; rot = same estimator on the rotating cloud-free "
                  "campaign; cloud = fiducial rotating cloudy campaign"))
    # surface-map morphology sensitivity
    mrows = {}
    for i_fc in range(len(E.FCS)):
        for morph in MORPHS:
            rows = [np.load(E.part_path(f"morph_{morph}_f{i_fc}_s{j}"))
                    for j in range(len(E.SEEDS))
                    if (E.part_path(f"morph_{morph}_f{i_fc}_s{j}")).exists()]
            if rows:
                mrows[(morph, i_fc)] = rows
    if mrows:
        # earthlike reference from the fiducial clouds parts, matched by seed
        base = {}
        for i_fc in (0, 3):
            for j in range(len(E.SEEDS)):
                p = E.part_path(f"clouds_f{i_fc}_s{j}")
                if p.exists():
                    d = np.load(p)
                    base[(i_fc, int(d["seed"]))] = (float(d["profiled_pearson"]),
                                                    float(d["profiled_ssim"]))
        out = {}
        for (morph, i_fc), rows in mrows.items():
            fc = E.FCS[i_fc]
            r = np.array([float(d["r"]) for d in rows])
            ss = np.array([float(d["ssim"]) for d in rows])
            dp = np.array([float(d["dprime"]) for d in rows])
            seeds = [int(d["seed"]) for d in rows]
            ref = np.array([base.get((i_fc, s), (np.nan, np.nan))[0]
                            for s in seeds])
            out[f"{morph}_f{fc:g}"] = dict(
                n_seeds=len(rows), sigma_cl=float(rows[0]["sigma_cl"]),
                cover=float(np.mean([d["cover"] for d in rows])),
                truth_land=float(rows[0]["truth_land"]),
                truth_mean=float(rows[0]["truth_mean"]),
                truth_sd=float(rows[0]["truth_sd"]),
                r=_ms(r), r_sd=_sd(r), ssim=_ms(ss), dprime=_ms(dp),
                earthlike_r=_ms(ref),
                paired_vs_earthlike=_ps(r, ref))
            np.savez(E.DATA / f"morphology_{morph}_f{fc:g}.npz",
                     seeds=np.array(seeds), r=r, ssim=ss, dprime=dp,
                     earthlike_r=ref, sigma_cl=float(rows[0]["sigma_cl"]),
                     cover=np.array([float(d["cover"]) for d in rows]))
        audit["morphology"] = out
    # quality vs latitude and illumination coverage
    lb = E.DATA / "latband.npz"
    if lb.exists():
        d = np.load(lb, allow_pickle=True)
        nb = len(d["bands"])
        per = {}
        for pre in ("cloud", "clear"):
            key = f"{pre}_r"
            if not any(f"{key}{bi}" in d for bi in range(nb)):
                continue
            M = np.column_stack([d[f"{key}{bi}"] for bi in range(nb)])
            N = np.column_stack([d[f"{pre}_nrmse{bi}"] for bi in range(nb)])
            G = np.column_stack([d[f"{pre}_gain{bi}"] for bi in range(nb)])
            O = np.column_stack([d[f"{pre}_b_off{bi}"] for bi in range(nb)])
            per[pre] = dict(r=[_ms(M[:, bi]) for bi in range(nb)],
                            r_sd=[_sd(M[:, bi]) for bi in range(nb)],
                            nrmse=[_ms(N[:, bi]) for bi in range(nb)],
                            gain=[_ms(G[:, bi]) for bi in range(nb)],
                            band_bias=[_ms(O[:, bi]) for bi in range(nb)])
            ka = f"{pre}_ralive"
            if f"{ka}0" in d:
                A = np.column_stack([d[f"{ka}{bi}"] for bi in range(nb)])
                per[pre]["r_illum_restricted"] = [_ms(A[:, bi])
                                                  for bi in range(nb)]
        audit["latband"] = dict(
            bands=[str(x) for x in d["bands"]],
            dayside=[float(x) for x in d["band_dayside"]],
            weight=[float(x) for x in d["band_weight"]],
            truth_sd=[float(x) for x in d["band_truth_sd"]],
            dead_frac=[float(x) for x in d["band_dead_frac"]],
            disk_pix=[int(x) for x in d["band_disk_pix"]],
            grid_pix=[int(x) for x in d["n_grid_per_band"]],
            n_seeds=int(np.asarray(d["seed"]).size), **per,
            note=("band r is computed on the SAME archived reconstructions as "
                  "the headline numbers, restricted to the band; weight is the "
                  "campaign-mean column energy of F, so zero weight means the "
                  "raster never samples the band; gain is sd(recon)/sd(truth) "
                  "within the band, which Pearson r cannot see"))
    # diagnostics / precision passthrough
    for f in ("deflation_diag.json", "precision.json", "kernel_convergence.json",
              "uniform_disk.json", "core_ablation.json", "kinematics.json",
              "quadrature.npz", "ledger.npz", "validation.npz"):
        if (E.DATA / f).exists():
            audit.setdefault("artifacts", []).append(f)
    (E.DATA / "audit.json").write_text(json.dumps(audit, indent=2, default=float))
    log("merged; audit.json written")


COMMANDS = {
    "setup": lambda a: cmd_setup(),
    "quadrature": lambda a: cmd_quadrature(),
    "ledger": lambda a: cmd_ledger(),
    "validation": lambda a: cmd_validation(),
    "clouds": lambda a: cmd_clouds(a[0]),
    "cadence": lambda a: cmd_cadence(a[0], a[1]),
    "cadence_control": lambda a: cmd_cadence_control(a[0], a[1], a[2]),
    "components": lambda a: cmd_components(),
    "robust_debias": lambda a: cmd_robust_debias(),
    "robust_clim": lambda a: cmd_robust_clim(),
    "robust_geom": lambda a: cmd_robust_geom(),
    "robust_prof": lambda a: cmd_robust_prof(),
    "resolution": lambda a: cmd_resolution(),
    "nulls_cloud": lambda a: cmd_nulls_cloud(),
    "nulls": lambda a: cmd_nulls(),
    "systematics": lambda a: cmd_systematics(),
    "lam_sweep": lambda a: cmd_lam_sweep(a[0]),
    "lam_ext": lambda a: cmd_lam_ext(a[0]),
    "robust_weather": lambda a: cmd_robust_weather(a[0]),
    "sigma_sens": lambda a: cmd_sigma_sens(),
    "sigma_sens_est": lambda a: cmd_sigma_sens_est(),
    "static_ref": lambda a: cmd_static_ref(),
    "robust_morph": lambda a: cmd_robust_morph(a[0]),
    "lam_res": lambda a: cmd_lam_res(a[0]),
    "latband": lambda a: cmd_latband(),
    "diagnostics": lambda a: cmd_diagnostics(),
    "precision": lambda a: cmd_precision(),
    "merge": lambda a: cmd_merge(),
}

if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv or argv[0] not in COMMANDS:
        print("Usage: python run_experiments.py <%s> [args]" % "|".join(COMMANDS))
        sys.exit(1)
    t0 = time.time()
    COMMANDS[argv[0]](argv[1:])
    log("done in %.1f s" % (time.time() - t0))

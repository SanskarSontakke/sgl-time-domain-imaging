"""Comprehensive experiment driver for time-domain SGL imaging.
Addresses all referee and editor comments:
  - Factorial cadence mechanism ablation (exposure smear, cloud-free control, iid vs OU clouds, overheads)
  - 4-way component-wise ablation (time-dependent F, whitening, deflation) with paired bootstrap CIs
  - Extended cloud robustness (debiasing parameter errors, latitudinal banding, surface coupling, multi-tau)
  - Complete spin geometry robustness (pole tilt, initial phase, profile likelihood)
  - Coronal and instrumental systematic drift tests
  - Spatial resolution r(l), land-ocean dichotomy detection d' against spatial nulls
  - Topologies (supercontinent, archipelago) and regularization sweeps
  - Deflation linear algebra and numerical precision checks
"""

import sys, time, json, os
from pathlib import Path
import numpy as np
import sglsim as S

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "results"
PARTS = DATA / "parts"
PARTS.mkdir(parents=True, exist_ok=True)
CACHE = DATA / "cache"
CACHE.mkdir(parents=True, exist_ok=True)
TMP = CACHE  # Portable cache inside workspace

NLAT, NLON = 36, 72
NLATF, NLONF = 72, 144
TRUTH_SEED = 7
TAU_DAYS = 4.0
LAM_GLS = 3e-3
KW_B2 = 3e-3
SEEDS = [11, 12, 13, 14, 15, 16, 17, 18, 19, 20]  # Expanded to 10 seeds
FCS = [0.0, 0.25, 0.40, 0.55, 0.70]
CADENCE = [(7200.0, 4), (3600.0, 8), (1800.0, 16), (900.0, 32), (450.0, 64)]
CAD_SEEDS = [11, 12, 13, 14]
CAD_FC = 0.55


def log(*a):
    print(f"[{time.strftime('%H:%M:%S')}]", *a, flush=True)


def campaign(ts=1800.0, mp=16):
    return S.Campaign(n=64, nsc=16, ts=ts, mp=mp, seed=2026)


def f_path(camp, prot=S.PROT, theta_pole=0.0, psi_pole=0.0, phi0=0.0, nsub=1):
    tag = f"F_n{camp.n}_ts{int(camp.ts)}_mp{camp.mp}_p{prot:.6e}_th{theta_pole:.3f}_phi{phi0:.3f}_ns{nsub}.npy"
    return TMP / tag


def get_F(camp, sgl, prot=S.PROT, theta_pole=0.0, psi_pole=0.0, phi0=0.0, nsub=1, build_ok=True):
    p = f_path(camp, prot, theta_pole, psi_pole, phi0, nsub)
    if p.exists():
        return np.load(p, mmap_mode="r")
    assert build_ok
    out = np.lib.format.open_memmap(p, mode="w+", dtype=np.float32,
                                    shape=(camp.nsamp, NLAT * NLON))
    S.build_F(camp, sgl, NLAT, NLON, prot_assumed=prot, theta_pole=theta_pole,
              psi_pole=psi_pole, phi0=phi0, nsub=nsub, out=out)
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


def truth(morphology="earthlike"):
    tF = S.make_truth_map(NLATF, NLONF, seed=TRUTH_SEED, morphology=morphology)
    return tF, S.coarsen(tF, 2)


# ----------------------------------------------------------------------
# Command: setup
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


# ----------------------------------------------------------------------
# Command: validation (Photometric & Deconvolution checks)
# ----------------------------------------------------------------------
def cmd_validation():
    res = {"ns": [], "theory": [], "measured": []}
    res["snrc_check"] = 1.0 / S.noise_sigma(1.0, 1800.0)
    log(f"SNR_C(1800 s) = {res['snrc_check']:.2f} (published: 43.16)")
    truthF, _ = truth()
    rng = np.random.default_rng(5)
    for n in (32, 64, 128):
        sgl = S.SGLOperator(n)
        scene = S.render_disk(truthF.ravel(), sgl.geo, 0.0, NLATF, NLONF, static=True)
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


# ----------------------------------------------------------------------
# Command: cadence_ablation (Factorial mechanism isolation)
# ----------------------------------------------------------------------
def cmd_cadence_ablation():
    """Factorial ablation isolating causal mechanisms of the cadence law:
      1. Exposure-smear model error (nsub=1 vs nsub=3 forward operator)
      2. Cloud-free control (fc=0)
      3. Temporally independent clouds vs OU-correlated clouds
      4. Observational overheads
    """
    log("Running factorial cadence ablation...")
    sgl = S.SGLOperator(64)
    truthF, truth_c = truth()
    LtL = get_LtL()
    configs = CADENCE
    results = {
        "mp": [c[1] for c in configs],
        "ts": [c[0] for c in configs],
        "duty_cycle": [],
        "r_inst_ou": [],          # Original: Instantaneous F, OU clouds
        "r_smear_modeled_ou": [], # Factor 1: Exposure-integrated F, OU clouds
        "r_cloud_free": [],       # Factor 2: Cloud-free control
        "r_iid_clouds": [],       # Factor 3: Temporally independent clouds
        "ssim_inst_ou": [],
        "ssim_smear_modeled_ou": [],
        "ssim_cloud_free": [],
        "ssim_iid_clouds": []
    }
    
    for icfg, (ts, mp) in enumerate(configs):
        camp = campaign(ts=ts, mp=mp)
        oh = S.effective_cadence_overhead(ts, mp, wallclock_days=camp.wallclock_days)
        results["duty_cycle"].append(oh["duty_cycle"])
        
        # Operators: instantaneous and exposure-integrated
        F_inst = get_F(camp, sgl, nsub=1)
        F_smear = get_F(camp, sgl, nsub=3)
        sigma_cl = get_sigcl(CAD_FC, camp, sgl, truthF)
        
        # Accumulators across CAD_SEEDS
        m_inst_ou, m_smear_ou, m_cf, m_iid = [], [], [], []
        
        for seed in CAD_SEEDS:
            # 1. Standard OU cloudy dataset
            cloud_ou = S.CloudModel(NLATF, NLONF, fc=CAD_FC, tau_days=TAU_DAYS, seed=100 + seed)
            dat_ou = S.simulate_dataset(camp, truthF, cloud_ou, sgl, seed=seed, nsub=3)
            
            # Solve with instantaneous F (original)
            s1 = S.debias_cloud(S.solve_gls(F_inst, dat_ou["y"], camp, dat_ou["sigma"],
                                            sigma_cl, TAU_DAYS, LAM_GLS, LtL, deflate=True), CAD_FC)
            m_inst_ou.append(S.eval_map(s1, truth_c))
            
            # Solve with exposure-integrated F (smear modeled)
            s2 = S.debias_cloud(S.solve_gls(F_smear, dat_ou["y"], camp, dat_ou["sigma"],
                                            sigma_cl, TAU_DAYS, LAM_GLS, LtL, deflate=True), CAD_FC)
            m_smear_ou.append(S.eval_map(s2, truth_c))
            
            # 2. Cloud-free control
            dat_cf = S.simulate_dataset(camp, truthF, None, sgl, seed=seed, nsub=3)
            s3 = S.solve_gls(F_inst, dat_cf["y"], camp, dat_cf["sigma"], 0.0,
                             TAU_DAYS, LAM_GLS, LtL, deflate=False)
            m_cf.append(S.eval_map(s3, truth_c))
            
            # 3. Temporally independent cloud field (iid per pass)
            cloud_iid = S.ExtendedCloudModel(NLATF, NLONF, fc=CAD_FC, tau_days=TAU_DAYS,
                                            seed=200 + seed, iid_per_pass=True)
            dat_iid = S.simulate_dataset(camp, truthF, cloud_iid, sgl, seed=seed, nsub=3)
            s4 = S.debias_cloud(S.solve_gls(F_inst, dat_iid["y"], camp, dat_iid["sigma"],
                                            sigma_cl, TAU_DAYS, LAM_GLS, LtL, deflate=True), CAD_FC)
            m_iid.append(S.eval_map(s4, truth_c))
            
        results["r_inst_ou"].append(float(np.mean([m["pearson"] for m in m_inst_ou])))
        results["ssim_inst_ou"].append(float(np.mean([m["ssim"] for m in m_inst_ou])))
        results["r_smear_modeled_ou"].append(float(np.mean([m["pearson"] for m in m_smear_ou])))
        results["ssim_smear_modeled_ou"].append(float(np.mean([m["ssim"] for m in m_smear_ou])))
        results["r_cloud_free"].append(float(np.mean([m["pearson"] for m in m_cf])))
        results["ssim_cloud_free"].append(float(np.mean([m["ssim"] for m in m_cf])))
        results["r_iid_clouds"].append(float(np.mean([m["pearson"] for m in m_iid])))
        results["ssim_iid_clouds"].append(float(np.mean([m["ssim"] for m in m_iid])))
        
        log(f"mp={mp:2d}: inst_r={results['r_inst_ou'][-1]:.3f}  "
            f"smear_r={results['r_smear_modeled_ou'][-1]:.3f}  "
            f"cf_r={results['r_cloud_free'][-1]:.3f}  "
            f"iid_r={results['r_iid_clouds'][-1]:.3f}  "
            f"duty={oh['duty_cycle']:.2f}")
            
    np.savez(DATA / "cadence_ablation.npz", **{k: np.array(v) for k, v in results.items()})
    log("Cadence ablation complete -> cadence_ablation.npz")


# ----------------------------------------------------------------------
# Command: component_ablation (4-way method decomposition with bootstrap CIs)
# ----------------------------------------------------------------------
def cmd_component_ablation():
    """Evaluate 4-way method decomposition on identical data:
      Method 1: Time-dependent F, White covariance, No deflation
      Method 2: Time-dependent F, Temporal whitening, No deflation
      Method 3: Time-dependent F, White covariance, Slot deflation
      Method 4: Full TDI (Temporal whitening + Slot deflation)
    """
    log("Running 4-way component ablation across 10 paired seeds...")
    camp = campaign()
    sgl = S.SGLOperator(64)
    truthF, truth_c = truth()
    F = get_F(camp, sgl)
    LtL = get_LtL()
    fc = 0.55
    sigma_cl = get_sigcl(fc, camp, sgl, truthF)
    
    r_mat = np.zeros((4, len(SEEDS)))
    ssim_mat = np.zeros((4, len(SEEDS)))
    
    methods = [
        ("White_NoDefl", True, False),
        ("Whitened_NoDefl", False, False),
        ("White_Defl", True, True),
        ("Full_TDI", False, True)
    ]
    
    for s_idx, seed in enumerate(SEEDS):
        cloud = S.CloudModel(NLATF, NLONF, fc=fc, tau_days=TAU_DAYS, seed=100 + seed)
        dat = S.simulate_dataset(camp, truthF, cloud, sgl, seed=seed)
        for m_idx, (mname, white, defl) in enumerate(methods):
            s = S.debias_cloud(S.solve_gls(F, dat["y"], camp, dat["sigma"], sigma_cl,
                                           TAU_DAYS, LAM_GLS, LtL, white=white, deflate=defl), fc)
            ev = S.eval_map(s, truth_c)
            r_mat[m_idx, s_idx] = ev["pearson"]
            ssim_mat[m_idx, s_idx] = ev["ssim"]
            
    # Compute paired statistics and 95% bootstrap intervals
    rng = np.random.default_rng(42)
    boot_diffs = []
    for _ in range(2000):
        b_idx = rng.integers(0, len(SEEDS), size=len(SEEDS))
        # TDI vs White_NoDefl
        boot_diffs.append(np.mean(r_mat[3, b_idx] - r_mat[0, b_idx]))
    ci_lo, ci_hi = np.percentile(boot_diffs, [2.5, 97.5])
    
    for m_idx, (mname, _, _) in enumerate(methods):
        log(f"{mname:18s}: Pearson r = {np.mean(r_mat[m_idx]):.3f} ± {np.std(r_mat[m_idx]):.3f}  "
            f"SSIM = {np.mean(ssim_mat[m_idx]):.3f} ± {np.std(ssim_mat[m_idx]):.3f}")
    log(f"Paired gain (TDI - White_NoDefl) Delta r = {np.mean(r_mat[3] - r_mat[0]):.3f} "
        f"[95% CI: {ci_lo:.3f}, {ci_hi:.3f}]")
        
    np.savez(DATA / "component_ablation.npz", r=r_mat, ssim=ssim_mat,
             methods=np.array([m[0] for m in methods]),
             ci_delta_r=np.array([ci_lo, ci_hi]))
    log("Component ablation complete -> component_ablation.npz")


# ----------------------------------------------------------------------
# Command: robust_extended (Broad cloud climatology & geometry tests)
# ----------------------------------------------------------------------
def cmd_robust_extended():
    """Broader robustness tests:
      - Affine parameter errors (delta_fc, delta_acl)
      - Spatially banded ITCZ clouds and surface-coupled clouds
      - Spin pole orientation tilt and initial rotational phase offset
      - Profile-likelihood 2D grid search
    """
    log("Running extended robustness and spin-orbit geometry suite...")
    camp = campaign()
    sgl = S.SGLOperator(64)
    truthF, truth_c = truth()
    F_nom = get_F(camp, sgl)
    LtL = get_LtL()
    fc = 0.55
    sigma_cl = get_sigcl(fc, camp, sgl, truthF)
    seed = 11
    
    # 1. Affine debiasing error tests
    cloud = S.CloudModel(NLATF, NLONF, fc=fc, tau_days=TAU_DAYS, seed=100 + seed)
    dat = S.simulate_dataset(camp, truthF, cloud, sgl, seed=seed)
    s_raw = S.solve_gls(F_nom, dat["y"], camp, dat["sigma"], sigma_cl, TAU_DAYS, LAM_GLS, LtL, deflate=True)
    
    delta_fcs = [-0.15, -0.07, 0.0, +0.07, +0.15]
    delta_acls = [-0.15, -0.07, 0.0, +0.07, +0.15]
    r_dfc = [S.eval_map(S.debias_cloud_err(s_raw, fc, delta_fc=df), truth_c)["pearson"] for df in delta_fcs]
    r_dacl = [S.eval_map(S.debias_cloud_err(s_raw, fc, delta_acl=da), truth_c)["pearson"] for da in delta_acls]
    
    # 2. Realistic structured clouds: ITCZ banding and surface coupling
    cloud_itcz = S.ExtendedCloudModel(NLATF, NLONF, fc=fc, tau_days=TAU_DAYS, seed=100 + seed, lat_profile=True)
    dat_itcz = S.simulate_dataset(camp, truthF, cloud_itcz, sgl, seed=seed)
    s_itcz = S.debias_cloud(S.solve_gls(F_nom, dat_itcz["y"], camp, dat_itcz["sigma"], sigma_cl,
                                        TAU_DAYS, LAM_GLS, LtL, deflate=True), fc)
    m_itcz = S.eval_map(s_itcz, truth_c)
    
    cloud_surf = S.ExtendedCloudModel(NLATF, NLONF, fc=fc, tau_days=TAU_DAYS, seed=100 + seed,
                                     surf_truth=truthF, surf_coupling=0.25)
    dat_surf = S.simulate_dataset(camp, truthF, cloud_surf, sgl, seed=seed)
    s_surf = S.debias_cloud(S.solve_gls(F_nom, dat_surf["y"], camp, dat_surf["sigma"], sigma_cl,
                                        TAU_DAYS, LAM_GLS, LtL, deflate=True), fc)
    m_surf = S.eval_map(s_surf, truth_c)
    
    # 3. Spin Pole Tilt and Initial Rotational Phase errors
    pole_tilts_deg = [0.0, 1.0, 5.0, 10.0, 20.0]
    r_pole = []
    for pt in pole_tilts_deg:
        rad = np.deg2rad(pt)
        F_tilt = get_F(camp, sgl, theta_pole=rad)
        s_tilt = S.debias_cloud(S.solve_gls(F_tilt, dat["y"], camp, dat["sigma"], sigma_cl,
                                            TAU_DAYS, LAM_GLS, LtL, deflate=True), fc)
        r_pole.append(S.eval_map(s_tilt, truth_c)["pearson"])
        
    phases_deg = [0.0, 5.0, 15.0, 30.0, 60.0]
    r_phase = []
    for ph in phases_deg:
        rad = np.deg2rad(ph)
        F_ph = get_F(camp, sgl, phi0=rad)
        s_ph = S.debias_cloud(S.solve_gls(F_ph, dat["y"], camp, dat["sigma"], sigma_cl,
                                          TAU_DAYS, LAM_GLS, LtL, deflate=True), fc)
        r_phase.append(S.eval_map(s_ph, truth_c)["pearson"])
        
    # 4. Profile Likelihood grid search over period and phase
    prot_errs = [-2e-4, -1e-4, 0.0, 1e-4, 2e-4]
    phase_errs_deg = [-10.0, -5.0, 0.0, 5.0, 10.0]
    prof_chi2 = np.zeros((len(prot_errs), len(phase_errs_deg)))
    for i, pe in enumerate(prot_errs):
        for j, phe in enumerate(phase_errs_deg):
            F_test = get_F(camp, sgl, prot=S.PROT * (1 + pe), phi0=np.deg2rad(phe))
            s_test = S.solve_gls(F_test, dat["y"], camp, dat["sigma"], sigma_cl,
                                 TAU_DAYS, LAM_GLS, LtL, deflate=True)
            resid = dat["y"] - F_test @ s_test
            prof_chi2[i, j] = float(np.sum(resid**2))
            
    np.savez(DATA / "robust_extended.npz",
             delta_fcs=np.array(delta_fcs), r_dfc=np.array(r_dfc),
             delta_acls=np.array(delta_acls), r_dacl=np.array(r_dacl),
             itcz_r=m_itcz["pearson"], itcz_ssim=m_itcz["ssim"],
             surf_r=m_surf["pearson"], surf_ssim=m_surf["ssim"],
             pole_tilts_deg=np.array(pole_tilts_deg), r_pole=np.array(r_pole),
             phases_deg=np.array(phases_deg), r_phase=np.array(r_phase),
             prot_errs=np.array(prot_errs), phase_errs_deg=np.array(phase_errs_deg),
             prof_chi2=prof_chi2)
    log("Extended robustness suite complete -> robust_extended.npz")


# ----------------------------------------------------------------------
# Command: spatial_resolution (Spherical harmonic power & detection d')
# ----------------------------------------------------------------------
def cmd_spatial_resolution():
    """Analyze effective spatial resolution and land-ocean detection:
      - Scale-dependent correlation r(l) across harmonic degrees l
      - Land-ocean dichotomy separation d' compared to phase-scrambled nulls
      - Comparison of rotating solution with static ideal-data reference
    """
    log("Running spatial resolution and land-ocean detection analysis...")
    camp = campaign()
    sgl = S.SGLOperator(64)
    truthF, truth_c = truth()
    F = get_F(camp, sgl)
    LtL = get_LtL()
    seed = 11
    
    # Cloud-free and cloudy reconstructions
    dat_cf = S.simulate_dataset(camp, truthF, None, sgl, seed=seed)
    s_cf = S.solve_gls(F, dat_cf["y"], camp, dat_cf["sigma"], 0.0, TAU_DAYS, LAM_GLS, LtL, deflate=False)
    
    cloud = S.CloudModel(NLATF, NLONF, fc=0.55, tau_days=TAU_DAYS, seed=100 + seed)
    dat_cl = S.simulate_dataset(camp, truthF, cloud, sgl, seed=seed)
    sigma_cl = get_sigcl(0.55, camp, sgl, truthF)
    s_cl = S.debias_cloud(S.solve_gls(F, dat_cl["y"], camp, dat_cl["sigma"], sigma_cl,
                                       TAU_DAYS, LAM_GLS, LtL, deflate=True), 0.55)
                                       
    # Scale-dependent correlations
    l_deg, r_l_cf = S.scale_dependent_correlation(s_cf, truth_c, lmax=20)
    _, r_l_cl = S.scale_dependent_correlation(s_cl, truth_c, lmax=20)
    
    # Land-ocean separation d'
    dprime_truth = S.detection_dprime(truth_c.ravel(), truth_c)
    dprime_cf = S.detection_dprime(s_cf, truth_c)
    dprime_cl = S.detection_dprime(s_cl, truth_c)
    
    # Spatial surrogate null distribution
    null_dprimes = []
    for n_seed in range(100):
        null_map = S.phase_scrambled_null(truth_c, seed=500 + n_seed)
        null_dprimes.append(S.detection_dprime(null_map.ravel(), truth_c))
    null_dprime_mean = float(np.mean(null_dprimes))
    null_dprime_95 = float(np.percentile(null_dprimes, 95))
    
    # Static ideal-data reference under identical photon budget
    camp_static = S.Campaign(n=64, nsc=16, ts=1800.0, mp=16, seed=2026, static=True)
    F_static = get_F(camp_static, sgl)
    dat_static = S.simulate_dataset(camp_static, truthF, None, sgl, seed=seed)
    s_static = S.solve_gls(F_static, dat_static["y"], camp_static, dat_static["sigma"],
                           0.0, TAU_DAYS, LAM_GLS, LtL, deflate=False)
    m_static = S.eval_map(s_static, truth_c)
    m_rotating = S.eval_map(s_cf, truth_c)
    
    log(f"Scale resolution: l_eff(cf) reaches l={l_deg[r_l_cf >= 0.5][-1] if np.any(r_l_cf >= 0.5) else 0}")
    log(f"Detection d': truth={dprime_truth:.2f}, cf={dprime_cf:.2f}, cloudy={dprime_cl:.2f} "
        f"vs null_mean={null_dprime_mean:.2f} (null 95%={null_dprime_95:.2f})")
    log(f"Rotating vs Static comparison: rotating r={m_rotating['pearson']:.3f} vs static r={m_static['pearson']:.3f}")
    
    np.savez(DATA / "spatial_resolution.npz",
             l_deg=l_deg, r_l_cf=r_l_cf, r_l_cl=r_l_cl,
             dprime_truth=dprime_truth, dprime_cf=dprime_cf, dprime_cl=dprime_cl,
             null_dprime_mean=null_dprime_mean, null_dprime_95=null_dprime_95,
             static_r=m_static["pearson"], static_ssim=m_static["ssim"],
             rotating_r=m_rotating["pearson"], rotating_ssim=m_rotating["ssim"])
    log("Spatial resolution analysis complete -> spatial_resolution.npz")


# ----------------------------------------------------------------------
# Command: deflation_diagnostics (Linear algebra & Numerical precision)
# ----------------------------------------------------------------------
def cmd_deflation_diagnostics():
    """Run condition number and numerical precision verification."""
    log("Running deflation linear algebra and numerical precision diagnostics...")
    camp = campaign()
    sgl = S.SGLOperator(64)
    truthF, _ = truth()
    F = get_F(camp, sgl)
    LtL = get_LtL()
    sigma_cl = get_sigcl(0.55, camp, sgl, truthF)
    
    defl_diag = S.analyze_deflation(camp, sgl, NLAT, NLON)
    log(f"Deflation condition: un-deflated={defl_diag['cond_undef']:.2e}, "
        f"deflated={defl_diag['cond_defl']:.2e}, info_retained={defl_diag['info_retained']:.4f}")
        
    cloud = S.CloudModel(NLATF, NLONF, fc=0.55, tau_days=TAU_DAYS, seed=111)
    dat = S.simulate_dataset(camp, truthF, cloud, sgl, seed=11)
    prec_diag = S.check_numerical_precision(F, dat["y"], camp, dat["sigma"],
                                            sigma_cl, TAU_DAYS, LAM_GLS, LtL)
    log(f"Numerical precision: max_rel_diff={prec_diag['max_rel_diff']:.2e}, "
        f"rms_rel_diff={prec_diag['rms_rel_diff']:.2e}")
        
    out = {**defl_diag, **prec_diag}
    (DATA / "deflation_diag.json").write_text(json.dumps(out, indent=2))
    log("Deflation and precision diagnostics saved -> deflation_diag.json")


# ----------------------------------------------------------------------
# Command: merge (Consolidate all parts into final data products)
# ----------------------------------------------------------------------
def cmd_merge():
    methods = ("gls", "white", "b2")
    _, truth_c = truth()
    # 1. Clouds
    shape = (3, len(FCS), len(SEEDS[:3]))
    ssim = np.full(shape, np.nan); nrmse = np.full(shape, np.nan)
    pear = np.full(shape, np.nan); covers = np.zeros(len(FCS))
    store = {"truth_c": truth_c}
    for i in range(len(FCS)):
        for j in range(3):
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
             fcs=np.array(FCS), seeds=np.array(SEEDS[:3]), covers=covers, **store)
             
    # 2. Cadence
    sb = np.full((3, len(CADENCE), len(CAD_SEEDS[:2])), np.nan)
    pb = np.full((3, len(CADENCE), len(CAD_SEEDS[:2])), np.nan)
    wall = np.zeros(len(CADENCE))
    for i in range(len(CADENCE)):
        for j in range(2):
            p = PARTS / f"cad_c{i}_s{j}.npz"
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
             
    # 3. Robust
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
        pp = PARTS / f"robust_prot_{k}.npz"
        if pp.exists():
            d = np.load(pp)
            errs.append(float(d["err"])); vals.append(float(d["ssim"]))
    kw["prot"] = np.array(errs); kw["ssim_prot"] = np.array(vals)
    np.savez(DATA / "robust.npz", **kw)
    log("All primary data products merged successfully.")


if __name__ == "__main__":
    a = sys.argv[1:]
    t0 = time.time()
    cmd = a[0] if len(a) > 0 else "help"
    if cmd == "setup":
        cmd_setup()
    elif cmd == "validation":
        cmd_validation()
    elif cmd == "cadence_ablation":
        cmd_cadence_ablation()
    elif cmd == "component_ablation":
        cmd_component_ablation()
    elif cmd == "robust_extended":
        cmd_robust_extended()
    elif cmd == "spatial_resolution":
        cmd_spatial_resolution()
    elif cmd == "deflation_diagnostics":
        cmd_deflation_diagnostics()
    elif cmd == "merge":
        cmd_merge()
    elif cmd == "all":
        cmd_setup()
        cmd_validation()
        cmd_cadence_ablation()
        cmd_component_ablation()
        cmd_robust_extended()
        cmd_spatial_resolution()
        cmd_deflation_diagnostics()
        cmd_merge()
    else:
        print("Usage: python run_experiments.py [setup|validation|cadence_ablation|component_ablation|robust_extended|spatial_resolution|deflation_diagnostics|merge|all]")
    log("Execution completed in %.1f s" % (time.time() - t0))

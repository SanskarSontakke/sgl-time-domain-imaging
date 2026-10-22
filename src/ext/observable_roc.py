"""Observable-level retrieval metrics (referee Part VII item 9).

Reuses archived reconstructions -- no new simulations.  Computes:
  (a) land/ocean feature-detection ROC (AUC) per method per seed
  (b) continent area and contrast recovery with paired errors
  (c) albedo-histogram moments (mean, sd, skew, kurtosis) vs truth
  (d) d' completeness curves vs photon floor / cover fraction
  (e) headline: observed d' vs cloud-only physical null

Scientific claim: the land-ocean detection d' = 0.732 +/- 0.081 (SE) from
the profiled TDI reconstruction at f_c = 0.55 exceeds the cloud-only
physical null maximum of 0.130 (40 realisations, p <= 0.024), confirming
that the reconstruction contains genuine surface-feature information
beyond what cloud structure alone can produce.
"""

import json
import sys
import time
import os

import numpy as np
from scipy import stats as sp_stats

sys.path.insert(0, os.path.dirname(__file__))
import extcommon as X
import sglsim as S

log = X.log


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _roc_auc(scores, labels):
    """Trapezoidal AUC for a binary classifier sweeping a threshold on *scores*
    against ground-truth *labels* (bool).  TPR = fraction of True correctly
    above threshold; FPR = fraction of False incorrectly above threshold."""
    labels = np.asarray(labels, dtype=bool)
    scores = np.asarray(scores).ravel()
    thr = np.sort(np.unique(scores))[::-1]
    tpr_list, fpr_list = [0.0], [0.0]
    n_pos = labels.sum()
    n_neg = (~labels).sum()
    if n_pos == 0 or n_neg == 0:
        return 0.5
    for t in thr:
        pred = scores >= t
        tpr_list.append(float((pred & labels).sum()) / n_pos)
        fpr_list.append(float((pred & ~labels).sum()) / n_neg)
    tpr_arr = np.array(tpr_list)
    fpr_arr = np.array(fpr_list)
    order = np.argsort(fpr_arr)
    fpr_arr = fpr_arr[order]
    tpr_arr = tpr_arr[order]
    return float(np.trapezoid(tpr_arr, fpr_arr))


def _surface_map(p, mname, truth_c):
    """The debiased surface map stored in a ``clouds_*`` part archive.

    ``run_experiments._fits`` stores ``map_<method>`` AFTER applying
    ``S.debias_cloud``, so debiasing it again applies the affine transform twice.
    That error is invisible to exactly the statistics this module cares about
    most --- Pearson $r$, $d'$ and ROC AUC are all invariant under
    $s \\mapsto (s-c)/(1-f_c)$ --- and visible only in the mean-scale statistics
    (albedo moments, area and contrast recovery), which is where it showed up.
    The guard therefore checks the stored BIAS, not the stored correlation.
    """
    m = np.asarray(p[f"map_{mname}"]).ravel()
    key = f"{mname}_bias"
    if key in p.files:
        b = float(np.mean(m)) - float(np.mean(truth_c))
        if abs(b - float(p[key])) > 1e-9:
            raise RuntimeError(
                f"{mname}: stored map is not on the debiased scale (recomputed "
                f"bias {b:+.6f} vs archived {float(p[key]):+.6f}); the part-"
                f"archive layout changed and this module must be re-read")
    return m


def _histogram_moments(arr):
    a = np.asarray(arr, dtype=float).ravel()
    a = a[np.isfinite(a)]
    if a.size < 4:
        return dict(mean=float("nan"), std=float("nan"),
                    skew=float("nan"), kurtosis=float("nan"))
    m = a.mean()
    s = a.std(ddof=1)
    if s < 1e-30:
        return dict(mean=float(m), std=0.0, skew=0.0, kurtosis=0.0)
    skew = float(((a - m) ** 3).mean() / s ** 3)
    kurt = float(((a - m) ** 4).mean() / s ** 4 - 3.0)
    return dict(mean=float(m), std=float(s), skew=skew, kurtosis=kurt)


def _continent_area_contrast(map_est_2d, truth_c, lat_max_deg=60.0):
    """Continent area recovery (fraction of true land pixels classified as
    land) and contrast recovery (ratio of estimated to true land-ocean
    albedo difference)."""
    nlat, nlon = truth_c.shape
    lat = (np.arange(nlat) + 0.5) / nlat * 180.0 - 90.0
    sel = np.abs(lat) <= lat_max_deg
    me = map_est_2d[sel]
    mt = truth_c[sel]
    land = mt > 0.15
    # Use median of estimated map as threshold
    thr = float(np.median(me))
    pred_land = me >= thr
    area_recovery = float((pred_land & land).sum()) / max(land.sum(), 1)
    area_false_pos = float((pred_land & ~land).sum()) / max((~land).sum(), 1)
    # Contrast
    est_contrast = me[land].mean() - me[~land].mean() if land.any() and (~land).any() else 0.0
    true_contrast = mt[land].mean() - mt[~land].mean()
    contrast_recovery = float(est_contrast / true_contrast) if abs(true_contrast) > 1e-10 else float("nan")
    return dict(area_recovery=area_recovery, false_positive_rate=area_false_pos,
                est_contrast=float(est_contrast), true_contrast=float(true_contrast),
                contrast_recovery=contrast_recovery)


# ---------------------------------------------------------------------------
# main analysis
# ---------------------------------------------------------------------------

def main():
    t0 = time.time()
    fast = "--fast" in sys.argv[1:]
    seeds = X.EXT_SEEDS if fast else X.FULL_SEEDS

    log(f"observable_roc: fast={fast}, seeds={seeds}")

    # Load archived data
    clouds = np.load(X.DATA / "clouds.npz")
    truth_c = clouds["truth_c"]          # (36, 72)
    methods = list(clouds["methods"])     # ['profiled','deflate','white','b2','b1','b2coarse']
    fcs = clouds["fcs"]                   # [0, 0.25, 0.4, 0.55, 0.7]
    dprime_mat = clouds["dprime_mat"]     # (6, 5, 10)
    pearson_mat = clouds["pearson_mat"]
    ssim_mat = clouds["ssim_mat"]
    bias_mat = clouds["bias_mat"]
    contrast_mat = clouds["contrast_mat"]

    # Truth labels for ROC
    land_mask = truth_c > 0.15   # (36, 72) bool
    nlat, nlon = truth_c.shape
    lat = (np.arange(nlat) + 0.5) / nlat * 180.0 - 90.0
    sel_lat = np.abs(lat) <= 60.0

    # Load nulls
    nulls = np.load(X.DATA / "nulls_cloud_ensemble.npz")
    null_d = nulls["d"]           # (40,)
    null_maps = nulls["maps"]     # (40, 2592)

    # ------------------------------------------------------------------
    # (a) ROC AUC per method per seed at fc=0.55 (index 3)
    # ------------------------------------------------------------------
    fc_idx = 3  # fc=0.55
    roc_results = {}
    for mi, mname in enumerate(methods):
        aucs = []
        for si, seed in enumerate(seeds):
            part_name = f"clouds_f{fc_idx}_s{si}"
            part_path = X.DATA / "parts" / f"{part_name}.npz"
            if not part_path.exists():
                continue
            p = np.load(part_path)
            # the stored map is ALREADY debiased -- see _surface_map
            map_debiased = _surface_map(p, mname, truth_c)
            map_debiased_2d = map_debiased.reshape(nlat, nlon)
            # ROC on mid-latitude pixels
            scores = map_debiased_2d[sel_lat].ravel()
            labels = land_mask[sel_lat].ravel()
            auc = _roc_auc(scores, labels)
            aucs.append(auc)
        if aucs:
            roc_results[mname] = dict(
                auc_mean=float(np.mean(aucs)),
                auc_se=float(np.std(aucs, ddof=1) / np.sqrt(len(aucs)) if len(aucs) > 1 else 0.0),
                auc_per_seed=[float(a) for a in aucs],
                n_seeds=len(aucs),
            )
    log(f"ROC AUC computed for {len(roc_results)} methods")

    # ------------------------------------------------------------------
    # (b) Continent area and contrast recovery
    # ------------------------------------------------------------------
    area_contrast = {}
    for mi, mname in enumerate(methods):
        ac_list = []
        for si, seed in enumerate(seeds):
            part_path = X.DATA / "parts" / f"clouds_f{fc_idx}_s{si}.npz"
            if not part_path.exists():
                continue
            p = np.load(part_path)
            map_2d = _surface_map(p, mname, truth_c).reshape(nlat, nlon)
            ac = _continent_area_contrast(map_2d, truth_c)
            ac_list.append(ac)
        if ac_list:
            area_contrast[mname] = {
                k: dict(mean=float(np.mean([a[k] for a in ac_list])),
                        se=float(np.std([a[k] for a in ac_list], ddof=1) / np.sqrt(len(ac_list)))
                        if len(ac_list) > 1 else 0.0)
                for k in ac_list[0]
            }

    # ------------------------------------------------------------------
    # (c) Albedo histogram moments vs truth
    # ------------------------------------------------------------------
    truth_moments = _histogram_moments(truth_c[sel_lat])
    hist_moments = {}
    for mi, mname in enumerate(methods):
        mom_list = []
        for si, seed in enumerate(seeds):
            part_path = X.DATA / "parts" / f"clouds_f{fc_idx}_s{si}.npz"
            if not part_path.exists():
                continue
            p = np.load(part_path)
            map_2d = _surface_map(p, mname, truth_c).reshape(nlat, nlon)
            mom = _histogram_moments(map_2d[sel_lat])
            mom_list.append(mom)
        if mom_list:
            hist_moments[mname] = {
                k: dict(mean=float(np.mean([m[k] for m in mom_list])),
                        se=float(np.std([m[k] for m in mom_list], ddof=1) / np.sqrt(len(mom_list)))
                        if len(mom_list) > 1 else 0.0)
                for k in mom_list[0]
            }

    # ------------------------------------------------------------------
    # (d) d' completeness curves: d' vs cover fraction
    # ------------------------------------------------------------------
    dprime_curves = {}
    for mi, mname in enumerate(methods):
        dprime_curves[mname] = dict(
            fc=fcs.tolist(),
            dprime_mean=dprime_mat[mi].mean(axis=1).tolist(),
            dprime_se=(dprime_mat[mi].std(axis=1, ddof=1) / np.sqrt(dprime_mat[mi].shape[1])).tolist(),
        )

    # ------------------------------------------------------------------
    # (e) Headline: observed d' vs null
    # ------------------------------------------------------------------
    # Profiled d' at fc=0.55
    obs_dprime = dprime_mat[methods.index("profiled"), fc_idx, :len(seeds)]
    obs_dprime_mean = float(obs_dprime.mean())
    obs_dprime_se = float(obs_dprime.std(ddof=1) / np.sqrt(len(obs_dprime)))
    obs_dprime_sd = float(obs_dprime.std(ddof=1))

    # Physical null
    null_max = float(null_d.max())
    null_mean = float(null_d.mean())
    null_sd = float(null_d.std(ddof=1))
    null_p95 = float(np.percentile(null_d, 95))
    # p-value: fraction of null >= observed mean (one-sided rank test)
    n_null = len(null_d)
    n_exceed = int(np.sum(null_d >= obs_dprime_mean))
    p_physical = (1 + n_exceed) / (1 + n_null)

    # Label-permutation null from the archive's own maps
    # Use the profiled map from seed 11 (first seed)
    part_path = X.DATA / "parts" / f"clouds_f{fc_idx}_s0.npz"
    p0 = np.load(part_path)
    map_prof_0 = _surface_map(p0, "profiled", truth_c).reshape(nlat, nlon)
    perm_result = S.label_permutation_dprime(map_prof_0, land_mask, n_perm=2000, seed=0)
    perm_p = perm_result["p_rank"]

    # Also compute permutation null for all seeds
    perm_dprimes = []
    for si in range(len(seeds)):
        pp = X.DATA / "parts" / f"clouds_f{fc_idx}_s{si}.npz"
        if not pp.exists():
            continue
        pd = np.load(pp)
        m = _surface_map(pd, "profiled", truth_c).reshape(nlat, nlon)
        pr = S.label_permutation_dprime(m, land_mask, n_perm=2000, seed=si)
        perm_dprimes.append(pr["observed"])
    perm_dprimes = np.array(perm_dprimes)

    headline = dict(
        observed_dprime_mean=obs_dprime_mean,
        observed_dprime_se=obs_dprime_se,
        observed_dprime_sd=obs_dprime_sd,
        null_physical_max=null_max,
        null_physical_mean=null_mean,
        null_physical_sd=null_sd,
        null_physical_p95=null_p95,
        null_physical_n=n_null,
        null_physical_p_leq=round(p_physical, 5),
        label_permutation_p_median=float(perm_p),
        label_permutation_dprime_per_seed=perm_dprimes.tolist(),
    )

    log(f"Headline: d' = {obs_dprime_mean:.3f} +/- {obs_dprime_se:.3f}, "
        f"null max = {null_max:.3f}, p = {p_physical:.4f}")

    # ------------------------------------------------------------------
    # Metric availability assessment
    # ------------------------------------------------------------------
    metric_availability = {}
    for mname in methods:
        avail = {
            "dprime": True,  # from archived dprime_mat
            "roc_auc": mname in roc_results,
            "area_contrast_recovery": mname in area_contrast,
            "histogram_moments": mname in hist_moments,
            "pearson_r": True,  # from archived pearson_mat
            "ssim": True,  # from archived ssim_mat
        }
        # Which metrics can be estimated without truth?
        no_truth = {
            "dprime": False,  # needs truth labels
            "roc_auc": False,  # needs truth labels
            "area_contrast_recovery": False,  # needs truth
            "histogram_moments": False,  # needs truth moments for comparison
            "pearson_r": False,  # needs truth map
            "ssim": False,  # needs truth map
        }
        metric_availability[mname] = dict(available=avail, estimable_without_truth=no_truth)

    # ------------------------------------------------------------------
    # Validation against archives
    # ------------------------------------------------------------------
    validation = {}
    # Check d' matches referee report
    validation["dprime_profiled_fc055_mean"] = dict(
        computed=obs_dprime_mean,
        archived=float(dprime_mat[methods.index("profiled"), fc_idx, :].mean()),
        referee_reported=0.732,
        match_referee=abs(obs_dprime_mean - 0.732) < 0.001,
    )
    validation["null_physical_max"] = dict(
        computed=null_max,
        referee_reported=0.130,
        match=abs(null_max - 0.130) < 0.001,
    )
    # Check pearson r matches
    r_prof = pearson_mat[methods.index("profiled"), fc_idx, :len(seeds)]
    validation["pearson_r_profiled_fc055"] = dict(
        mean=float(r_prof.mean()),
        se=float(r_prof.std(ddof=1) / np.sqrt(len(r_prof))),
        referee_reported=0.3422,
        match=abs(r_prof.mean() - 0.3422) < 0.001,
    )

    # ------------------------------------------------------------------
    # Build output
    # ------------------------------------------------------------------
    wall = time.time() - t0

    # Save npz
    npz_data = dict(
        roc_auc_profiled=np.array([r["auc_per_seed"] for m, r in roc_results.items()
                                    if m == "profiled"] if "profiled" in roc_results else [[]]),
        null_d=null_d,
        obs_dprime_per_seed=obs_dprime,
        truth_labels=land_mask.astype(np.int8),
    )
    X.save_npz("observable_roc", **{k: v for k, v in npz_data.items() if v.size > 0})

    # Save json
    caveats = [
        "ROC AUC and area/contrast metrics require the truth map; they are not estimable in flight",
        "d' uses the same land/ocean threshold (truth_c > 0.15) as S.detection_dprime",
        f"Label-permutation null uses 2000 permutations per seed (floor 1/2001 = 5.0e-4)",
        f"Physical null ensemble has 40 realisations (p-value floor 1/41 = 0.0244)",
        "Histogram moments computed on mid-latitude (|lat| <= 60 deg) pixels only",
        "Area recovery and its false-positive rate classify the retrieved map at its own MEDIAN, an uncalibrated balanced split: they say how the retrieved ordering of pixels partitions the true classes, not whether a thresholded map would be usable. Contrast recovery uses the truth labels for both groups and is the load-bearing number of the two.",
        "Maps are read from results/parts/clouds_f*_s*.npz, where run_experiments stores them AFTER debiasing; _surface_map verifies that against the archived bias instead of re-applying the transform, which would leave r, d' and AUC untouched and corrupt only the albedo-scale statistics.",
    ]

    out = dict(
        headline=headline,
        roc_auc=roc_results,
        area_contrast_recovery=area_contrast,
        histogram_moments=dict(truth=truth_moments, reconstructed=hist_moments),
        dprime_completeness_curves=dprime_curves,
        metric_availability=metric_availability,
        validation=validation,
        caveats=caveats,
        provenance=X.provenance("observable_roc", extra=dict(
            seeds_used=seeds, fc_index=fc_idx, fast=fast, wall_time_s=round(wall, 1),
        )),
    )
    X.save_json("observable_roc", out)
    X.summary("observable_roc",
              dprime_mean=obs_dprime_mean,
              dprime_se=obs_dprime_se,
              null_max=null_max,
              p_physical=p_physical,
              roc_auc_profiled=roc_results.get("profiled", {}).get("auc_mean", None),
              wall_time_s=round(wall, 1))


if __name__ == "__main__":
    main()

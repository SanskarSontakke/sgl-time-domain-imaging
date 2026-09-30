"""Rebuild the web-demo machine-readable data file from the shipped archive.

public/data/project_data.json has no importers in the Next.js app (every screen
takes its numbers from components or from data/reconstructionMaps.ts), so it is
purely a downloadable "results blob".  It is regenerated here from
results/audit.json + results/clouds.npz -- the same files the response letter
cites -- so it cannot drift from the manuscript.  (audit.json stores a single
pooled {mean,sd,se} per method for the cloud sweep, so the per-fc curves are
recomputed from the archived per-seed matrices in clouds.npz; SSIM exists only
there.)

Run from the repository root:  python3 src/make_app_data.py
"""

import json

import numpy as np

from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
AUDIT = json.loads((ROOT / "results" / "audit.json").read_text())
TARGETS = json.loads((ROOT / "results" / "targets.json").read_text())
CLOUDS = np.load(ROOT / "results" / "clouds.npz")

FCS = [0.0, 0.25, 0.40, 0.55, 0.70]
FID = 3  # index of the fiducial cloudy case, fc = 0.55
METHODS = [str(m) for m in CLOUDS["methods"]]


def r4(x):
    return round(float(x), 4)


def curve(mat, axis=1):
    """Per-fc mean of an (n_method, n_fc, n_seed) matrix."""
    return [r4(v) for v in mat.mean(axis=axis)]


def per_fc_se(mat):
    """Per-fc standard error across seeds (n = 10)."""
    n = mat.shape[-1]
    return [round(float(v), 5) for v in mat.std(axis=-1, ddof=1) / np.sqrt(n)]


def pm(block, digits=4):
    return {"mean": round(block["mean"], digits),
            "se": round(block["se"], digits - 1), "n": block["n"]}


def finite(o):
    """JSON has no encoding for inf/nan; map them to null recursively."""
    if isinstance(o, dict):
        return {k: finite(v) for k, v in o.items()}
    if isinstance(o, list):
        return [finite(v) for v in o]
    if isinstance(o, float) and not np.isfinite(o):
        return None
    return o


def stats(mat, m):
    """(5,) mean and se curves for one archived method."""
    i = METHODS.index(m)
    return curve(mat[i]), per_fc_se(mat[i])


p_r, p_se = stats(CLOUDS["pearson_mat"], "profiled")
w_r, w_se = stats(CLOUDS["pearson_mat"], "white")
b2_r, b2_se = stats(CLOUDS["pearson_mat"], "b2")
b1_r, _ = stats(CLOUDS["pearson_mat"], "b1")
p_s, w_s, b2_s, b1_s = (stats(CLOUDS["ssim_mat"], m)[0]
                        for m in ("profiled", "white", "b2", "b1"))

cad = AUDIT["cadence_photons"]
cadw = AUDIT["cadence_wallclock"]
ctl = AUDIT["cadence_controls"]["photons"]
comp = AUDIT["components"]
res = AUDIT["resolution"]
nul = AUDIT["nulls"]
prec = json.loads((ROOT / "results" / "precision.json").read_text())

CONFIGS = ["A_white_nodefl", "B_ou_nodefl", "C_v2_deflate",
           "D_profiled_anchor", "E_profiled_free", "F_full_tdi"]

payload = {
    "_provenance": {
        "generated_from": "results/audit.json + results/clouds.npz "
                          "(src/run_experiments.py merge)",
        "conventions": AUDIT["conventions"],
        "note": "Every value here is a v3 archive number. The manuscript tables "
                "in paper/main.tex are the authoritative presentation; this file "
                "exists so the demo site can ship a machine-readable blob.",
    },
    "targets": TARGETS["targets"],
    "headline": {
        "cloud_free_rotating": {"r": p_r[0], "ssim": p_s[0], "se_r": p_se[0]},
        "fiducial_cloudy": {"r": p_r[FID], "ssim": p_s[FID], "se_r": p_se[FID],
                            "fc": FCS[FID]},
        "high_cloud": {"r": p_r[4], "ssim": p_s[4], "se_r": p_se[4],
                       "fc": FCS[4]},
    },
    "clouds_summary": {
        "fcs": FCS,
        "n_seeds_per_fc": 10,
        "methods": ["profiled", "white", "b2", "b1"],
        "pearson_mean": {"profiled": p_r, "white": w_r, "b2": b2_r, "b1": b1_r},
        "pearson_se": {"profiled": p_se, "white": w_se, "b2": b2_se},
        "ssim_mean": {"profiled": p_s, "white": w_s, "b2": b2_s, "b1": b1_s},
    },
    "deflation_diag": finite(json.loads(
        (ROOT / "results" / "deflation_diag.json").read_text())),
    "cadence_photons": {
        "mp": cad["mp"], "ts": cad["ts"], "wall_days": cad["wall_days"],
        "duty": cad["duty"], "fits_90d": cad["fits_90d"],
        "r_profiled": cad["r_profiled"], "r_white": cad["r_white"],
        "r_b2": cad["r_b2"], "r_b1": cad["r_b1"],
        "controls": {"r_cloud_free": ctl["r_cf"],
                     "r_per_pass_independent": ctl["r_iid"]},
        "n_seeds": cad["n_seeds"],
        "note": "arm A (fixed photons per raster position: M_p * t_s = 28,800 "
                "s). SSIM is not archived for this arm; see the r columns.",
    },
    "cadence_wallclock": {
        "mp": cadw["mp"], "ts": cadw["ts"], "wall_days": cadw["wall_days"],
        "duty": cadw["duty"], "r_profiled": cadw["r_profiled"],
        "n_seeds": cadw["n_seeds"],
    },
    "component_ablation": {
        "configurations": CONFIGS,
        "r": {k: pm(comp[k]["r"]) for k in CONFIGS},
        "ssim": {k: pm(comp[k]["ssim"]) for k in CONFIGS},
        "paired": {k[len("paired_"):]: comp[k] for k in comp
                   if k.startswith("paired_")},
        "norm_ratio_C_vs_D": comp["norm_ratio_C_vs_D"],
        "n_seeds": 10,
    },
    "spatial_resolution": {
        "l_deg": res["l"],
        "r_l_cf": [r4(v) for v in res["r_cf_mean"]],
        "r_l_cl": [r4(v) for v in res["r_cl_mean"]],
        "l_eff_cf": res["l_eff_cf"], "l_eff_cl": res["l_eff_cl"],
        "quadrature_err_by_l": [r4(v) for v in res["quadrature_err_mean"]],
        "note": "36x72 grid: degrees above l ~ 18-20 are not representable; "
                "the cloud-free curve stays at r >= 0.986 across the whole "
                "range, i.e. no band is lost -- this is a measurement ceiling, "
                "not a resolution claim. The cloudy curve is reported as a "
                "band: the running mean crosses 0.5 at l ~ 9 (~2200 km).",
    },
    "nulls": {
        "dprime_observed_by_seed": [r4(v) for v in nul["d_observed"]],
        "dprime_observed_mean": r4(float(np.mean(nul["d_observed"]))),
        "cloud_null_p_min": nul["cloud_null_p_min"],
        "perm_null_p_min": nul["perm_null_p_min"],
        "cloud_null_ensemble": nul["cloud_null_ensemble"],
        "note": nul["note"],
    },
    "static_reference": AUDIT["static_reference"],
    "robust_geometry": AUDIT["robust_geom"],
    "robust_climatology": AUDIT["robust_clim"],
    "robust_debias": AUDIT["robust_debias"],
    "morphology": AUDIT["morphology"],
    "latband": AUDIT["latband"],
    "lambda_sweep": AUDIT["lambda_sweep"],
    "sigma_sensitivity": AUDIT["sigma_sensitivity"],
    "validation": {
        # precision.json carries an unregularized condition number logged as
        # Infinity; JSON has no finite encoding for it, so it ships as null.
        **finite({k: v for k, v in prec.items()}),
        "note": "results/precision.json; cond_A_unregularized = +Infinity is "
                "reported as null (the unregularized normal matrix is rank "
                "2016 of 2592).",
    },
}

out = ROOT / "public" / "data" / "project_data.json"
out.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n")
print("wrote", out, f"{out.stat().st_size / 1024:.0f} KB")

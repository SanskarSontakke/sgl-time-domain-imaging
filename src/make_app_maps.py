"""Regenerate the web-demo reconstruction payload from the shipped v3 archive.

Consumes results/clouds.npz (merged by `run_experiments.py merge`) and writes
one identical JSON payload to two places:

    data/reconstructionMaps.ts    (imported by ImageReconstructionSandbox.tsx)
    public/data/reconstruction_maps.json (scratch animation scripts)

Conventions, chosen to match src/make_figures.py:
  * maps are rendered on the paper's albedo window [0, 0.7] with matplotlib's
    cividis colormap at 256 levels; the "natural" variant is a piecewise-linear
    ocean/vegetation/ice palette keyed to the same normalized value;
  * arrays are stored north-up (row 0 = +90 deg latitude), i.e. vertically
    flipped relative to the origin="lower" matplotlib figures;
  * metric rows are ordered [profiled TDI, white-noise GLS, phase-binned
    coadd (B2)] and hold the per-fc means over the 10 paired seeds -- exactly
    the row order the sandbox component indexes;
  * clouds[fc_0] is all zeros (the cloud-free campaign has no OU realization);
    fc >= 1 use the snap-0 opacity of the unprefixed v2-era part files
    (results/parts/clouds_f<i>_s0.npz), downsampled 2x2 from the 72x144
    climate grid. The v3 suite does not archive the cloud field itself, so
    this overlay is illustrative (its realized cover matches the v3 sweep to
    ~0.02); the metric rows above are the authoritative v3 numbers.

Run from src/:  python3 make_app_maps.py
"""

import json
from pathlib import Path

import numpy as np
from matplotlib import colormaps

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = ROOT / "results"
NLAT, NLON = 36, 72
VMIN, VMAX = 0.0, 0.7
NLEVEL = 256
METHODS = ("profiled", "white", "b2")          # rows, in payload order
KEYS = ("gls", "white", "b2")                  # payload key prefixes
FCS = (0.0, 0.25, 0.40, 0.55, 0.70)

# Normalized value -> natural RGB, extracted from the v1-era demo palette and
# re-fitted on the same [0, 0.7] window (deep ocean < 0.12, vegetated land,
# then ice/snow above ~0.65).
NAT_K = np.array([0, 16, 30, 34, 60, 90, 120, 150, 166, 172, 182, 187, 200,
                  221, 255])
NAT_RGB = np.array([[15, 45, 110], [21, 60, 127], [31, 98, 83], [36, 114, 37],
                    [52, 125, 42], [70, 137, 47], [94, 154, 55],
                    [118, 169, 87], [129, 176, 103], [140, 183, 119],
                    [150, 190, 133], [160, 197, 149], [190, 213, 170],
                    [226, 236, 241], [250, 253, 255]])


def render(field, cmap_nat=False):
    u = np.clip((field - VMIN) / (VMAX - VMIN), 0.0, 1.0)
    k = np.rint(u * (NLEVEL - 1)).astype(int)
    if cmap_nat:
        rgb = np.stack([np.interp(k, NAT_K, NAT_RGB[:, c])
                        for c in range(3)], axis=-1)
    else:
        lut = colormaps["cividis"](np.linspace(0, 1, NLEVEL))[:, :3] * 255.0
        rgb = lut[k]
    return np.rint(rgb).astype(int).tolist()


def north_up(a):
    return np.asarray(a, dtype=float).reshape(NLAT, NLON)[::-1]


def main():
    cl = np.load(DATA / "clouds.npz")
    archive = [str(m) for m in cl["methods"]]
    rows = [archive.index(m) for m in METHODS]
    pearson, ssim = [], []
    for mi in rows:
        pearson.append([round(float(np.nanmean(cl["pearson_mat"][mi, i])), 4)
                        for i in range(len(FCS))])
        ssim.append([round(float(np.nanmean(cl["ssim_mat"][mi, i])), 4)
                     for i in range(len(FCS))])

    payload = {
        "fcs": list(FCS),
        "cividis_truth": render(north_up(cl["truth_c"])),
        "natural_truth": render(north_up(cl["truth_c"]), cmap_nat=True),
        "pearson": pearson,
        "ssim": ssim,
        "clouds": {},
    }
    for pref in KEYS:
        payload[f"{pref}_cividis"] = {}
        payload[f"{pref}_natural"] = {}
    for pref, meth in zip(KEYS, METHODS):
        for i in range(len(FCS)):
            m = north_up(cl[f"map_{meth}_fc{i}"])
            payload[f"{pref}_cividis"][f"fc_{i}"] = render(m)
            payload[f"{pref}_natural"][f"fc_{i}"] = render(m, cmap_nat=True)
    for i in range(len(FCS)):
        if i == 0:
            op = np.zeros((NLAT, NLON))
        else:
            d = np.load(DATA / "parts" / f"clouds_f{i}_s0.npz")
            op = np.asarray(d["snap0_opac"], float).reshape(NLAT, 2, NLON, 2)
            op = op.mean(axis=(1, 3))
        payload["clouds"][f"fc_{i}"] = np.round(north_up(op), 3).tolist()

    blob = json.dumps(payload, separators=(",", ":"))
    (ROOT / "data" / "reconstructionMaps.ts").write_text(
        "export const RECONSTRUCTION_DATA = " + blob + ";\n")
    out = ROOT / "public" / "data" / "reconstruction_maps.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(blob)
    print(f"wrote {len(blob) / 1e6:.2f} MB payload "
          f"({len(payload)} top-level keys)")


if __name__ == "__main__":
    main()

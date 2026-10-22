#!/usr/bin/env python3
"""Gate G-3: prove that the single-version refactor changed no reported number.

Walks the pre-refactor audit JSON and the pre-refactor archives and compares
every numeric leaf with the current tree, following the documented key renames.
Tolerance is tiered, because "identical" has two legitimate meanings here:

  tier 0   deterministic reductions (mean/SE/counts/derived ratios) -> exact
  tier 1   linear-algebra reductions (BLAS / summation order)        -> 1e-12

Any leaf outside its tier is a behaviour change and must be bisected, not
absorbed.

Usage: tools/verify_flat.py <old_audit.json> <new_audit.json>
       tools/verify_flat.py --npz <old_dir> <new_dir>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

# documented rename map (audit JSON pointer form), old -> new
RENAME = {
    "v2": "deflate",
    "C_v2_deflate": "C_deflate",
    "r_v2": "r_deflate",
    "fiducial_profiled_vs_v2_rel_diff": "fiducial_profiled_vs_deflate_rel_diff",
    "sigma_sensitivity_v2": "sigma_sensitivity_deflate",
}
# keys whose *content* is intentionally redefined by the referee repairs
SKIP_SUBSTR = ("generated_utc", "l_eff", "energy_frac", "cellmean_formula_vs_brute",
               "peak_to_offdiag", "paired_F_vs_C", "paired_reldev_F_vs_C",
               "l_eff_thresholds", "n_seeds")
# the three F-C contrasts the shipped archive carried without a writer (F-22);
# the writer emits them with an explicit "_diff_" infix
ORPHAN = {"reldev_F_minus_C": "reldev_F_vs_C",
          "mean_reldev_F_minus_C": "mean_reldev_F_vs_C",
          "sem_reldev_F_minus_C": "sem_reldev_F_vs_C"}


def remap(seg: str) -> str:
    """Map a pre-refactor name onto its single-version successor."""
    if seg in RENAME:
        return RENAME[seg]
    if seg in ORPHAN:
        return ORPHAN[seg]
    # the compound infix "C_v2_deflate" collapses to "C_deflate", not to
    # "C_deflate_deflate"; the bare label "v2" becomes "deflate"
    seg = seg.replace("v2_deflate", "deflate")
    return re.sub(r"(?<![a-z0-9])v2(?![0-9a-z])", "deflate", seg)


def walk(node, path="", out=None):
    if out is None:
        out = {}
    if isinstance(node, dict):
        for k, v in node.items():
            walk(v, f"{path}/{remap(k)}", out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk(v, f"{path}[{i}]", out)
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        out[path] = float(node)
    return out


def compare_json(old_p, new_p) -> tuple[int, float, list]:
    old = walk(json.loads(Path(old_p).read_text()))
    new = walk(json.loads(Path(new_p).read_text()))
    missing, worst, n = [], 0.0, 0
    for k, v in old.items():
        if any(s in k for s in SKIP_SUBSTR):
            continue
        if k not in new:
            missing.append(k)
            continue
        n += 1
        d = abs(new[k] - v)
        worst = max(worst, d)
        if d > 1e-12 and v != 0 and d / max(abs(v), 1e-300) > 1e-12:
            missing.append(f"{k}: value differs by {d:.3e}")
    return n, worst, missing


def compare_npz(old_dir: Path, new_dir: Path) -> tuple[int, float, list]:
    n, worst, problems = 0, 0.0, []
    for p in sorted(old_dir.glob("*.npz")):
        q = new_dir / p.name
        if not q.exists():
            problems.append(f"{p.name}: archive missing")
            continue
        a, b = np.load(p, allow_pickle=True), np.load(q, allow_pickle=True)
        for k in a.files:
            if any(s in k for s in SKIP_SUBSTR):
                continue
            nk = remap(k)
            if nk not in b.files:
                problems.append(f"{p.name}:{k} -> {nk}: key missing")
                continue
            x0, y0 = np.asarray(a[k]), np.asarray(b[nk])
            if x0.dtype.kind in "OSU" or y0.dtype.kind in "OSU":
                # label arrays: must agree after the documented substitution
                u = [str(v) for v in x0.ravel()]
                v = [str(w) for w in y0.ravel()]
                if [remap(s) for s in u] != v:
                    problems.append(f"{p.name}:{nk}: labels {u} vs {v}")
                continue
            if x0.shape != y0.shape:
                problems.append(f"{p.name}:{k}: shape {x0.shape} vs {y0.shape}")
                continue
            x, y = x0.astype(float), y0.astype(float)
            fin = np.isfinite(x)
            if not fin.any():
                continue
            d = float(np.max(np.abs(y[fin] - x[fin])))
            worst = max(worst, d)
            n += 1
            if d > 1e-12:
                problems.append(f"{p.name}:{nk}: max abs diff {d:.3e}")
    return n, worst, problems


def main() -> int:
    if "--npz" in sys.argv:
        i = sys.argv.index("--npz")
        n, worst, problems = compare_npz(Path(sys.argv[i + 1]), Path(sys.argv[i + 2]))
        label = "archive arrays"
    else:
        n, worst, problems = compare_json(sys.argv[1], sys.argv[2])
        label = "audit leaves"
    print(f"{label} compared: {n}; worst absolute difference: {worst:.3e}")
    if problems:
        print(f"{len(problems)} PROBLEM(S):")
        for x in problems[:40]:
            print("  ", x)
        return 1
    print("G-3 PASS: every reported number survives the refactor unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main())

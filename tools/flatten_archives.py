#!/usr/bin/env python3
"""De-version the checkpoint parts: strip the suite prefix, rename the method
keys, and rewrite the stored label strings -- while proving that no numeric
array changes by one bit.

Why a transform and not a rename: the skip-if-done logic of the pipeline is
name-based, and some part files store the solver label INSIDE them, so a file
rename alone leaves version tokens in the data (definition of done D4).  This
script therefore rewrites name + keys + labels in one pass and verifies, per
array, that the bytes of every numeric payload are identical before and after.

The shipped top-level archives are NOT touched here: they are regenerated from
the transformed parts by `python run_experiments.py merge`, so the writers stay
the single source of truth.

Usage:  tools/flatten_archives.py [--dry-run] [--parts DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

import numpy as np

PREFIX = re.compile(r"^v[123]_")
TOKEN = re.compile(r"(?<![a-z0-9])v2(?![0-9a-z])")
KEY_MAP = {
    "v2_pearson": "deflate_pearson",
    "v2_ssim": "deflate_ssim",
    "v2_nrmse": "deflate_nrmse",
    "v2_bias": "deflate_bias",
    "v2_contrast": "deflate_contrast",
    "map_v2": "map_deflate",
    "C_v2_deflate_pearson": "C_deflate_pearson",
    "C_v2_deflate_ssim": "C_deflate_ssim",
    "C_v2_deflate_nrmse": "C_deflate_nrmse",
    "C_v2_deflate_bias": "C_deflate_bias",
    "C_v2_deflate_contrast": "C_deflate_contrast",
    "reldev_C_v2_deflate": "reldev_C_deflate",
    "norm_C_v2_deflate": "norm_C_deflate",
}
# Part FILE names embed the estimator label, so the stem needs its own map
# (the word-boundary TOKEN regex deliberately does not match inside "sigclv2").
NAME_MAP = {"sigclv2": "sigcldeflate"}


def flat_name(name: str) -> str:
    stem = PREFIX.sub("", name)
    for old, new in NAME_MAP.items():
        stem = stem.replace(old, new)
    return stem


def sha(a) -> str:
    return hashlib.sha256(np.ascontiguousarray(np.asarray(a)).tobytes()).hexdigest()


def flatten_one(path: Path, out_dir: Path, dry: bool) -> tuple[int, int]:
    """Return (keys renamed, label values rewritten) for one part file."""
    d = np.load(path, allow_pickle=True)
    payload = {}
    renamed = rewritten = 0
    for k, v in ((kk, d[kk]) for kk in d.files):
        nk = KEY_MAP.get(k, TOKEN.sub("deflate", k))
        renamed += (nk != k)
        if v.dtype.kind in "OSU":
            vals = [TOKEN.sub("deflate", str(x)) for x in np.asarray(v).ravel()]
            rewritten += sum(1 for kk, x in zip(np.asarray(v).ravel(), vals)
                             if str(kk) != x)
            # NOTE: np.array(..., dtype="<U2") would TRUNCATE "deflate" to "de".
            # The width must be recomputed from the replacement strings, not
            # inherited from the label that is being replaced.
            if v.dtype.kind == "O":
                payload[nk] = np.array(vals, dtype=object).reshape(np.shape(v))
            else:
                width = max((len(s) for s in vals), default=1)
                payload[nk] = (np.array(vals, dtype=f"U{width}").reshape(np.shape(v))
                               if any(str(a) != b for a, b in
                                      zip(np.asarray(v).ravel(), vals)) else v)
        else:
            payload[nk] = v
    if not dry:
        dest = out_dir / flat_name(path.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".tmp.npz")
        np.savez(tmp, **payload)
        tmp.rename(dest)
        # verification: numeric payloads must be bit-identical
        back = np.load(dest, allow_pickle=True)
        for k, v in payload.items():
            if np.asarray(v).dtype.kind in "OSU":
                continue
            if sha(back[k]) != sha(v):
                raise SystemExit(f"ABORT: {dest.name}:{k} changed during transform")
    return renamed, rewritten


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="results/parts")
    ap.add_argument("--from-dir", default=None,
                    help="read the pre-transform parts from here (still writes "
                         "into --parts); used to re-run a subset after a fix")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    parts = Path(args.parts)
    src = Path(args.from_dir) if args.from_dir else parts
    out = Path("/tmp/parts_flat") if args.dry_run else parts
    tot_k = tot_l = n = 0
    for p in sorted(src.glob("*.npz")):
        d = np.load(p, allow_pickle=True)
        has_key = any(kk in KEY_MAP or TOKEN.search(kk) for kk in d.files)
        has_val = any(TOKEN.search(str(x)) for kk in d.files
                      if np.asarray(d[kk]).dtype.kind in "OSU"
                      for x in np.asarray(d[kk]).ravel())
        if not (flat_name(p.name) != p.name or has_key or has_val):
            continue
        r, w = flatten_one(p, out, args.dry_run)
        tot_k += r; tot_l += w; n += 1
        if r or w:
            print(f"{p.name}: {r} key(s), {w} label value(s)")
    print(f"{'DRY-RUN ' if args.dry_run else ''}{n} part files processed, "
          f"{tot_k} keys renamed, {tot_l} label values rewritten")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
r"""Build step for the numbers the manuscript derives but the pipeline does not store.

``results/`` is the pipeline's evidence: per-seed reconstructions, stage
summaries, headline statistics.  A paper, however, also prints quantities that
are *one remove* from that evidence -- a 95 % bootstrap interval around an
archived mean, a paired $t$ between two archived arms, a band mean over four
seeds and eight harmonics, a $\chi^2$ spread, the slope of a five-point
regression.  None of them is a leaf of a shipped archive, so the numeric
provenance ledger (``tools/claims.py``) had nothing to point at, and a referee
asking "where does $-76.6$ come from?" got an answer buried in prose.

This tool is the answer, in machine-readable form.  It is the research
analogue of a build step: it reads the shipped archives, calls the *shipped*
statistical helper (``src/expcommon.py::paired_stats``, 20,000 percentile
resamples of the paired differences under generator seed 42 -- the exact
convention the manuscript cites in Appendix~\ref{app:seeds}), and writes
``tools/derived_stats.json``.  ``tools/claims.py`` indexes that file as another
archive, so every derived number in the paper becomes traceable to a key, and
``--check`` fails when the committed artifact no longer matches a fresh
derivation.

Modes
-----
``(default)`` / ``--write``  regenerate ``tools/derived_stats.json``.
``--check``                  re-derive into memory and diff against the
                             committed file; non-zero on drift.  This is what
                             CI runs, so the artifact cannot be left behind by
                             a results change.
``--list``                   print the derived keys and their values.

Nothing here re-simulates: every input is a file already under ``results/``,
and every formula is a mean, a standard error, a paired difference, a
percentile bootstrap or a least-squares slope.  That is deliberate.  A derived
statistic is only worth a ledger entry if a reader can reproduce it from the
evidence the paper ships.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
PARTS = RESULTS / "parts"
OUT = ROOT / "tools" / "derived_stats.json"

sys.path.insert(0, str(ROOT / "src"))
import expcommon as E  # noqa: E402  (path set above; the shipped helper)

NBOOT = 20_000
BOOT_SEED = 42


# --------------------------------------------------------------------------- #
# readers
# --------------------------------------------------------------------------- #
def scalar_parts(family: str, key: str, n: int | None = None) -> np.ndarray:
    """One scalar field, collected over the ``<family>_s<i>.npz`` series."""
    if n is None:
        n = len(sorted(PARTS.glob(f"{family}_s*.npz")))
    out = []
    for i in range(n):
        p = PARTS / f"{family}_s{i}.npz"
        if not p.exists():
            raise FileNotFoundError(f"missing checkpoint {p}")
        out.append(float(np.load(p)[key]))
    return np.asarray(out, float)


def array_parts(family: str, key: str, n: int | None = None) -> np.ndarray:
    """A per-seed array field stacked along a new leading seed axis."""
    if n is None:
        n = len(sorted(PARTS.glob(f"{family}_s*.npz")))
    out = [np.asarray(np.load(PARTS / f"{family}_s{i}.npz")[key], float)
           for i in range(n)]
    return np.stack(out)


def archive(name: str, key: str) -> np.ndarray:
    p = RESULTS / name
    if not p.exists():
        raise FileNotFoundError(f"missing shipped archive {p}")
    return np.asarray(np.load(p, allow_pickle=True)[key], float)


# --------------------------------------------------------------------------- #
# the statistics the paper prints
# --------------------------------------------------------------------------- #
def one_sample(v: np.ndarray) -> dict:
    """Mean, sd, se and percentile bootstrap CI of a per-seed vector.

    ``paired_stats(v, 0)`` is used rather than a hand-rolled bootstrap so that
    the interval in the paper is exactly the interval the shipped helper
    produces -- same generator, same resample count, same percentiles.
    """
    st = E.paired_stats(v, np.zeros_like(v), nboot=NBOOT, seed=BOOT_SEED)
    return {"n": int(v.size), "per_seed": [float(x) for x in v],
            "mean": st["mean"], "sd": st["sd"], "se": st["se"],
            "ci_lo": st["ci_lo"], "ci_hi": st["ci_hi"]}


def paired(x: np.ndarray, y: np.ndarray) -> dict:
    """Paired difference x - y with the shipped bootstrap interval and t.

    ``n_favour`` counts the seeds whose own difference carries the sign of the
    ensemble difference.  The manuscript quotes that count as "10/10 seeds" or
    "0/10 seeds in favour" in a dozen places; until it was derived here the
    number was a claim about the per-seed table that no machine checked.
    """
    st = E.paired_stats(x, y, nboot=NBOOT, seed=BOOT_SEED)
    st["t"] = st["mean"] / st["se"] if st["se"] else float("nan")
    d = np.asarray(x, float) - np.asarray(y, float)
    st["per_seed"] = [float(v) for v in d]
    st["n_favour"] = int(np.sum(np.sign(d) == np.sign(st["mean"])))
    return st


def ols_slope(x: np.ndarray, y: np.ndarray) -> float:
    """Least-squares slope, the only regression the manuscript quotes."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    return float(((x - x.mean()) * (y - y.mean())).sum()
                 / ((x - x.mean()) ** 2).sum())


# Rows of Table ``tab:app_seeds``: printed label -> (source, key).
SEEDTABLE = {
    "rotating_cloud_free": ("parts", "clouds_f0", "profiled_pearson"),
    "tdi_fiducial": ("parts", "comp", "F_full_tdi_pearson"),
    "white_gls": ("parts", "comp", "A_white_nodefl_pearson"),
    "exact_profile_white": ("parts", "comp", "D_profiled_anchor_pearson"),
    "approx_deflate_ou": ("parts", "comp", "C_deflate_pearson"),
    "static_reference": ("npz", "static_reference.npz", "stat_r"),
    "surface_coupled": ("parts", "robclim_surf", "pearson"),
}
CONTRASTS = {
    "D_minus_A": ("exact_profile_white", "white_gls"),
    "F_minus_D": ("tdi_fiducial", "exact_profile_white"),
    "F_minus_C": ("tdi_fiducial", "approx_deflate_ou"),
}

# Epsilon indices printed in Table ``tab:sys`` (the 3e-8 rung is not quoted).
SYS_EPS = (0, 1, 3, 4, 5, 6, 7)
SYS_ARMS = ("drift_r", "streamer_r", "both_r")

# Harmonic bands of the lambda-resolution control: label -> [lo, hi) degree.
BANDS = {"l1_4": (0, 4), "l5_8": (4, 8), "l9_12": (8, 12),
         "l13_16": (12, 16), "l17_20": (16, 20), "l13p": (12, 20)}
HARMONIC = {"cloudfree": "lamres_f0", "cloudy": "lamres_f3"}


def derive() -> dict:
    stats: dict = {}

    # ---- 1. per-seed ensemble table (Appendix ``app:seeds``) --------------
    rows = {}
    for label, (kind, src, key) in SEEDTABLE.items():
        v = (scalar_parts(src, key) if kind == "parts"
             else archive(src, key))
        rows[label] = v
        stats.setdefault("seedtable", {})[label] = one_sample(v)
    for label, (a, b) in CONTRASTS.items():
        stats.setdefault("contrasts", {})[label] = paired(rows[a], rows[b])

    # Whitening the cloud-free fiducial: the paper quotes the profiled
    # estimator's loss against whitening and its paired t, both negative.
    cloudfree = scalar_parts("clouds_f0", "profiled_pearson")
    stats.setdefault("contrasts", {})["profiled_minus_white_fc0"] = \
        paired(cloudfree, scalar_parts("clouds_f0", "white_pearson"))
    # The cloud-limited ceiling: cloudy TDI against the rotating cloud-free
    # reference on the same seeds (t quoted beside Delta r = -0.6364).
    stats.setdefault("contrasts", {})["tdi_minus_rotating_cloudfree"] = \
        paired(scalar_parts("comp", "F_full_tdi_pearson"), cloudfree)
    # ... and the same ceiling measured against the white-noise rotating arm
    # (the paper quotes both baselines, -0.6364 and -0.6379, in one sentence).
    stats.setdefault("contrasts", {})["tdi_minus_rotating_white"] = \
        paired(scalar_parts("comp", "F_full_tdi_pearson"),
               scalar_parts("clouds_f0", "white_pearson"))
    # Surface--cloud phase coupling: the abstract and the results section both
    # quote its paired loss, its t and its p against the fiducial cloudy arm,
    # so the pairing has to exist as a derived object rather than in prose.
    stats.setdefault("contrasts", {})["surface_minus_tdi"] = \
        paired(rows["surface_coupled"], rows["tdi_fiducial"])

    # ---- 2. injected-systematics table (``tab:sys``) ----------------------
    base = scalar_parts("sys", "base_r")
    sys_stats = {"base": one_sample(base), "eps_index": list(SYS_EPS), "arms": {}}
    for arm in SYS_ARMS:
        m = array_parts("sys", arm)          # (seed, eps)
        cells = {}
        for k in SYS_EPS:
            st = paired(m[:, k], base)
            cells[str(k)] = {"r": one_sample(m[:, k]), "delta_r": st["mean"],
                             "se": st["se"], "t": st["t"],
                             "p_t": st["p_t"], "p_sign": st["p_sign"],
                             "n_favour": int(np.sum(
                                 (m[:, k] - base) * np.sign(st["mean"]) > 0))}
        sys_stats["arms"][arm] = cells
    # The sub-additivity statement: joint loss against the sum of the parts.
    joint = {k: sys_stats["arms"]["both_r"][str(k)]["delta_r"] for k in SYS_EPS}
    summed = {k: (sys_stats["arms"]["drift_r"][str(k)]["delta_r"]
                  + sys_stats["arms"]["streamer_r"][str(k)]["delta_r"])
              for k in SYS_EPS}
    sys_stats["sum_of_parts"] = {
        str(k): {"drift_plus_streamer": summed[k], "joint": joint[k],
                 "joint_over_sum_pct": (100.0 * joint[k] / summed[k]
                                        if summed[k] else float("nan"))}
        for k in SYS_EPS}
    stats["systematics"] = sys_stats

    # ---- 3. harmonic-resolution control (lambda sweep, 4 seeds) ----------
    for case, family in HARMONIC.items():
        r_ell = array_parts(family, "r_ell")        # (seed, lam, ell)
        out = {"n_seeds": int(r_ell.shape[0]), "bands": {}}
        for band, (lo, hi) in BANDS.items():
            per_seed = r_ell[:, :, lo:hi].mean(axis=2)   # (seed, lam)
            first = per_seed[:, 0].mean()
            last = per_seed[:, -1].mean()
            ent = {"lam_low": float(first), "lam_high": float(last),
                   "shift": float(last - first),
                   "by_lambda": [float(x) for x in per_seed.mean(axis=0)]}
            if r_ell.shape[0] > 2:
                st = paired(per_seed[:, -1], per_seed[:, 0])
                ent["paired"] = {k: st[k] for k in
                                 ("mean", "se", "ci_lo", "ci_hi", "p_t")}
                ent["paired"]["t"] = st["mean"] / st["se"] if st["se"] else None
            out["bands"][band] = ent
        for key in ("dprime", "contrast", "pearson", "ssim"):
            arr = array_parts(family, key)
            out[key] = {"lam_low_mean": float(arr[:, 0].mean()),
                        "lam_low_sd": float(arr[:, 0].std(ddof=1)),
                        "lam_high_mean": float(arr[:, -1].mean()),
                        "lam_high_sd": float(arr[:, -1].std(ddof=1)),
                        "by_lambda_mean": [float(x) for x in arr.mean(axis=0)]}
        stats.setdefault("harmonic", {})[case] = out

    # ---- 4. truth-map ensemble: per-geography means ----------------------
    try:
        truth_seeds = archive("ext_truth_ensemble.npz", "truth_seeds")
        noise_seeds = archive("ext_truth_ensemble.npz", "noise_seeds")
        r = archive("ext_truth_ensemble.npz", "cloudy_profiled_pearson")
        n_geo, n_noise = int(truth_seeds.size), int(noise_seeds.size)
        if r.size == n_geo * n_noise:
            blocked = r.reshape(n_geo, n_noise)
            stats["ensemble"] = {
                "n_geographies": n_geo, "seeds_per_geography": n_noise,
                "per_geography_mean": [float(x) for x in blocked.mean(axis=1)],
                "overall": one_sample(r),
                "between_map_sd": float(blocked.mean(axis=1).std(ddof=1)),
                "within_map_sd": float(blocked.std(ddof=1, axis=1).mean()),
                "fiducial_offset": float(blocked.mean(axis=1)[0]
                                         - r.mean())}
    except (FileNotFoundError, ValueError):
        # A fast-tier or partial ensemble archive simply does not get derived
        # statistics; the ledger then treats those numbers as unexplained.
        pass

    # ---- 5. the cover law: five weather arms, cover against r ------------
    # The manuscript's "the ordering of the arms is the ordering of their
    # covers" claim: Spearman -1 is visible by eye, the Pearson coefficient and
    # the fitted slope are not, and neither is archived.
    arms = ("ou_reference", "markov", "hawkes", "topo_anchored",
             "strong_anchor_arm")
    try:
        cloud = json.loads((RESULTS / "ext_cloud_physics.json")
                           .read_text(encoding="utf-8"))
        pairs = []
        for arm in arms:
            rec = cloud[arm]
            cover = rec.get("cover_mean")
            if cover is None:
                cover = float(np.mean(rec["cover_per_seed"]))
            pairs.append((float(cover), float(rec["r_mean"]), arm))
        pairs.sort()
        covers = np.asarray([p[0] for p in pairs])
        rs = np.asarray([p[1] for p in pairs])
        stats["cover_law"] = {
            "arms": [p[2] for p in pairs],
            "cover": [float(x) for x in covers],
            "r": [float(x) for x in rs],
            "pearson_r_cov": float(np.corrcoef(covers, rs)[0, 1]),
            "slope_dr_dcover": ols_slope(covers, rs)}
    except (KeyError, TypeError, ValueError):
        pass

    return stats


# --------------------------------------------------------------------------- #
# I/O and comparison
# --------------------------------------------------------------------------- #
def build() -> dict:
    return {
        "generated_by": "python3 tools/derive_stats.py --write",
        "comment": (
            "Derived statistics for the numeric provenance ledger.  Every "
            "value here is recomputed from shipped archives under results/ by "
            "tools/derive_stats.py, using src/expcommon.py::paired_stats for "
            "bootstrap intervals.  It is a build artifact, not pipeline "
            "evidence, which is why it lives in tools/ and not in results/.  "
            "CI regenerates it and fails on drift (--check)."),
        "method": {"helper": "src/expcommon.py::paired_stats",
                   "nboot": NBOOT, "rng_seed": BOOT_SEED,
                   "percentiles": [2.5, 97.5]},
        "stats": _strict(derive())}


def _strict(node):
    """Make the artifact strict JSON: an undefined statistic is ``null``.

    A ratio at the no-injection rung is $0/0$ (no drift, so no $t$), and Python
    would write that as a bare ``NaN`` -- which JSON has no spelling for.  Every
    reader of this file other than CPython (the demo app, a referee's script)
    would choke on it, and ``--check`` would compare NaN to NaN and call it
    agreement.  ``null`` says what is true: nothing is defined there.
    """
    import math

    if isinstance(node, dict):
        return {k: _strict(v) for k, v in node.items()}
    if isinstance(node, (list, tuple)):
        return [_strict(v) for v in node]
    if isinstance(node, bool) or not isinstance(node, (int, float)):
        return node
    if not math.isfinite(float(node)):
        return None
    return float(node)



def _flat(node, prefix=""):
    out = {}
    if node is None:
        out[prefix] = None
    elif isinstance(node, dict):
        for k, v in node.items():
            out.update(_flat(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(node, (list, tuple)):
        for i, v in enumerate(node):
            out.update(_flat(v, f"{prefix}[{i}]"))
    elif isinstance(node, (int, float)) and not isinstance(node, bool):
        out[prefix] = float(node)
    return out


def diff_committed(data: dict, tol: float = 1e-9) -> list[str]:
    """Compare a fresh derivation with the committed artifact, key by key."""
    if not OUT.exists():
        return [f"{OUT.name} is missing -- run: python3 tools/derive_stats.py"]
    old = _flat(json.loads(OUT.read_text(encoding="utf-8")).get("stats", {}))
    new = _flat(data["stats"])
    out = []
    for k in sorted(set(old) - set(new)):
        out.append(f"derived_stats:{k} is in the committed artifact but no "
                   f"longer derived (a source archive changed shape or went away)")
    for k in sorted(set(new) - set(old)):
        out.append(f"derived_stats:{k} is newly derived ({new[k]!r}) -- the "
                   f"committed artifact is stale; regenerate it")
    for k in sorted(set(old) & set(new)):
        a, b = old[k], new[k]
        if a is None or b is None:
            if a is not b:
                out.append(f"derived_stats:{k} drifted: committed {a!r}, "
                           f"freshly derived {b!r} -- a statistic went "
                           "undefined or came back from undefined")
            continue
        if abs(a - b) > tol:
            out.append(f"derived_stats:{k} drifted: committed {a!r}, "
                       f"freshly derived {b!r}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true",
                    help="regenerate the artifact (the default action)")
    ap.add_argument("--check", action="store_true",
                    help="re-derive and fail if the committed artifact differs")
    ap.add_argument("--list", action="store_true", dest="listing",
                    help="print every derived key and value")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    data = build()

    if args.listing:
        for k, v in sorted(_flat(data["stats"]).items()):
            print(f"{k:<62} {v!r}")
        return 0

    if args.check:
        bad = diff_committed(data)
        leaves = len(_flat(data["stats"]))
        if bad:
            print(f"derived stats: {len(bad)} of {leaves} derived values are "
                  f"out of date:")
            for line in bad[:40]:
                print("  -", line)
            return 1
        print(f"derived stats: {leaves} values, all reproducible from the "
              f"shipped archives")
        return 0

    args.out.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    try:
        shown = args.out.relative_to(ROOT)
    except ValueError:
        shown = args.out
    print(f"derived {len(_flat(data['stats']))} statistics -> {shown}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

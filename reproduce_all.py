"""Top-level reproduction entry point for the SGL time-domain-imaging project.

    python3 -m reproduce_all --fast              # cheap analytic stages + merge
    python3 -m reproduce_all --full              # the whole suite (hours)
    python3 -m reproduce_all --stages "quadrature clouds 3"
    python3 -m reproduce_all --fast --ext        # plus the Part VII extensions
    python3 -m reproduce_all --make-baseline /tmp/base.json
    python3 -m reproduce_all --check --baseline /tmp/base.json

WHAT IT DOES
Every stage is executed in a SCRATCH COPY of ``results/`` (``--scratch``, default
``/tmp/sgl_reproduce_<pid>``), never in the shipped tree: the harness honours the
``SGL_RESULTS_DIR`` environment variable (see ``src/expcommon.py``), so a
verification run cannot overwrite an audited number.  Afterwards the scratch
archives are compared, leaf by leaf and array by array, against the shipped ones
and a diff report is printed.  Exit code is non-zero if anything differs beyond
``--tol`` (default 0, i.e. bit-for-bit; use 1e-12 for BLAS-order-sensitive
stages on a different machine).

TIERS
``--fast`` runs the seven stages that cost ~2 minutes in total and need no
simulation checkpoints: setup, quadrature, ledger, validation, precision,
diagnostics, merge.  They recompute ``results/quadrature.npz``,
``ledger.npz``, ``validation.npz``, ``kernel_convergence.json``,
``uniform_disk.json``, ``core_ablation.json``, ``kinematics.json``,
``deflation_diag.json``, ``precision.json`` and rebuild ``audit.json``
from the shipped checkpoints.  That is a real test of the DERIVATION half of the
pipeline; it does not re-simulate photons.

``--full`` additionally re-runs every simulation stage.  With ``--from-zero`` the
scratch checkpoints are deleted first, so the entire suite is re-simulated
(cost: hours on 4 cores; each new campaign dataset is ~25 s and each fit ~8 s).

STAGE NAMES
A stage name is a subcommand of ``src/run_experiments.py``; ``--stages`` takes a
space-separated list where a stage may be followed by its own arguments, e.g.
``--stages "quadrature clouds 3 cadence photons 2"``.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
RESULTS = ROOT / "results"

# ---------------------------------------------------------------- stages ----
# (subcommand, [args]) -- the complete inventory that produced results/*.
def full_stages():
    st = [("setup", []), ("quadrature", []), ("ledger", []), ("validation", [])]
    st += [("clouds", [str(i)]) for i in range(5)]
    st += [("cadence", [arm, str(i)]) for arm in ("photons", "wallclock")
           for i in range(5)]
    st += [("cadence_control", [arm, str(i), kind])
           for arm in ("photons", "wallclock") for i in range(5)
           for kind in ("cf", "iid")]
    st += [("components", []), ("robust_debias", []), ("robust_clim", []),
           ("robust_geom", []), ("robust_prof", []), ("resolution", []),
           ("nulls_cloud", []), ("nulls", []), ("systematics", [])]
    st += [("lam_sweep", [str(i)]) for i in (0, 3)]
    st += [("lam_ext", [str(i)]) for i in (0, 3)]
    st += [("lam_res", [str(i)]) for i in (0, 3)]
    st += [("robust_weather", [v]) for v in
           ("corr8", "corr20", "u3", "u12", "tau2", "tau8")]
    st += [("robust_morph", [str(i)]) for i in (0, 3)]
    st += [("sigma_sens", []), ("sigma_sens_est", []), ("static_ref", []),
           ("latband", []), ("diagnostics", []), ("precision", [])]
    st.append(("merge", []))
    return st


FAST_STAGES = [("setup", []), ("quadrature", []), ("ledger", []),
               ("validation", []), ("diagnostics", []), ("precision", []),
               ("merge", [])]

# Part VII extension modules (src/ext/).  Each writes only results/ext_<name>.
EXT_MODULES = ("fisher_bounds", "corona_screen", "disk_kernel", "ephemeris",
               "portability", "telemetry", "truth_ensemble", "evidence_lambda",
               "scheduling", "priors", "observable_roc", "cloud_physics",
               "swarm", "target_uncertainty")


# ---------------------------------------------------------------- running ----
def run_stage(name, args, env):
    cmd = [sys.executable, "run_experiments.py", name, *args]
    t0 = time.time()
    p = subprocess.run(cmd, cwd=str(SRC), env=env, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    dt = time.time() - t0
    tail = [ln for ln in p.stdout.splitlines() if ln.strip()][-3:]
    for ln in tail:
        print("    |", ln[:150])
    print(f"  [{name} {' '.join(args)}] rc={p.returncode} {dt:.1f}s")
    if p.returncode != 0:
        print(p.stdout[-4000:])
    return p.returncode, dt


def parse_stages(spec):
    """Group a flat token list into (stage, args) using known subcommands."""
    known = {n for n, _ in full_stages()} | {"merge"}
    out, cur = [], None
    for tok in spec.split():
        if tok in known:
            if cur:
                out.append(cur)
            cur = (tok, [])
        elif cur:
            cur[1].append(tok)
        else:
            raise SystemExit(f"--stages: unknown stage {tok!r}; known: "
                             + " ".join(sorted(known)))
    if cur:
        out.append(cur)
    return out


# ---------------------------------------------------------------- diffing ----
def walk_json(obj, pre=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from walk_json(v, f"{pre}.{k}" if pre else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_json(v, f"{pre}[{i}]")
    else:
        yield pre, obj


IGNORE_JSON = {"generated_utc"}


def _ignored(key):
    """A leaf is ignored if it is a timestamp wherever it sits in the tree."""
    return key.split(".")[-1].split("[")[0] in IGNORE_JSON


def diff_json(ref_path, new_path, tol):
    a = dict(walk_json(json.loads(ref_path.read_text())))
    b = dict(walk_json(json.loads(new_path.read_text())))
    keys = sorted(set(a) | set(b))
    bad, worst = [], 0.0
    for k in keys:
        if _ignored(k):
            continue
        va, vb = a.get(k, "<missing>"), b.get(k, "<missing>")
        if va == "<missing>" or vb == "<missing>":
            bad.append((k, va, vb, "presence"))
            continue
        if isinstance(va, bool) or isinstance(vb, bool):
            # type-sensitive: True/1 must not read as agreement, or a flag that
            # was silently replaced by a count would pass the gate
            if type(va) is not type(vb) or va != vb:
                bad.append((k, va, vb, "bool"))
            continue
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            if va is None or vb is None:
                continue
            d = abs(float(va) - float(vb))
            scale = max(1.0, abs(float(va)))
            worst = max(worst, d / scale)
            if d / scale > tol:
                bad.append((k, va, vb, d))
        elif str(va) != str(vb) and not (va is None and vb is None):
            bad.append((k, va, vb, "str"))
    return bad, worst, len(keys)


def diff_npz(ref_dir, new_dir, tol):
    import numpy as np
    files = sorted(p.name for p in ref_dir.glob("*.npz"))
    new = {p.name for p in new_dir.glob("*.npz")}
    bad, worst, n_arr = [], 0.0, 0
    for f in files:
        if f not in new:
            bad.append((f, "<present>", "<missing>", "presence"))
            continue
        A, B = np.load(ref_dir / f, allow_pickle=True), np.load(new_dir / f,
                                                                allow_pickle=True)
        for k in sorted(set(A.files) | set(B.files)):
            if k not in A.files or k not in B.files:
                bad.append((f"{f}:{k}", "in-ref" if k in A.files else "-",
                            "in-new" if k in B.files else "-", "presence"))
                continue
            x, y = np.asarray(A[k]), np.asarray(B[k])
            n_arr += 1
            if x.shape != y.shape:
                bad.append((f"{f}:{k}", x.shape, y.shape, "shape"))
                continue
            if x.dtype.kind in "SUO" or x.dtype == bool:
                if not np.array_equal(x, y):
                    bad.append((f"{f}:{k}", "labels", "differ", "labels"))
                continue
            if x.size == 0:
                continue
            xf, yf = x.astype(float), y.astype(float)
            if not np.array_equal(np.isfinite(xf), np.isfinite(yf)):
                bad.append((f"{f}:{k}", "nan mask", "differs", "mask"))
                continue
            with np.errstate(invalid="ignore"):
                dif = np.abs(xf - yf)
            fin = dif[np.isfinite(dif)]
            d = float(fin.max()) if fin.size else 0.0
            ref = np.abs(xf[np.isfinite(xf)])
            sc = float(ref.max()) if ref.size else 1.0
            rel = d / (sc or 1.0)
            worst = max(worst, rel)
            if rel > tol:
                bad.append((f"{f}:{k}", d, rel, "numeric"))
    return bad, worst, len(files), n_arr


# ------------------------------------------------------------------ main ----
def main(argv=None):
    ap = argparse.ArgumentParser(prog="python3 -m reproduce_all")
    ap.add_argument("--fast", action="store_true", help="cheap stages only")
    ap.add_argument("--full", action="store_true", help="every simulation stage")
    ap.add_argument("--stages", type=str, default=None,
                    help='explicit stages, e.g. "quadrature clouds 3"')
    ap.add_argument("--ext", action="store_true",
                    help="also run the Part VII extension modules in src/ext/")
    ap.add_argument("--check", action="store_true",
                    help="compare only; run nothing")
    ap.add_argument("--baseline", type=str, default=None,
                    help="manifest written by --make-baseline, for --check")
    ap.add_argument("--make-baseline", type=str, default=None, metavar="PATH",
                    help="write a byte-level manifest of results/ and exit")
    ap.add_argument("--from-zero", action="store_true",
                    help="delete scratch checkpoints first (full re-simulation)")
    ap.add_argument("--no-cache", action="store_true",
                    help="delete scratch results/cache (re-simulate datasets)")
    ap.add_argument("--scratch", type=str, default=None)
    ap.add_argument("--tol", type=float, default=0.0,
                    help="relative tolerance for the archive diff (0 = exact)")
    ap.add_argument("--keep", action="store_true", help="keep the scratch tree")
    ap.add_argument("--figures", action="store_true",
                    help="regenerate paper/figures from the scratch archives")
    args = ap.parse_args(argv)

    if args.make_baseline:
        return subprocess.run([sys.executable, str(ROOT / "tools" / "array_manifest.py"),
                               "write", str(RESULTS), args.make_baseline]).returncode

    if args.check:
        # No stage is run: the shipped tree is compared against a frozen
        # byte-level manifest.  This is the CI drift check.
        base = Path(args.baseline or "tools/baseline_manifest.json")
        if not base.exists():
            print(f"no baseline manifest at {base}; create it with "
                  f"python3 -m reproduce_all --make-baseline {base}")
            return 2
        print("\n=== baseline manifest check (no stages run) ===")
        return subprocess.run([sys.executable, str(ROOT / "tools" / "array_manifest.py"),
                               "check", str(RESULTS), str(base)]).returncode

    if args.stages:
        stages = parse_stages(args.stages)
    elif args.full:
        stages = full_stages()
    else:
        stages = list(FAST_STAGES)

    scratch = Path(args.scratch or f"/tmp/sgl_reproduce_{os.getpid()}")
    sres = scratch / "results"
    if scratch.exists():
        shutil.rmtree(scratch)
    print(f"copying results/ -> {sres} ...", flush=True)
    scratch.mkdir(parents=True)
    shutil.copytree(RESULTS, sres, symlinks=True)
    if args.from_zero:
        for p in sres.glob("parts/*.npz"):
            p.unlink()
        print("  scratch checkpoints deleted (--from-zero)")
    if args.no_cache:
        shutil.rmtree(sres / "cache", ignore_errors=True)
        print("  scratch cache deleted (--no-cache)")
    # The harness is redirected, not copied: stages still run from src/ (flat
    # imports) but read and write the scratch archives only.
    env = dict(os.environ, SGL_RESULTS_DIR=str(sres))

    t_all, rc_all = time.time(), 0
    for name, a in stages:
        rc, _ = run_stage(name, a, env)
        rc_all |= rc

    ext_out = {}
    if args.ext:
        for m in EXT_MODULES:
            f = SRC / "ext" / f"{m}.py"
            if not f.exists():
                print(f"  [ext.{m}] MISSING (skipped)")
                continue
            cmd = [sys.executable, "-m", f"ext.{m}"]
            if args.fast or not args.full:
                cmd.append("--fast")
            t0 = time.time()
            p = subprocess.run(cmd, cwd=str(SRC), env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            ext_out[m] = p.returncode
            rc_all |= p.returncode
            line = [ln for ln in p.stdout.splitlines()
                    if ln.startswith("SUMMARY_JSON")]
            print(f"  [ext.{m}] rc={p.returncode} {time.time() - t0:.1f}s "
                  f"{(line[-1][:200] if line else '')}")
            if p.returncode:
                print(p.stdout[-3000:])

    if args.figures:
        rc_all |= run_script("make_figures.py", env, sres)

    # ---------------- diff report ----------------
    ref_audit = RESULTS / "audit.json"
    new_audit = sres / "audit.json"
    print("\n=== reproduction diff report ===")
    fails = 0
    if ref_audit.exists() and new_audit.exists():
        bad, worst, n = diff_json(ref_audit, new_audit, args.tol)
        print(f"audit.json: {n} leaves compared, {len(bad)} differ, "
              f"worst rel diff {worst:.3e} (tol {args.tol:g})")
        for k, va, vb, d in bad[:25]:
            print(f"  DIFF {k}: shipped={va} rerun={vb} ({d})")
        fails += len(bad)
        b2, w2, nf, na = diff_npz(RESULTS, sres, args.tol)
        print(f"archives: {nf} npz files, {na} arrays compared, {len(b2)} differ, "
              f"worst rel diff {w2:.3e}")
        for k, va, vb, d in b2[:25]:
            print(f"  DIFF {k}: {va} vs {vb} ({d})")
        fails += len(b2)
    else:
        print("audit.json missing in one of the trees")
        fails += 1
    print(f"total wall clock {time.time() - t_all:.1f}s; "
          f"stage failures {rc_all}")
    if fails or rc_all:
        print(f"RESULT: FAIL ({fails} differing items)")
    else:
        print("RESULT: OK (0 archive diffs)")
    if not args.keep:
        shutil.rmtree(scratch, ignore_errors=True)
    else:
        print(f"scratch kept at {scratch}")
    return 1 if (fails or rc_all) else 0


def run_script(script, env, sres):
    p = subprocess.run([sys.executable, script], cwd=str(SRC), env=env,
                       text=True, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    print(f"  [{script}] rc={p.returncode}")
    if p.returncode:
        print(p.stdout[-2000:])
    return p.returncode


if __name__ == "__main__":
    sys.exit(main())

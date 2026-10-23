#!/usr/bin/env python3
"""Numeric provenance ledger for the manuscript -- the research analogue of a
build step plus a unit test.

A paper ships two kinds of object: prose that a reader can skim, and numbers
that a reader has to trust.  The trust problem is what this tool removes.  It
maintains an explicit ledger (``tools/claims_ledger.json``) in which every
reported number is a quadruple

    a verbatim sentence fragment from the manuscript,
    the exact digits the manuscript prints inside that fragment,
    a dotted key inside a shipped archive under ``results/``,
    the display precision that key is quoted at.

``--check`` then re-derives the string from the archive and fails if the two no
longer agree.  That single rule catches both directions of drift a submission
accumulates: an archive that changed under the text (the paper now reports a
stale number) and a text that changed under the archive (the ledger can no
longer vouch for the sentence).  Neither is visible to a reader, and both are
invisible to a spell checker.

Three further modes exist because a ledger you can grow is a ledger you can
audit:

``--harvest``  rebuilds the ledger from scratch by matching every distinctive
               numeric string in the manuscript against every scalar leaf of
               the archives.  It is how the ledger was seeded and how it is
               extended after a results change; ``--check`` is what CI runs.
``--report``   prints the ledger as a table, plus the manuscript numbers that
               are NOT traceable, which is the coverage question a referee
               asks ("where does each figure come from?").
``--coverage`` prints only the coverage counters and exits non-zero when the
               ledger is smaller than ``--min-claims`` or the untraceable list
               is longer than ``--max-untraceable``.

Quotes are compared on whitespace-flattened text, because LaTeX line breaks
inside a number or around a ``\\pm`` are a formatting choice, not content.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
LEDGER = ROOT / "tools" / "claims_ledger.json"
DERIVED = ROOT / "tools" / "derived_stats.json"
MANUSCRIPT = ROOT / "paper" / "main.tex"
INPUTS = {"targets_table": ROOT / "paper" / "targets_table.tex"}

# how wide the ledger's own docstring says the entry schema is
ENTRY_KEYS = {"id", "kind", "quote", "src", "key", "digits", "shown", "note"}
KINDS = {"value", "count", "relation"}

# a scalar leaf is only harvestable if the manuscript prints it with at least
# this many significant characters; "0.20" or "3.0" are too generic to vouch
# for a specific source key.
MIN_STR_LEN = 5
MAX_PRECISION = 7


def hit_limit(s: str) -> int:
    """How often a printed form may occur and still name one particular leaf.

    "0.20" appearing 90 times proves nothing; "$\\Delta r=-0.198$" repeated
    six times is still the same reported quantity.  Specificity, not
    frequency, is what decides whether a string can vouch for a key.
    """
    return 4 if len(s) < 6 else 24

# Commas are ambiguous in English prose and in LaTeX alike: "20,000" is one
# grouped number, while "$n=16,32,128$" is a list of three designs.  A run is
# therefore read as one number only in its two-group thousands form, which is
# all the manuscript needs -- it never prints above 99,999 without a separator.
GROUPED_RE = re.compile(r"\d{1,3},\d{3}(?:\.\d+)?")
RUN_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?")
INPUT_RE = re.compile(r"\\input\{([^}]+)\}")


# --------------------------------------------------------------------------- #
# manuscript text
# --------------------------------------------------------------------------- #
def raw_manuscript() -> str:
    """main.tex with ``\\input{...}`` fragments spliced in, as LaTeX sees it."""
    text = MANUSCRIPT.read_text(encoding="utf-8")

    def splice(m: re.Match) -> str:
        name = m.group(1)
        path = INPUTS.get(name)
        if path is None or not path.exists():
            return m.group(0)
        return path.read_text(encoding="utf-8")

    return INPUT_RE.sub(splice, text)


def body(text: str) -> str:
    """The document body only, without the bibliography.

    The ledger is about *reported results*.  The preamble is typesetting
    parameters, and the reference list carries other people's volume numbers
    and arXiv IDs, none of which are ours to trace; leaving either in would
    only teach the coverage count to ignore real gaps.
    """
    m = re.search(r"\\begin\{document\}", text)
    if m:
        text = text[m.end():]
    m = re.search(r"\\end\{document\}", text)
    if m:
        text = text[:m.start()]
    text = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}",
                  " ", text, flags=re.S)
    return re.sub(r"ORCID:\s*[\d\-]+", " ", text)


def flat_manuscript() -> str:
    """Comment-stripped, whitespace-flattened manuscript body: one long line.

    Comments are removed line-wise BEFORE flattening, because once the newlines
    are gone a ``%`` would silently delete the rest of the document.  LaTeX's
    ``{,}`` thousands separator is normalised to a plain comma, so that
    "43{,}019.9" and "43,019.9" are one number rather than two tokens.
    """
    text = re.sub(r"(?<!\\)%.*", " ", body(raw_manuscript()))
    return " ".join(text.replace("{,}", ",").split())


def iter_numbers(text: str):
    """Yield ``(token, offset)`` for every printed number in ``text``.

    Three typographic traps, each handled here:

    * A LaTeX en dash is two hyphens, so "666[283--1148]" would otherwise be
      read as a negative 1148.  When the minus is really the second half of a
      dash it is dropped and the magnitude is what stands.
    * Runs are matched greedily from their first digit, so "0.0067" is never
      extracted out of "-0.0067" and a standard error cannot claim credit for
      a confidence bound that merely shares its digits.
    * "$n=16,32,128$" and "$t_s=7200,3600,1800,900,450$~s" are lists, not
      large numbers; only the two-group thousands spelling stays united.
    """
    for m in RUN_RE.finditer(text):
        run, start = m.group(0), m.start()
        if run.endswith(","):
            run = run[:-1]
        if run.startswith("-") and start > 0 and text[start - 1] == "-":
            run, start = run[1:], start + 1      # back half of an en dash
        if "," in run and not GROUPED_RE.fullmatch(run):
            pos = start
            for part in run.split(","):
                if part and part != "-":
                    yield part, pos
                pos += len(part) + 1
            continue
        if run and run != "-":
            yield run, start


def token_index(text: str) -> dict[str, list[int]]:
    """Every printed number in the manuscript, with its offsets.

    Building this once turns harvesting from a scan per archive leaf into a
    dictionary lookup; the regex also enforces token boundaries, so "0.0067"
    is never found inside "-0.0067".
    """
    out: dict[str, list[int]] = {}
    for tok, start in iter_numbers(text):
        out.setdefault(tok, []).append(start)
    return out


# --------------------------------------------------------------------------- #
# archive index
# --------------------------------------------------------------------------- #
def _walk(obj, prefix: str, out: dict) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            _walk(v, f"{prefix}.{k}" if prefix else str(k), out)
    elif isinstance(obj, (list, tuple)):
        out[prefix] = len(obj)
        for i, v in enumerate(obj):
            _walk(v, f"{prefix}[{i}]", out)
    elif isinstance(obj, bool) or obj is None:
        return
    elif isinstance(obj, (int, float)):
        out[prefix] = obj


def json_leaves(out: dict) -> None:
    for path in sorted(RESULTS.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        leaf: dict = {}
        _walk(data, "", leaf)
        for k, v in leaf.items():
            out[f"{path.name}::{k}"] = v


def npz_leaves(out: dict, max_size: int = 64) -> None:
    """Scalars stored in ``results/*.npz``.

    A 0-d array is a stored scalar; a short vector is indexed element-wise.
    The reference grammar is ``file::array`` for a stored scalar and
    ``file::array[i]`` or ``file::array[i,j]`` for an element.
    """
    import numpy as np

    for path in sorted(RESULTS.glob("*.npz")):
        try:
            arch = np.load(path, allow_pickle=True)
        except Exception:  # noqa: BLE001 - an unreadable archive is not fatal
            continue
        for name in arch.files:
            try:
                arr = np.asarray(arch[name])
            except Exception:  # noqa: BLE001
                continue
            if arr.dtype.kind not in "iuf":
                continue
            if arr.ndim == 0:
                out[f"{path.name}::{name}"] = arr.item()
            elif arr.size <= max_size:
                for idx in np.ndindex(*arr.shape):
                    out[f"{path.name}::{name}[{','.join(map(str, idx))}]"] = \
                        float(arr[idx])


def derived_leaves(out: dict, max_size: int = 2000, max_cells: int = 800) -> None:
    """Reductions of the shipped arrays, under the same reference grammar.

    This is what makes a table cell traceable.  The manuscript's per-method,
    per-cloud-cover table prints the mean over the 10 paired seeds, and the
    archive stores the 10 seeds, not the mean: ``clouds.npz::ssim_mat[2,1]``
    would be one seed, while ``clouds.npz::ssim_mat[2,1]{mean}`` is the number
    in the paper.  A claim may therefore name an axis-wise reduction, and the
    checker recomputes it from the shipped bytes.  Only arrays small enough to
    be a *result* rather than a *map* are reduced, so a 2,592-cell albedo image
    cannot lend its pixels to a headline correlation.
    """
    import numpy as np

    ops = {"mean": np.mean, "median": np.median, "min": np.min, "max": np.max,
           "sd": lambda a: np.std(a, ddof=1) if a.size > 1 else 0.0,
           "se": lambda a: (np.std(a, ddof=1) / np.sqrt(a.size)
                            if a.size > 1 else 0.0)}
    for path in sorted(RESULTS.glob("*.npz")):
        try:
            arch = np.load(path, allow_pickle=True)
        except Exception:  # noqa: BLE001
            continue
        for name in arch.files:
            try:
                arr = np.asarray(arch[name])
            except Exception:  # noqa: BLE001
                continue
            if arr.dtype.kind not in "iuf" or arr.ndim == 0:
                continue
            if arr.size > max_size or arr.ndim > 3:
                continue
            for op, fn in ops.items():
                out[f"{path.name}::{name}{{{op}}}"] = float(fn(arr))
                if arr.ndim == 1:
                    continue
                for n, idx in enumerate(np.ndindex(*arr.shape[:-1])):
                    if n >= max_cells:
                        break
                    sub = arr[idx]
                    out[f"{path.name}::{name}"
                        f"[{','.join(map(str, idx))}]{{{op}}}"] = float(fn(sub))


def parts_leaves(out: dict, max_size: int = 64) -> None:
    """Checkpoint archives under ``results/parts/``.

    The pipeline's stage summaries are derived from these, and a handful of
    published counts -- solver evaluations per arm, per-seed losses -- exist
    only here.  Reading them is what keeps such a claim from being called
    unexplained.
    """
    import numpy as np

    for path in sorted((RESULTS / "parts").glob("*.npz")):
        try:
            arch = np.load(path, allow_pickle=True)
        except Exception:  # noqa: BLE001
            continue
        for name in arch.files:
            try:
                arr = np.asarray(arch[name])
            except Exception:  # noqa: BLE001
                continue
            if arr.dtype.kind not in "iuf" or arr.size == 0:
                continue
            ref = f"parts/{path.name}::{name}"
            if arr.ndim == 0:
                out[ref] = arr.item()
            elif arr.size <= max_size:
                for idx in np.ndindex(*arr.shape):
                    out[f"{ref}[{','.join(map(str, idx))}]"] = float(arr[idx])


def derived_leaves_from_stats(out: dict) -> None:
    """Statistics rebuilt from the archives by ``tools/derive_stats.py``.

    A bootstrap interval, a paired $t$, a band mean over seeds and harmonics:
    these are one remove from the evidence, so no shipped archive holds them.
    Rather than let the manuscript print them unexplained, the build step
    recomputes them from ``results/`` with the pipeline's own helper and writes
    ``tools/derived_stats.json``, which is indexed here like any other archive.
    Regenerating it is part of the gate, so a number backed only by a derived
    statistic is still backed by something a machine re-derives on every run.
    """
    if not DERIVED.exists():
        return
    try:
        data = json.loads(DERIVED.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return
    leaf: dict = {}
    _walk(data.get("stats", {}), "", leaf)
    for k, v in leaf.items():
        out[f"derived_stats.json::{k}"] = v


def archive_values(with_npz: bool = True) -> dict:
    out: dict = {}
    json_leaves(out)
    derived_leaves_from_stats(out)
    if with_npz:
        npz_leaves(out)
        derived_leaves(out)
        parts_leaves(out)
    return out


def resolve(ref: str, values: dict):
    if ref not in values:
        raise KeyError(f"unknown archive reference {ref!r}")
    return values[ref]


# --------------------------------------------------------------------------- #
# hand-written relations: numbers the paper derives from other numbers
# --------------------------------------------------------------------------- #
# A harvested claim answers "which archive holds this number?".  It cannot
# answer "why does the paper print -0.198 next to 0.1444 and 0.3422?", and it
# cannot see a sentence whose arithmetic is wrong while every number in it is
# right.  These entries close that gap for the quantities the paper *computes*
# in prose: each names the leaves, the arithmetic, and the sentence.
RELATIONS: list[dict] = [
    {"id": "rel-surface-cloud-delta-r", "kind": "relation",
     "expr": "surf - fiducial",
     "vars": {"surf": "ext_cloud_physics.json::headline.archived_collapse_r",
              "fiducial": "ext_cloud_physics.json::headline.r_ou_mean"},
     "shown": "-0.1978", "digits": 4,
     "quote": "a paired loss of $\\Delta r = -0.1978 \\pm 0.0175$",
     "statement": "the surface--cloud coupling loss is the archived "
                  "collapsed r minus the fiducial OU r",
     "note": "both terms are archived headline scalars of "
             "ext_cloud_physics.json; their difference is computed in prose "
             "and stored nowhere"},
    {"id": "rel-surface-cloud-delta-r-abbrev", "kind": "relation",
     "expr": "surf - fiducial",
     "vars": {"surf": "ext_cloud_physics.json::headline.archived_collapse_r",
              "fiducial": "ext_cloud_physics.json::headline.r_ou_mean"},
     "shown": "-0.198", "digits": 3,
     "quote": "a paired loss of $-0.198\\pm0.017$",
     "statement": "the same loss, quoted to three decimals in the results "
                  "section",
     "note": "the identical archived pair as rel-surface-cloud-delta-r, "
             "printed at a different display precision"},
    {"id": "rel-surface-cloud-t", "kind": "relation",
     "expr": "(surf - fiducial) / se",
     "vars": {"surf": "derived_stats.json::seedtable.surface_coupled.mean",
              "fiducial": "derived_stats.json::seedtable.tdi_fiducial.mean",
              "se": "derived_stats.json::contrasts.surface_minus_tdi.se"},
     "shown": "-11.3", "digits": 1,
     "quote": "($t=-11.3$, 0/10 seeds)",
     "statement": "the quoted t is the paired loss over its standard error",
     "note": "all three terms are derived from the per-seed columns of "
             "Table tab:app_seeds by tools/derive_stats.py"},
    {"id": "rel-surface-cloud-pt", "kind": "relation",
     "expr": "1000000 * p_t",
     "vars": {"p_t": "derived_stats.json::contrasts.surface_minus_tdi.p_t"},
     "shown": "1.3", "digits": 1,
     "scale": 1,
     "quote": "$p_t = 1.3 \\times 10^{-6}$, 10/10 seeds",
     "statement": "the paired t-test p of the surface--cloud loss, printed as "
                  "a mantissa against the $10^{-6}$ power of ten",
     "note": "the exponent is typography; the mantissa is the archived "
             "probability scaled by a million"},
    {"id": "rel-surface-cloud-seeds-against", "kind": "relation",
     "expr": "n - favour",
     "vars": {"n": "derived_stats.json::contrasts.surface_minus_tdi.n",
              "favour": "derived_stats.json::contrasts.surface_minus_tdi.n_favour"},
     "shown": "0", "digits": 0,
     "quote": "($t=-11.3$, 0/10 seeds)",
     "statement": "no seed favoured the opposite sign of the surface--cloud "
                  "loss, which is what the abstract's 10/10 sentence claims",
     "note": "printed as a fraction, so the digits field is the numerator"},
    {"id": "rel-cloudy-ceiling-loss", "kind": "relation",
     "expr": "cloudy - clear",
     "vars": {"cloudy": "audit.json::components.F_full_tdi.r.mean",
              "clear": "audit.json::clouds.fiducial.r_profiled.mean"},
     "shown": "-0.6364", "digits": 4,
     "quote": "a paired loss of $\\Delta r = -0.6364\\pm0.0083$",
     "statement": "the cloud-limited ceiling is the fiducial cloudy "
                  "correlation minus the rotating cloud-free one",
     "note": "cloudy is the F_full_tdi component mean and clear the fiducial "
             "rotating cloud-free mean, both archived in audit.json"},
    {"id": "rel-anchored-gain-retention", "kind": "relation",
     "expr": "anchored / unprofiled * 100",
     "vars": {"anchored": 774.1, "unprofiled": 913.7},
     "shown": "84.72", "digits": 2,
     "quote": "for the anchored profile ($84.72\\%$ retained)",
     "statement": "the retention percentage is the ratio of the two gains "
                  "quoted in the same sentence",
     "note": "hand-written; the two gains are the archived 774.05 and 913.68 "
             "of deflation_diag.json, rounded as printed"},
    {"id": "rel-common-mode-retention", "kind": "relation",
     "expr": "(1 - 1/nsub) * 100",
     "vars": {"nsub": "audit.json::conventions.nsub"},
     "shown": "93.75", "digits": 2,
     "quote": "while retaining $1-1/N_{\\rm sc}=93.75\\%$ of the information",
     "statement": "the information retained after removing one common mode "
                  "of N_sc",
     "note": "nsub is the archived convention in audit.json; the 1 and the "
             "100 are exact arithmetic, not results"},
    {"id": "rel-common-mode-rank-reduction", "kind": "relation",
     "expr": "100 / nsub",
     "vars": {"nsub": "audit.json::conventions.nsub"},
     "shown": "6.25", "digits": 2,
     "quote": "(6.25\\% rank reduction)",
     "statement": "the rank reduction is the complement of the retention",
     "note": "one common mode out of the archived nsub=16, expressed as a "
             "percentage; it is the complement of "
             "rel-common-mode-retention"},
    {"id": "rel-orbital-phase-sweep", "kind": "relation",
     "expr": "360 * campaign / year",
     "vars": {"campaign": 87.33, "year": 365.25},
     "shown": "86.1", "digits": 1,
     "quote": "drifts through $86.1^\\circ$ of orbital phase over the 87.33-day",
     "statement": "the sub-stellar longitude swept in one fiducial campaign",
     "note": "360 degrees and the 365.25-day Julian year are definitions, not "
             "results; 87.33 is the fiducial campaign length the same "
             "sentence names"},
    {"id": "rel-90-day-phase-sweep", "kind": "relation",
     "expr": "360 * window / year",
     "vars": {"window": 90.0, "year": 365.25},
     "shown": "88.7", "digits": 1,
     "quote": "$88.7^\\circ$ over a 90.0-day window",
     "statement": "the same sweep evaluated over a round 90-day window",
     "note": "90.0 is the round window the sentence itself names and 365.25 "
             "the Julian year, so neither input is an experimental result"},
    {"id": "rel-image-diameter", "kind": "relation",
     "expr": "2 * r_earth * z / (pc * dist)",
     "vars": {"r_earth": 6371.0, "z": 650.0, "pc": 206264.806, "dist": 30.0},
     "shown": "1.338", "digits": 3,
     "quote": "=1.338\\;{\\rm km}",
     "statement": "an Earth radius at 30 pc, magnified to 650 AU, projected "
                  "as a kilometre-scale image",
     "note": "hand-written; the constants are the IAU values, not results"},
    {"id": "rel-strong-interference-onset", "kind": "relation",
     "expr": "b * b / (2 * r_g * AU)",
     "vars": {"b": 695700.0, "r_g": 2.953, "AU": 149597870.7},
     "shown": "547.8", "digits": 1,
     "quote": "$z_0\\simeq b^2/2r_g\\simeq547.8$~AU",
     "statement": "the focal distance b^2/2r_g for grazing rays at one solar "
                  "radius",
     "note": "hand-written; r_g is the 2.95 km quoted in the same sentence"},
    {"id": "rel-free-profile-retention", "kind": "relation",
     "expr": "free / unprofiled * 100",
     "vars": {"free": 18.79, "unprofiled": 913.7},
     "shown": "2.06", "digits": 2,
     "quote": "($2.06\\%$ retained)",
     "statement": "the free profile keeps two per cent of the disk-integrated "
                  "albedo response",
     "note": "the two gains are the archived 18.79025 and 913.67660 constant "
             "mode gains of deflation_diag.json profiling tree, rounded as "
             "printed"},
    # ---- raster kinematics (Section 2, the stop-and-dwell bound) ----------
    # The design states the image pitch and the translation budget; the
    # velocities are arithmetic on them, and the cumulative impulse is
    # arithmetic on the hop count.  Chained so a change to the raster pitch
    # propagates instead of leaving a stale km/s figure behind.
    {"id": "rel-raster-pitch", "kind": "relation",
     "expr": "2 * r_earth * z * 1000 / (pc * dist * n)",
     "vars": {"r_earth": 6371.0, "z": 650.0, "pc": 206264.806, "dist": 30.0,
              "n": 64.0},
     "shown": "20.913", "digits": 3,
     "quote": "$\\Delta_{\\rm img} = 20.913$~m",
     "statement": "the raster pitch is the projected Earth diameter at 30 pc, "
                  "magnified to 650 AU, divided into the 64x64 grid",
     "note": "hand-written; IAU constants and the design grid, not results"},
    {"id": "rel-stop-and-dwell-vmax", "kind": "relation",
     "expr": "2 * pitch / budget",
     "vars": {"pitch": 20.913398073, "budget": 30.0},
     "shown": "1.394", "digits": 3,
     "quote": "$v_{\\rm max} = 2\\Delta/\\Delta t \\simeq 1.394$~m\\,s$^{-1}$",
     "statement": "peak velocity of a rest-to-rest bang-bang hop across one "
                  "pitch inside the 30~s translation budget",
     "note": "hand-written; pitch is the value derived by rel-raster-pitch, "
             "carried here at full precision"},
    {"id": "rel-stop-and-dwell-hop-dv", "kind": "relation",
     "expr": "2 * v",
     "vars": {"v": 1.394226538},
     "shown": "2.788", "digits": 3,
     "quote": "$\\Delta v_{\\rm hop} = 2 v_{\\rm max} \\simeq 2.788$~m\\,s$^{-1}$",
     "statement": "a rest-to-rest hop costs two velocity reversals",
     "note": "hand-written; v is the peak velocity printed in the same "
             "sentence, which rel-stop-and-dwell-vmax derives from the pitch"},
    {"id": "rel-slot-hops", "kind": "relation",
     "expr": "passes * (slots - 1)",
     "vars": {"passes": 16.0, "slots": 256.0},
     "shown": "4,080", "digits": 0,
     "quote": "16\\times255=4,080$ times",
     "statement": "slot-to-slot hops per spacecraft over the fiducial campaign",
     "note": "hand-written; 16 passes and 256 dwell slots per pass are the "
             "design values stated in the same subsection"},
    {"id": "rel-cumulative-impulsive-dv", "kind": "relation",
     "expr": "hops * 2 * (2 * pitch / budget) / 1000",
     "vars": {"hops": 4080.0, "pitch": 20.913398073, "budget": 30.0},
     "shown": "11.38", "digits": 2,
     "quote": "$\\approx 11.38$~km\\,s$^{-1}$",
     "statement": "the cumulative impulsive budget of stop-and-dwell rastering",
     "note": "hops is the count derived by rel-slot-hops and the parenthesised "
             "term is the v_max of rel-stop-and-dwell-vmax; the 2 is the "
             "reversal pair of a rest-to-rest hop and the 1000 metres to "
             "kilometres"},
    {"id": "rel-uncapped-analytic-n32", "kind": "relation",
     "expr": "4 * a64",
     "vars": {"a64": "validation.npz::theory[1]"},
     "shown": "1.1646", "digits": 4,
     "quote": "$4\\times0.29115=1.1646$",
     "statement": "halving the grid doubles D and halves sqrt(N), so the "
                  "uncapped analytic SNR gain quadruples",
     "note": "a64 is the uncapped n=64 analytic value in "
             "data/validation.npz; the paper quotes it to five places so the "
             "product is exact at the printed precision"},
    {"id": "rel-sys-subadditive-1e-5", "kind": "relation",
     "expr": "drift + streamer",
     "vars": {"drift": "derived_stats.json::systematics.arms.drift_r.6.delta_r",
              "streamer":
                  "derived_stats.json::systematics.arms.streamer_r.6.delta_r"},
     "shown": "-0.151", "digits": 3,
     "quote": "sum-of-parts $-0.151$ ($73\\%$)",
     "statement": "the sum of the two single-systematic losses at "
                  "$\\epsilon=10^{-5}$, which the joint loss undershoots",
     "note": "index 6 of the injected-eps axis is $\\epsilon=10^{-5}$"},
    {"id": "rel-sys-subadditive-1e-4", "kind": "relation",
     "expr": "drift + streamer",
     "vars": {"drift": "derived_stats.json::systematics.arms.drift_r.7.delta_r",
              "streamer":
                  "derived_stats.json::systematics.arms.streamer_r.7.delta_r"},
     "shown": "-0.565", "digits": 3,
     "quote": "$-0.285$ against $-0.565$ ($50\\%$)",
     "statement": "the same sum of parts at $\\epsilon=10^{-4}$",
     "note": "index 7 of the injected-eps axis is $\\epsilon=10^{-4}$, the "
             "decade after rel-sys-subadditive-1e-5"},
    {"id": "rel-ensemble-offset-in-map-sd", "kind": "relation",
     "expr": "offset / between",
     "vars": {"offset": "derived_stats.json::ensemble.fiducial_offset",
              "between": "derived_stats.json::ensemble.between_map_sd"},
     "shown": "1.5", "digits": 1,
     "quote": "which is $1.5\\times$ the between-map sd",
     "statement": "how far the fiducial geography sits above the ensemble "
                  "mean, measured in the spread between geography means",
     "note": "both terms come from the 5x4 truth-map ensemble reshaped by "
             "tools/derive_stats.py from ext_truth_ensemble.npz"},
    {"id": "rel-ensemble-offset-in-mc-error", "kind": "relation",
     "expr": "offset / se",
     "vars": {"offset": "derived_stats.json::ensemble.fiducial_offset",
              "se": "derived_stats.json::ensemble.overall.se"},
     "shown": "4.7", "digits": 1,
     "quote": "$4.7\\times$ the Monte-Carlo error of that mean",
     "statement": "the same offset measured against the standard error of the "
                  "20-member ensemble mean",
     "note": "hand-written over derived leaves"},
    {"id": "rel-ensemble-versus-headline", "kind": "relation",
     "expr": "headline - mean",
     "vars": {"headline": "derived_stats.json::seedtable.tdi_fiducial.mean",
              "mean": "derived_stats.json::ensemble.overall.mean"},
     "shown": "0.025", "digits": 3,
     "quote": "the ensemble mean is $0.025$ lower",
     "statement": "the ten-seed fiducial headline against the five-geography "
                  "ensemble mean",
     "note": "hand-written over derived leaves"},
]


# --------------------------------------------------------------------------- #
# hand-declared externals: numbers that are not ours to trace
# --------------------------------------------------------------------------- #
# Every printed number in the body must be explained by the ledger, by an
# archive, by a relation above, or by one of these declarations.  A new figure
# in the paper that is none of those fails the run, which is the point: the
# list is a checklist of the paper's non-results, not a filing cabinet.
EXTERNAL: dict[str, str] = {
    # calendar and unit constants
    "365.25": "the Julian year in days; a calendar constant used to convert "
              "the 87.33-day campaign into orbital phase",
    # the reproducibility contract itself
    "20,000": "the bootstrap resample count, declared in "
              "tools/derived_stats.json::method.nboot and implemented by "
              "src/expcommon.py::paired_stats",
    "1e-12": "the tolerance continuous integration re-runs the fast tier at, "
             "set in .github/workflows/verify.yml and tools/verify_flat.sh",
    # solar-physics literature values
    "4.445": "quiet-Sun Baumbert--Allen electron density at b = 1.5 R_sun, "
             "read off the literature model the sentence names",
    "4.907": "refractive blur of the image at 650 AU for that density model; "
             "an analytic propagation of the quoted constants, not a "
             "simulated result",
    "4.225": "solar flux dilution at 650 AU: (650 AU / 1 AU)^2 = 4.225e5, "
             "the square of the fiducial distance, printed in scientific "
             "notation",
    "1.0982": "the de-inclination factor as usually quoted in the literature; "
              "the paper's own value, 1.0978, comes from the preceding "
              "equation and is ledgered separately",
    # fiducial surface map: recomputed from shipped code, never archived
    "50.96": "the fiducial earthlike truth map's land-bearing coarse-pixel "
             "fraction, recomputed from the shipped generator "
             "(src/expcommon.py::truth with the frozen truth seed 7); the "
             "earthlike field is the fiducial baseline, so its per-pixel "
             "statistics are not duplicated into a parts archive",
}


def external_errors(values: dict | None = None,
                    text: str | None = None) -> list[str]:
    """Keep the declarations honest in both directions.

    A declaration is a statement that the archives cannot answer for a printed
    number, so it goes stale in two ways: the sentence is rewritten and the
    token is no longer printed (a filing cabinet with numbers nobody quotes),
    or the shipped evidence starts to cover a token that is still declared
    external (an unexplained number being waved through).  Both are errors.
    """
    values = archive_values() if values is None else values
    text = flat_manuscript() if text is None else text
    printed = {s for s, _ in manuscript_numbers(text)}
    arf = archive_forms(values)
    errors: list[str] = []
    for token in sorted(EXTERNAL):
        reason = EXTERNAL[token]
        if not isinstance(reason, str) or len(reason.split()) < 4:
            errors.append(f"external {token!r}: declared without a reason")
        if token not in printed:
            errors.append(f"external {token!r}: no longer printed in the "
                          f"manuscript, so the declaration is stale")
        elif token in arf:
            errors.append(f"external {token!r}: the shipped archives can "
                          f"already print this, so it should be ledgered "
                          f"rather than declared external")
    return errors


# --------------------------------------------------------------------------- #
# display
# --------------------------------------------------------------------------- #
def display(value, digits: int) -> str:
    """What the manuscript would print for ``value`` at ``digits`` places."""
    return f"{value:.{digits}f}"


def forms(value, digits: int) -> list[str]:
    """Every spelling of ``value`` at ``digits`` the paper might use.

    Thousands separators appear in LaTeX as ``20{,}000``, and an integral value
    below a thousand is printed without a decimal tail, so both variants are
    legitimate.  A quantity that rounds to zero is normally printed without the
    minus sign -- the paper's "$0.0000$" cells are differences of about
    $10^{-6}$, and "-0.0000" would read as an error -- so the unsigned spelling
    is offered too.
    """
    plain = display(value, digits)
    out = [plain]
    if abs(value) >= 1000:
        grouped = f"{value:,.{digits}f}"
        out += [grouped, grouped.replace(",", "{,}")]
    if float(value).is_integer() and abs(value) < 1000:
        out.append(str(int(value)))
    if plain.startswith("-") and set(plain[1:]) <= set("0."):
        out.append(plain[1:])
    return out


# how an archived quantity may be rescaled for print: 1 as-is, 100 as a
# percentage (the paper reports retained information, land fraction and
# chi^2 deficits in percent, and a percentage is still the same number)
SCALES = (1, 100)


def printable(value: float) -> list[tuple[int, int]]:
    """``(scale, digits)`` pairs worth trying, coarse to fine."""
    return [(sc, d) for sc in SCALES for d in range(0, MAX_PRECISION + 1)]


def display_of(value: float, scale: int, digits: int) -> str:
    return display(value * scale, digits)


def rounds_to(value: float, digits: int, shown: str, scale: int = 1) -> bool:
    """Does the printed string equal the archive value at that precision?"""
    needle = shown.replace("{,}", ",").replace(",", "")
    return any(needle == f.replace(",", "") for f in forms(value * scale, digits))


# --------------------------------------------------------------------------- #
# ledger I/O
# --------------------------------------------------------------------------- #
def load_ledger(path: Path = LEDGER) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "claims" not in data or not isinstance(data["claims"], list):
        raise ValueError(f"{path}: missing a 'claims' list")
    return data


def save_ledger(data: dict, path: Path = LEDGER) -> None:
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8")


# --------------------------------------------------------------------------- #
# checking
# --------------------------------------------------------------------------- #
def _num(ref, values: dict) -> float:
    """A leaf value, or the sum of a list of leaves (for a band mean)."""
    if isinstance(ref, (int, float)) and not isinstance(ref, bool):
        return float(ref)
    if isinstance(ref, list):
        return float(sum(values[r] for r in ref))
    return float(values[ref])


# --------------------------------------------------------------------------- #
# a calculator, not an eval()
# --------------------------------------------------------------------------- #
def _eval_node(node, env: dict[str, float]) -> float:
    """Evaluate one node of an arithmetic expression tree.

    Relations are written as small formulas over named archive leaves
    -- ``(collapse - fiducial) / se`` -- and a formula in a data file is
    only safe if the language reading it is arithmetic and nothing else.
    Attribute access, calls, comprehensions and names that are not bound
    are all rejected, so a corrupted ledger cannot execute anything.
    """
    import ast

    if isinstance(node, ast.Expression):
        return _eval_node(node.body, env)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("only numbers are allowed")
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in env:
            raise KeyError(f"undefined name {node.id!r}")
        return float(env[node.id])
    if isinstance(node, ast.UnaryOp):
        val = _eval_node(node.operand, env)
        if isinstance(node.op, ast.USub):
            return -val
        if isinstance(node.op, ast.UAdd):
            return val
        raise ValueError("unary operator not allowed")
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, env)
        right = _eval_node(node.right, env)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise ZeroDivisionError("division by zero in relation")
            return left / right
        if isinstance(node.op, ast.Pow):
            if abs(right) > 10:
                raise ValueError("exponent out of range")
            return left ** right
        raise ValueError("binary operator not allowed")
    raise ValueError(f"{type(node).__name__} is not arithmetic")


def evaluate(expr: str, env: dict[str, float]) -> float:
    import ast

    tree = ast.parse(expr, mode="eval")
    return _eval_node(tree, env)


def check_relation(c: dict, values: dict) -> str | None:
    """Verify a relation the manuscript asserts between archived numbers.

    A paired difference, a ratio, a t statistic -- these are the claims a
    referee checks first and the ones a byte-level archive diff never sees,
    because both sides can stay exactly right while the sentence about them
    goes wrong.
    """
    env = {}
    try:
        env = {name: _num(ref, values)
               for name, ref in c.get("vars", {}).items()}
        result = evaluate(c["expr"], env)
    except Exception as exc:  # noqa: BLE001 - report, never propagate
        return f"{c['id']}: expression {c['expr']!r} did not evaluate ({exc})"
    shown = c.get("shown", "")
    digits = int(c.get("digits", 4))
    scale = int(c.get("scale", 1))
    if shown and shown not in c.get("quote", ""):
        return f"{c['id']}: the quoted sentence no longer prints {shown!r}"
    if shown and not rounds_to(result, digits, shown, scale):
        return (f"{c['id']}: STALE RELATION -- {c['expr']} over "
                f"{c.get('vars', {})} evaluates to {result:.10g}, printed as "
                f"{display(result * scale, digits)!r}, but the manuscript "
                f"still prints {shown!r}")
    return None


def all_claims(ledger: dict) -> list[dict]:
    """The harvested ledger plus the hand-written relations it cannot infer."""
    return list(ledger["claims"]) + RELATIONS


def schema_errors(c: dict) -> list[str]:
    """Structural checks on one ledger entry."""
    out = []
    kind = c.get("kind")
    for req in ("id", "kind", "quote", "note"):
        if req not in c:
            out.append(f"{c.get('id', '?')}: entry has no {req!r}")
    if kind not in KINDS:
        out.append(f"{c.get('id', '?')}: kind {kind!r} is not one of "
                   f"{sorted(KINDS)}")
        return out
    if kind == "relation":
        for req in ("expr", "vars", "statement", "shown", "digits"):
            if req not in c:
                out.append(f"{c['id']}: relation has no {req!r}")
        if not isinstance(c.get("vars"), dict):
            out.append(f"{c['id']}: relation 'vars' must map names to archive "
                       "references or literals")
        for name, ref in (c.get("vars") or {}).items():
            if not name.isidentifier():
                out.append(f"{c['id']}: relation variable {name!r} is not a "
                           "usable name")
        for req in ("src", "key"):
            if req in c:
                out.append(f"{c['id']}: relation must not carry {req!r}")
    else:
        for req in ("src", "key", "digits", "shown"):
            if req not in c:
                out.append(f"{c['id']}: {kind} has no {req!r}")
        if not 0 <= int(c.get("digits", 0)) <= MAX_PRECISION:
            out.append(f"{c['id']}: digits out of range")
        if int(c.get("scale", 1)) not in SCALES:
            out.append(f"{c['id']}: scale {c.get('scale')} is not printable")
    if len(c.get("quote", "")) < 8:
        out.append(f"{c['id']}: quote is too short to identify a sentence")
    return out


def check_ledger(ledger: dict, values: dict | None = None,
                 text: str | None = None) -> list[str]:
    values = archive_values() if values is None else values
    text = flat_manuscript() if text is None else text
    errors: list[str] = []
    seen: set[str] = set()
    for c in all_claims(ledger):
        cid = c.get("id", "<missing id>")
        if cid in seen:
            errors.append(f"{cid}: duplicate ledger id")
        seen.add(cid)
        errors += schema_errors(c)
        quote = c.get("quote", "")
        if quote not in text:
            errors.append(f"{cid}: quote is no longer verbatim in the manuscript")
            continue
        if c.get("kind") == "relation":
            err = check_relation(c, values)
            if err:
                errors.append(err)
            continue
        if c.get("kind") not in ("value", "count"):
            errors.append(f"{cid}: unknown kind {c.get('kind')!r}")
            continue
        ref = f"{c['src']}::{c['key']}"
        if ref not in values:
            errors.append(f"{cid}: archive reference {ref} does not exist")
            continue
        val = values[ref]
        shown = c.get("shown", "")
        if shown not in quote:
            errors.append(
                f"{cid}: the quoted sentence no longer prints {shown!r}")
            continue
        if not rounds_to(val, c["digits"], shown, c.get("scale", 1)):
            errors.append(
                f"{cid}: STALE NUMBER -- {ref} now holds {val!r}, which is "
                f"{display(val * c.get('scale', 1), c['digits'])} at "
                f"{c['digits']} places, but the manuscript still prints "
                f"{shown!r}")
    errors += external_errors(values, text)
    return errors


# --------------------------------------------------------------------------- #
# harvesting
# --------------------------------------------------------------------------- #
def _window(text: str, pos: int, length: int) -> str:
    """A quote around the match, snapped to spaces and shrunk to fit."""
    lo, hi = pos, pos + length
    for _ in range(10):
        a = text.rfind(" ", max(0, lo - 46), lo)
        b = text.find(" ", hi, min(len(text), hi + 46))
        a = 0 if a < 0 else a + 1
        b = len(text) if b < 0 else b
        candidate = text[a:b]
        if text.count(candidate) == 1 and len(candidate) >= length + 6:
            return candidate
        lo, hi = a, b
    return text[max(0, pos - 40): pos + length + 40]


def harvest(values: dict | None = None) -> dict:
    """Build a ledger by matching distinctive archive numbers to the text.

    For every scalar leaf of the archives, the first display precision that
    yields a string of at least ``MIN_STR_LEN`` characters is used; a string
    that occurs in the manuscript too often for its length (``hit_limit``) is
    too generic to vouch for one particular key, and one that never occurs is
    simply not reported.  Ties are broken towards the shorter key path -- the
    headline number rather than a per-element index -- and every alternative
    source is recorded in ``note`` so a human reviewer can see what is
    ambiguous.
    """
    values = archive_values() if values is None else values
    text = flat_manuscript()
    toks = token_index(text)

    # string -> every archive leaf that prints as it, at every precision
    pool: dict[str, list[tuple[str, int, int, int]]] = {}
    for ref, val in values.items():
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            continue
        for scale, digits in printable(val):
            for s in forms(val * scale, digits):
                if len(s) < MIN_STR_LEN:
                    continue
                pos = toks.get(s)
                if not pos or len(pos) > hit_limit(s):
                    continue
                entry = (ref, digits, scale, len(pos))
                if entry not in pool.setdefault(s, []):
                    pool[s].append(entry)

    claims: list[dict] = []
    claimed: set[str] = set()
    for s, hits in sorted(pool.items(), key=lambda kv: (-len(kv[0]), kv[0])):
        if s in claimed:
            continue
        # a printed prefix of a number already vouched for adds no provenance
        if any(s in c for c in claimed):
            continue
        # prefer the plain value over its percent spelling, then the shorter ref
        hits = sorted(hits, key=lambda h: (h[2], len(h[0]), h[0]))
        ref, digits, scale, _n = hits[0]
        src, _, key = ref.partition("::")
        val = values[ref]
        pos = toks[s][0]
        quote = _window(text, pos, len(s))
        if s not in quote:
            continue
        claimed.add(s)
        note = "harvested"
        if scale == 100:
            note += "; printed as a percentage"
        if len(hits) > 1:
            note += "; also matches " + ", ".join(
                f"{r}@{d}" for r, d, _s, _c in hits[1:3])
        claims.append({
            "id": re.sub(r"[^a-z0-9]+", "-",
                         f"{src.rsplit('.', 1)[0]}-{key}").strip("-")[:88],
            "kind": "count" if float(val).is_integer() and scale == 1 else "value",
            "quote": quote,
            "shown": s,
            "src": src,
            "key": key,
            "digits": digits,
            "scale": scale,
            "note": note,
        })
    claims.sort(key=lambda c: c["id"])
    # ids must be unique even when two leaves of the same archive share a path
    taken: dict[str, int] = {}
    for c in claims:
        base = c["id"]
        if base in taken:
            taken[base] += 1
            c["id"] = f"{base}--{taken[base]}"
        else:
            taken[base] = 0
    return {"generated_by": "python3 tools/claims.py --harvest",
            "comment": "Numeric provenance ledger for paper/main.tex.  "
                       "Regenerate with --harvest; CI verifies with --check "
                       "and never regenerates, so a stale number fails rather "
                       "than silently re-deriving itself.",
            "claims": claims}


# --------------------------------------------------------------------------- #
# coverage: which manuscript numbers does the ledger vouch for?
# --------------------------------------------------------------------------- #
# Bookkeeping macros whose arguments are not reported numbers.  \\caption is
# deliberately absent: a caption carries results, and hiding them from the
# coverage count would flatter the ledger.
MACRO_RE = re.compile(
    r"\\(?:label|ref|eqref|cit[ae][a-z]*|cite[a-z]*|input|usepackage|setlength|"
    r"hspace|vspace|arxiv|newcommand|texttt|includegraphics)\s*"
    r"(?:\[[^\]]*\])?\s*\{[^{}]*\}")


def manuscript_numbers(text: str | None = None) -> list[tuple[str, int]]:
    """Numeric tokens in the manuscript that look like reported results.

    LaTeX bookkeeping (\\label, \\ref, citations, graphics paths, lengths) is
    stripped first, then years and small integers are dropped, because neither
    is a number a referee would ask to see traced to an archive.
    """
    text = flat_manuscript() if text is None else text
    stripped = text
    for _ in range(4):
        before = stripped
        stripped = MACRO_RE.sub(" ", stripped)
        if before == stripped:
            break
    out = []
    for s, start in iter_numbers(stripped):
        if s.count(".") == 0 and len(s.lstrip("-").replace(",", "")) <= 2:
            continue                      # small ints: prose counters
        if re.fullmatch(r"(19|20)\d\d", s):
            continue                      # years
        out.append((s, start))
    return out


def archive_forms(values: dict) -> set[str]:
    """Every number the shipped archives could print, at any useful precision.

    A manuscript number that has an archive spelling but no ledger entry is
    not a defect -- it is simply a value the ledger never chose to vouch for,
    usually because it is generic ("0.20" appears in nine places).  A number
    with NO archive spelling is the interesting case: it did not come from the
    shipped data.
    """
    out: set[str] = set()
    for val in values.values():
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            continue
        for scale, digits in printable(val):
            for s in forms(val * scale, digits):
                if len(s) >= MIN_STR_LEN:
                    out.add(s)
    return out


def coverage(ledger: dict, values: dict | None = None,
             text: str | None = None) -> dict:
    """How much of the manuscript the ledger can vouch for.

    Each printed number of the body is sorted into four buckets:

    ``ledgered``     some claim names this exact string and cites an archive
    ``archival``     the string is a possible spelling of an archive leaf but
                     no claim vouches for it (generic or ambiguous value)
    ``external``     declared in the ledger's ``external`` block, with a
                     reason -- a literature constant, a design choice, a
                     derived geometric quantity
    ``unexplained``  none of the above: the paper prints a number whose
                     origin nobody has recorded
    """
    values = archive_values() if values is None else values
    text = flat_manuscript() if text is None else text
    claimed = set()
    for c in all_claims(ledger):
        s = c.get("shown", "")
        if s:
            claimed |= {s, s.replace("{,}", ","), s.replace(",", "{,}")}
    declared = set(EXTERNAL)
    declared |= {e["value"] for e in ledger.get("external", [])}
    arf = archive_forms(values)
    numbers = manuscript_numbers(text)
    buckets = {"ledgered": 0, "archival": 0, "external": 0, "unexplained": 0}
    unexplained: list[str] = []
    for s, _pos in numbers:
        if s in claimed:
            buckets["ledgered"] += 1
        elif len(s) < MIN_STR_LEN:
            buckets["archival"] += 1      # too short to name one leaf
        elif s in declared:
            buckets["external"] += 1
        elif s in arf:
            buckets["archival"] += 1
        else:
            buckets["unexplained"] += 1
            unexplained.append(s)
    total = len(numbers)
    return {"claims": len(all_claims(ledger)),
            "external": len(declared),
            "distinct-unexplained": len(set(unexplained)),
            "numbers": total,
            "traceable": buckets["ledgered"],
            "untraceable": buckets["unexplained"],
            "buckets": buckets,
            "pct": 100.0 * buckets["ledgered"] / total if total else 0.0,
            "untraceable_list": unexplained}


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #
def describe(c: dict) -> str:
    """One-line description of where a claim's number comes from."""
    if c.get("kind") == "relation":
        return " + ".join(f"{k}={v}" for k, v in c["vars"].items()) + \
            f"  =>  {c['expr']}"
    return f"{c['src']}::{c['key']}"


def report(ledger: dict, values: dict) -> str:
    lines = [f"{'id':<44} {'kind':<9} {'archive reference':<52} "
             f"{'shown':>12}  quote"]
    for c in all_claims(ledger):
        ref = describe(c)
        raw = values.get(f"{c.get('src', '')}::{c.get('key', '')}")
        current = "" if raw is None else f" (archive {raw:.10g})"
        lines.append(f"{c['id']:<44} {c['kind']:<9} {ref:<52} "
                     f"{c['shown']:>12}  {c['quote'][:48]}{current}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify the ledger")
    ap.add_argument("--harvest", action="store_true",
                    help="rewrite the ledger from the current archives/text")
    ap.add_argument("--report", action="store_true", help="print the ledger")
    ap.add_argument("--coverage", action="store_true",
                    help="print traceability counters")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--min-claims", type=int, default=0)
    ap.add_argument("--max-untraceable", type=int, default=10 ** 9)
    ap.add_argument("--no-npz", action="store_true",
                    help="index results/*.json only, skipping scalar .npz arrays")
    args = ap.parse_args(argv)

    values = archive_values(with_npz=not args.no_npz)
    text = flat_manuscript()

    if args.harvest:
        data = harvest(values)
        save_ledger(data)
        errs = check_ledger(data, values, text)
        print(f"harvested {len(data['claims'])} claims -> {LEDGER.relative_to(ROOT)}")
        print(f"re-check: {len(errs)} failures")
        for e in errs[:20]:
            print("  -", e)
        return 1 if errs else 0

    ledger = load_ledger()

    if args.report:
        print(report(ledger, values))
        return 0

    if args.coverage:
        cov = coverage(ledger, values, text)
        if args.json:
            print(json.dumps({k: v for k, v in cov.items()
                              if k != "untraceable_list"}))
        else:
            b = cov["buckets"]
            print(f"ledger claims:   {cov['claims']}")
            print(f"result-like numbers in the manuscript: {cov['numbers']}")
            print(f"vouched for by an archive: {cov['traceable']} "
                  f"({cov['pct']:.1f}%)")
            print(f"archival spelling, no claim: {b['archival']}")
            print(f"declared external: {b['external']} "
                  f"({cov['external']} declarations)")
            print(f"untraceable: {cov['untraceable']}")
            for s in sorted(set(cov["untraceable_list"]))[:20]:
                print(f"  - {s}")
        rc = 0
        if cov["claims"] < args.min_claims:
            print(f"FAIL: ledger has {cov['claims']} claims, floor is {args.min_claims}")
            rc = 1
        if cov["untraceable"] > args.max_untraceable:
            print(f"FAIL: {cov['untraceable']} untraceable numbers, ceiling is "
                  f"{args.max_untraceable}")
            rc = 1
        return rc

    errs = check_ledger(ledger, values, text)
    cov = coverage(ledger, values, text)
    if args.json:
        print(json.dumps({"claims": cov["claims"], "failures": errs,
                          "traceable_pct": round(cov["pct"], 2)}))
    elif errs:
        print(f"ledger: {len(errs)} of {cov['claims']} claims do NOT trace:")
        for e in errs[:40]:
            print("  -", e)
    else:
        print(f"ledger: {cov['claims']} claims, all tracing to results/ "
              f"({cov['traceable']}/{cov['numbers']} result-like numbers "
              f"vouched for, {cov['pct']:.1f}%)")
    rc = 1 if errs else 0
    if cov["claims"] < args.min_claims:
        print(f"FAIL: ledger below the {args.min_claims}-claim floor")
        rc = 1
    if cov["untraceable"] > args.max_untraceable:
        print(f"FAIL: {cov['untraceable']} untraceable numbers above the "
              f"{args.max_untraceable} ceiling")
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())

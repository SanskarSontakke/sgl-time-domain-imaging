#!/usr/bin/env python3
"""doc_numbers.py -- audit the counts the documentation makes about this repository.

The manuscript has three proof layers already.  ``tools/derive_stats.py`` reduces
the shipped archives to a fixed census of deterministic statistics (run
``--show-facts`` for what the tree currently says -- a count typed into this
docstring would be one more number to audit); ``tools/claims.py`` vouches for
every number *printed in the paper* against them; and
``tools/manuscript_outline.py`` proves that the document's own structure -- page,
figure, table, equation and reference counts, section order, cross-references --
is what the build says it is.  None of those three covers the prose *around* the
paper: the README's "36 pages, 9 figures, 16 tables", its table of what each
proof layer currently reports, ``tests/README.md``'s per-module count table, the
archive census in its data-dependency list, the stage counts in Appendix D, the
CI comment's audit-leaf and stored-array denominators.  Those are checkable
claims too, and they rot exactly the way a stale PDF rots: silently, and one
refactor later.

This module is the documentation half of the build-and-test loop, the equivalent
of snapshot-testing a static site.  It has three parts:

1. ``facts()`` computes each quantity from the tree itself -- a pytest
   collection, an AST walk over ``tests/``, ``np.load`` over ``results/``, a
   JSON parse of the ledger.  Nothing here is typed in by hand, so the tool
   cannot agree with a document that has drifted.
2. ``CLAIMS`` is the registry: every documented sentence that states one of those
   quantities, as a pattern plus the facts it must equal.  A pattern that stops
   matching is itself a finding -- deleting a claim is not a way of passing this
   gate.
3. ``scan()`` returns findings, one per broken claim, and ``main()`` turns that
   into an exit code for ``tools/verify_numbers.sh`` and for continuous
   integration.  Two extras stop the registry itself from being the weak link: a
   measured fact that no document states is a finding (``--allow-unstated`` turns
   it back into a note), and the README's row for this tool is compared with the
   report this run actually produced.

Two deliberate limits.  Counts of *history* are not audited: ``reviews/``
describes revision v3 as "13 tables, 8 figures, 24 pages", which was true of that
draft and must stay true of it, so every pattern here is anchored to the words
that make it a present-tense claim ("currently", "the default fast tier").
And timings are not audited at all -- "~1.5 s" depends on the machine, and a gate
that fails on a slow laptop teaches people to ignore it.

Usage:
    python3 tools/doc_numbers.py                 # human report, exit 1 on findings
    python3 tools/doc_numbers.py --json          # machine-readable
    python3 tools/doc_numbers.py --show-facts    # what the tree currently says
    python3 tools/doc_numbers.py --allow-unstated # report, not fail, unclaimed facts
    python3 tools/doc_numbers.py --min-claims 40 # refuse a silently emptied audit
"""
from __future__ import annotations

import argparse
import ast
import collections
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --------------------------------------------------------------------------- #
# fact computation
# --------------------------------------------------------------------------- #
# Every fact is a function of the tree, with no hand-written numbers anywhere.
# They are grouped so a failure names the measurement that broke, not a file
# full of regexes.

TEST_DIR = ROOT / "tests"
NAMED_MODULE = re.compile(r"^(test_\w+)\.py$")


def _test_functions() -> dict[str, int]:
    """``def test_*`` per module, by syntax rather than by running pytest.

    The distinction matters: one function can collect four parametrised checks,
    and the documentation states both numbers.  An AST walk counts what a reader
    would call a test; ``--collect-only`` counts what pytest runs.
    """
    out = {}
    for path in sorted(TEST_DIR.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        out[path.name] = sum(1 for node in ast.walk(tree)
                             if isinstance(node, ast.FunctionDef)
                             and node.name.startswith("test_"))
    return out


def _collect(extra: tuple[str, ...] = ()) -> dict[str, int]:
    """Per-module collection counts, from pytest itself.

    ``-q`` prints one node id per check, which is both the cheapest and the
    least ambiguous way to count them: the human-readable tail of the same
    output says "583 tests collected" in one case and "21/583 tests collected
    (562 deselected)" in the other, so the summary line cannot be parsed with one
    pattern.  Summing the node ids avoids that, and the totals fall out.
    """
    cmd = [sys.executable, "-m", "pytest", str(TEST_DIR), "--collect-only",
           "-q", "-p", "no:cacheprovider", *extra]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if proc.returncode not in (0, 5):
        raise RuntimeError(
            f"pytest --collect-only {' '.join(extra)} exited "
            f"{proc.returncode}: {(proc.stderr or proc.stdout)[-400:]}")
    counts: dict[str, int] = collections.Counter()
    for line in proc.stdout.splitlines():
        m = re.match(r"(?:.*?[\\/])?(test_\w+\.py)::", line)
        if m:
            counts[m.group(1)] += 1
    return dict(counts)


def _counts() -> dict:
    """The suite census: functions, checks, and the two tiers."""
    all_checks = _collect()
    slow = _collect(("-m", "slow"))
    fast = _collect(("-m", "not slow"))
    functions = _test_functions()
    return {
        "test.functions": sum(functions.values()),
        "checks.collected": sum(all_checks.values()),
        "checks.fast": sum(fast.values()),
        "checks.slow": sum(slow.values()),
        "test.functions.per_module": functions,
        "checks.per_module": all_checks,
        "checks.slow.per_module": slow,
    }


def _archives() -> dict:
    """The shipped-results census the test suite's data-dependency list states."""
    res = ROOT / "results"
    npz = sorted(p.name for p in res.glob("*.npz"))
    js = sorted(p.name for p in res.glob("*.json"))
    return {
        "results.npz": len(npz),
        "results.json": len(js),
        "results.parts": len(list((res / "parts").glob("*.npz"))),
        "results.ext": sum(1 for n in npz if n.startswith("ext_")),
        "results.ext.json": sum(1 for n in js if n.startswith("ext_")),
        "ext.modules": sum(1 for p in (ROOT / "src" / "ext").glob("*.py")
                           if p.name not in ("__init__.py", "extcommon.py")),
    }


def _arrays() -> dict:
    """Stored arrays and audit leaves, which is what the CI tolerance note claims.

    ``.github/workflows/verify.yml`` says the fast tier differs from the shipped
    archives "on 5 of 2,987 audit leaves and 5 of 639 stored arrays".  Those two
    denominators are properties of the tree, so they are counted rather than
    remembered; a re-run that changes them changes the meaning of the tolerance.
    """
    import numpy as np

    total = 0
    for path in sorted((ROOT / "results").glob("*.npz")):
        with np.load(path, allow_pickle=False) as handle:
            total += len(handle.files)

    def leaves(node) -> int:
        if isinstance(node, dict):
            return sum(leaves(v) for v in node.values())
        if isinstance(node, list):
            return sum(leaves(v) for v in node)
        return 1

    audit = json.loads((ROOT / "results" / "audit.json").read_text(encoding="utf-8"))
    return {"results.stored_arrays": total, "results.audit_leaves": leaves(audit)}


def _stages() -> dict:
    """The reproduction driver's registry, straight from ``reproduce_all``."""
    import reproduce_all

    return {
        "stages.fast": len(reproduce_all.FAST_STAGES),
        "stages.full": len(reproduce_all.full_stages()),
        "run_experiments.subcommands": sum(
            1 for node in ast.walk(ast.parse(
                (ROOT / "src" / "run_experiments.py").read_text(encoding="utf-8")))
            if isinstance(node, ast.FunctionDef) and node.name.startswith("cmd_")),
    }


def _proof_layers() -> dict:
    """What the other gates say, so this one can check that they were written down.

    ``derived_stats.json`` stores its statistics in six named families rather than
    one flat map, so the census is of leaves; ``claims_ledger.json`` carries only
    the harvested claims, because the arithmetic relations are code, not data --
    they are read from ``claims.RELATIONS`` so that deleting one is a finding here
    rather than a silent shrinkage.
    """
    import claims as CL
    import manuscript_outline as mo

    ledger = json.loads((ROOT / "tools" / "claims_ledger.json").read_text(encoding="utf-8"))
    stats = json.loads((ROOT / "tools" / "derived_stats.json").read_text(encoding="utf-8"))

    def leaves(node) -> int:
        if isinstance(node, dict):
            return sum(leaves(v) for v in node.values())
        if isinstance(node, list):
            return sum(leaves(v) for v in node)
        return 1

    n_claims, n_relations = len(ledger["claims"]), len(CL.RELATIONS)
    cov = CL.coverage(ledger, CL.archive_values())
    return {
        "manuscript.pages": mo.DOCUMENTED["pages"],
        "manuscript.figures": mo.DOCUMENTED["figures"],
        "manuscript.tables": mo.DOCUMENTED["tables"],
        "manuscript.bibitems": mo.DOCUMENTED["bibitems"],
        "manuscript.equations": mo.DOCUMENTED["equations"],
        "manuscript.appendices": mo.DOCUMENTED["appendices"],
        "ledger.claims": n_claims,
        "ledger.relations": n_relations,
        "ledger.entries": n_claims + n_relations,
        "ledger.examined": cov["numbers"],
        "ledger.unexplained": cov["buckets"]["unexplained"],
        "stats.derived": leaves(stats["stats"]),
        "stats.families": len(stats["stats"]),
    }


_FACTS: dict | None = None


def facts(refresh: bool = False) -> dict:
    """Every audited quantity, computed from the tree.  Cached: a pytest
    collection costs about a third of a second and the suite calls this once."""
    global _FACTS
    if _FACTS is None or refresh:
        blob: dict = {}
        for part in (_counts, _archives, _arrays, _stages, _proof_layers):
            blob.update(part())
        _FACTS = blob
    return _FACTS


# --------------------------------------------------------------------------- #
# the registry of documented claims
# --------------------------------------------------------------------------- #
# ``groups`` lines up capture groups with fact keys; a group named after a module
# list ("checks.per_module[test_latex_integrity.py]") indexes the dict facts.
# ``at_least`` is how many matches the file must contain, so a claim cannot be
# removed to avoid being contradicted.
class Claim:
    def __init__(self, rule: str, file: str, pattern: str, groups: tuple,
                 note: str, at_least: int = 1, flags: int = 0):
        self.rule = rule
        self.file = file
        self.pattern = pattern
        self.groups = groups
        self.note = note
        self.at_least = at_least
        self.flags = flags

    def regex(self) -> re.Pattern:
        return re.compile(self.pattern, self.flags)


def _fact(name: str, table: dict) -> int:
    """Resolve a possibly module-indexed fact key to a number."""
    if "[" in name:
        key, _, rest = name.partition("[")
        rest = rest.rstrip("]")
        value = table[key].get(rest)
        if value is None:
            raise KeyError(f"{key} has no entry {rest!r}")
        return value
    return table[name]


CLAIMS: list[Claim] = [
    # ---- README.md: what the artifact is ------------------------------ #
    Claim("readme.shape", "README.md",
          r"(\d+) pages, (\d+) figures, (\d+) tables, (\d+) references",
          ("manuscript.pages", "manuscript.figures", "manuscript.tables",
           "manuscript.bibitems"),
          "the one-line description of the manuscript a reader sees first"),
    Claim("readme.extensions", "README.md",
          r"regeneration of the (\d+) extension archives",
          ("results.ext",),
          "tools/run_ext_full.sh is described by the archive count it regenerates"),
    Claim("readme.ext.driver", "README.md",
          r"--ext\s+# plus the (\d+) extension modules",
          ("results.ext",),
          "the driver's --ext flag is documented as running this many modules"),

    # ---- README.md: the proof-layer table, which quotes the other gates -- #
    Claim("readme.proof.stats", "README.md",
          r"(\d+) statistics in (\d+) families, in `tools/derived_stats\.json`",
          ("stats.derived", "stats.families"),
          "the reduce step reports its own census, so it must match the file"),
    Claim("readme.proof.ledger", "README.md",
          r"(\d+) ledger entries, of which (\d+) are harvested claims and "
          r"(\d+) are prose arithmetic",
          ("ledger.entries", "ledger.claims", "ledger.relations"),
          "the vouching step's size is two counts plus their sum"),
    Claim("readme.proof.coverage", "README.md",
          r"(\d+) printed numbers examined, (\d+) unexplained",
          ("ledger.examined", "ledger.unexplained"),
          "the paper's number census, which the strict gate holds at zero"),
    Claim("readme.proof.shape", "README.md",
          r"(\d+) pages, (\d+) figures, (\d+) tables, (\d+) references, "
          r"(\d+) numbered equations, (\d+) appendices",
          ("manuscript.pages", "manuscript.figures", "manuscript.tables",
           "manuscript.bibitems", "manuscript.equations",
           "manuscript.appendices"),
          "the structural row restates the whole document shape, including the "
          "counts the one-line description leaves out"),

    # ---- tests/README.md: the suite census ---------------------------- #
    Claim("tests.total", "tests/README.md",
          r"\*\*Total: (\d+) test functions, (\d+) collected checks\*\* "
          r"\((\d+) in the default fast\s*\ntier, (\d+) marked",
          ("test.functions", "checks.collected", "checks.fast", "checks.slow"),
          "the headline census of the whole suite"),
    Claim("tests.exclude", "tests/README.md",
          r"Exclude slow tests \(default CI tier; (\d+) of (\d+) checks\)",
          ("checks.fast", "checks.collected"),
          "the command section repeats both tiers"),
    Claim("tests.slow.only", "tests/README.md",
          r"Slow tier only \(the (\d+) end-to-end re-simulation checks\)",
          ("checks.slow",),
          "the slow tier is described by its size"),
    Claim("tests.tier.fast", "tests/README.md",
          r"\*\*Fast \(default\)\*\*: (\d+) checks\.",
          ("checks.fast",),
          "the tier definition repeats the fast count"),
    Claim("tests.tier.slow", "tests/README.md",
          r"\*\*Slow \(> 5s\)\*\*: (\d+) checks marked",
          ("checks.slow",),
          "the slow tier's own definition"),
    Claim("tests.tier.split", "tests/README.md",
          r"(\d+) in\s*\n\s*`test_pipeline_live\.py`",
          ("checks.per_module[test_pipeline_live.py]",),
          "which module the slow checks live in, and how many"),
    Claim("tests.tier.split2", "tests/README.md",
          r"and (\d+) in `test_reproduce_entrypoint\.py`",
          ("checks.slow.per_module[test_reproduce_entrypoint.py]",),
          "the other half of the slow tier"),
    Claim("tests.run.fast", "tests/README.md",
          r'\*\*Fast tier\*\* \(`-m "not slow"`, (\d+) checks\)',
          ("checks.fast",),
          "the runtime table repeats the tier size"),
    Claim("tests.run.slow", "tests/README.md",
          r"\*\*Slow tier\*\* \(`-m slow`, (\d+) checks\)",
          ("checks.slow",),
          "the runtime table's slow row"),
    Claim("tests.data.npz", "tests/README.md",
          r"`results/\*\.npz` \((\d+) shipped archives, (\d+) of them",
          ("results.npz", "results.ext"),
          "the data dependency the fast tier reads"),
    Claim("tests.data.json", "tests/README.md",
          r"`results/\*\.json` \((\d+) headline files",
          ("results.json",),
          "the headline JSON census, the shorter half of the archive inventory"),
    Claim("tests.data.extjson", "tests/README.md",
          r"all (\d+) `ext_\*` archives ship an",
          ("results.ext.json",),
          "the npz/json pairing claim for extensions"),
    Claim("tests.data.parts", "tests/README.md",
          r"`results/parts/\*\.npz` \((\d+) checkpoint files\)",
          ("results.parts",),
          "checkpoint census, the denominator of the flatten step"),
    Claim("tests.modules.ext", "tests/README.md",
          r"Contract for the (\d+) computed extensions in `src/ext/`",
          ("ext.modules",),
          "the extension-archive contract row"),
    Claim("tests.modules.stages", "tests/README.md",
          r"stage registry \((\d+) fast / (\d+) full\)",
          ("stages.fast", "stages.full"),
          "the driver row states both registry sizes"),
    Claim("tests.config.pytest", "tests/README.md",
          r"`pytest\.ini`: Defines the `slow` marker and test paths",
          (),
          "the suite documents a configuration file, so it must exist"),
    Claim("tests.markers", "tests/README.md",
          r"(\d+) checks marked `@pytest\.mark\.slow`",
          ("checks.slow",),
          "the marker is claimed to be what makes the tier"),

    # ---- the manuscript's own appendix --------------------------------- #
    Claim("paper.suite", "paper/main.tex",
          r"The pytest suite \((\d+) test functions, (\d+) collected\s*\n"
          r"checks, (\d+) of them in the default fast tier\)",
          ("test.functions", "checks.collected", "checks.fast"),
          "Appendix D tells the reader how the claims are checked"),
    Claim("paper.modes.fast", "paper/main.tex",
          r"\{\\tt --fast\} & (\d+) &",
          ("stages.fast",),
          "Table of reproduction modes: the fast tier's stage count"),
    Claim("paper.modes.full", "paper/main.tex",
          r"\{\\tt --full\} & (\d+) &",
          ("stages.full",),
          "Table of reproduction modes: the full tier's stage count"),
    Claim("paper.modes.ext", "paper/main.tex",
          r"\{\\tt --fast --ext\} & (\d+)\\,\+\\,(\d+) &",
          ("stages.fast", "results.ext"),
          "the --ext row is the fast tier plus the extension modules"),
    Claim("paper.entrypoints", "paper/main.tex",
          r"whose (\d+) subcommands each",
          ("run_experiments.subcommands",),
          "the generation side is described by its subcommand count"),
    Claim("paper.arrays", "paper/main.tex",
          r"relative, on 5 of (\d+) stored arrays",
          ("results.stored_arrays",),
          "the tolerance claim has a denominator"),
    Claim("paper.gates.ext", "paper/main.tex",
          r"the presence\s*\nof all (\d+) extension archives",
          ("results.ext",),
          "gate G-4 is described by the archive census it enforces"),

    # ---- CI and the tools it runs -------------------------------------- #
    Claim("ci.denominators", ".github/workflows/verify.yml",
          r"\d+ of ([\d,]+) audit leaves and \d+ of ([\d,]+) stored arrays",
          ("results.audit_leaves", "results.stored_arrays"),
          "the tolerance comment's denominators are properties of the tree; the "
          "numerators are what one runner measured and are not audited"),

    # ---- the referee response ------------------------------------------ #
    Claim("response.shape", "reviews/response_to_editor.md",
          r"currently (\d+) pages, (\d+)\s*\nfigures, (\d+) tables, (\d+) numbered equations",
          ("manuscript.pages", "manuscript.figures", "manuscript.tables",
           "manuscript.equations"),
          "the letter to the editor states the manuscript's shape"),

    # ---- the demo app -------------------------------------------------- #
    Claim("app.pages", "components/*.tsx",
          r"(\d+) pages, OJA two-column format",
          ("manuscript.pages",),
          "the public demo advertises the same page count as the paper"),
]

# Files the app claim fans out over; everything else is a single path.
APP_GLOB = "components/*.tsx"


# --------------------------------------------------------------------------- #
# the workflow's own self-consistency
# --------------------------------------------------------------------------- #
# Continuous integration is documentation too: a ceiling in a comment, a marker
# expression that silently selects nothing, a job that builds in the checkout.
# These are read structurally rather than as prose claims, because the point is
# that the file's settings agree with the sentences about them.
WORKFLOW = ".github/workflows/verify.yml"
JOB_RE = re.compile(r"^  (\w[\w-]*):\s*$", re.M)


def _job_blocks(text: str) -> dict[str, str]:
    """Split a GitHub workflow into its job bodies, by indentation.

    Only the part below the ``jobs:`` key is considered: ``on:`` and
    ``permissions:`` use the same two-space indentation for their own keys, and a
    job called ``push`` would be a misreading, not a finding.
    """
    body = text[text.index("\njobs:"):] if "\njobs:" in text else text
    marks = [(m.group(1), m.start()) for m in JOB_RE.finditer(body)]
    out = {}
    for i, (name, start) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(body)
        out[name] = body[start:end]
    return out


def audit_workflow(findings: list[str]) -> dict:
    """Check the workflow against the claims it makes about itself."""
    text = _read(WORKFLOW)
    if text is None:
        findings.append(f"[ci.present] {WORKFLOW} is missing")
        return {}
    jobs = _job_blocks(text)
    ceilings = {}
    for name, body in jobs.items():
        m = re.search(r"timeout-minutes: *(\d+)", body)
        if not m:
            findings.append(f"[ci.timeout] job {name!r} has no timeout-minutes, "
                            f"so it inherits the six-hour default and a hung "
                            f"step is a red tick three hours later")
            continue
        if int(m.group(1)) < 10:
            findings.append(f"[ci.timeout] job {name!r} has a "
                            f"{m.group(1)}-minute ceiling; the manuscript build "
                            f"needs a TeX Live install, which is not a ten-minute "
                            f"job")
        ceilings[name] = int(m.group(1))
    quoted = re.search(r"the paper job has (\d+) minutes", text)
    if not quoted:
        findings.append("[ci.timeout] the paper job's ceiling is no longer "
                        "stated where it is set; the comment is what makes the "
                        "number a decision rather than a guess")
    elif "paper" in ceilings and int(quoted.group(1)) != ceilings["paper"]:
        findings.append(f"[ci.timeout] the comment says the paper job has "
                        f"{quoted.group(1)} minutes but the job asks for "
                        f"{ceilings['paper']}")
    if "cancel-in-progress: true" not in text:
        findings.append("[ci.concurrency] no cancel-in-progress: a series of "
                        "pushes queues several identical TeX Live installs")
    gates = jobs.get("gates", "")
    if '-m "not slow"' not in gates:
        findings.append("[ci.tier] the gates job does not deselect the slow "
                        "tier, so CI would re-run the simulation")
    if "--strict-markers" not in gates:
        findings.append("[ci.tier] the gates job runs pytest without "
                        "--strict-markers, so an unregistered marker is a "
                        "warning rather than an error")
    paper = jobs.get("paper", "")
    if "make_app_docs.py --check" not in paper:
        findings.append("[ci.mirrors] the paper job no longer checks the "
                        "document mirrors")
    elif paper.index("make_app_docs.py --check") > paper.index("check_pdf_build.sh"):
        findings.append("[ci.mirrors] the mirror check runs after the build, so "
                        "it compares a working tree the job already recompiled")
    if re.search(r"^\s*latexmk ", paper, re.M):
        findings.append("[ci.scratch] the paper job compiles in the checkout; "
                        "pdfTeX stamps a creation date, which breaks the byte "
                        "mirror gate on a rebuild that proved nothing")
    # apt is the only step in the job that depends on a package mirror, so it is
    # the only step that can hang.  An uncapped hang spends the whole job ceiling
    # and the job reports that it ran out of time rather than what stalled.
    install = re.search(r"- name: Install TeX Live\n([\s\S]*?)(?=\n      - )", paper)
    if not install:
        findings.append("[ci.install] the paper job has no Install TeX Live step "
                        "this audit can read, so the one step that can hang is "
                        "no longer watched")
    else:
        block = install.group(1)
        cap = re.search(r"timeout-minutes: *(\d+)", block)
        if not cap:
            findings.append("[ci.install] the TeX Live install step is uncapped; "
                            "a stalled mirror then spends the whole job ceiling "
                            "before the job can name what hung")
        elif "paper" in ceilings and int(cap.group(1)) >= ceilings["paper"]:
            findings.append(f"[ci.install] the install step's {cap.group(1)}-minute "
                            f"cap is not below the paper job's "
                            f"{ceilings['paper']}-minute ceiling, so it caps "
                            f"nothing")
        if cap and "Acquire::Retries" not in block:
            findings.append("[ci.install] apt runs without Acquire::Retries, so a "
                            "transient mirror failure becomes a hang instead of a "
                            "retry")
        quoted_cap = re.search(r"its own (\d+)-minute cap", text)
        if not quoted_cap:
            findings.append("[ci.install] the install cap is no longer stated "
                            "where it is set; the comment is what makes the "
                            "number a decision rather than a guess")
        elif cap and int(quoted_cap.group(1)) != int(cap.group(1)):
            findings.append(f"[ci.install] the comment says the install step has "
                            f"its own {quoted_cap.group(1)}-minute cap but the "
                            f"step asks for {cap.group(1)}")
    return {"jobs": sorted(jobs), "ceilings": ceilings}
def _read(rel: str) -> str | None:
    path = ROOT / rel
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


# ``tests/README.md`` keeps a table whose third column is the number of checks
# pytest collects in that module.  It is the most useful and most rot-prone
# number in the repository -- every added test changes a row -- so it is audited
# structurally rather than as a pattern: rows are read, compared with a
# collection, and both directions are checked, so a module can neither be deleted
# from the table nor invented by it.
TABLE_ROW = re.compile(r"^\| `(test_\w+\.py)` \|[^|]*\| *(\d+) *\|\s*$", re.M)


def audit_module_table(table: dict, findings: list[str]) -> int:
    """Compare the per-module row counts with what pytest collects."""
    text = _read("tests/README.md")
    if text is None:
        findings.append("[tests.table] tests/README.md is missing")
        return 0
    rows = {name: int(count) for name, count in TABLE_ROW.findall(text)}
    truth = table["checks.per_module"]
    for name, count in sorted(rows.items()):
        if name not in truth:
            findings.append(f"[tests.table] tests/README.md has a row for "
                            f"{name}, which collects nothing -- the module was "
                            f"deleted or renamed and the table did not follow")
        elif rows[name] != truth[name]:
            findings.append(f"[tests.table] {name}: the table says {count} "
                            f"collected checks, a collection says "
                            f"{truth[name]}")
    for name in sorted(set(truth) - set(rows)):
        findings.append(f"[tests.table] {name} collects {truth[name]} checks and "
                        f"is not in the table at all")
    total = sum(rows.values())
    if total != table["checks.collected"]:
        findings.append(f"[tests.table] the table sums to {total} but the suite "
                        f"collects {table['checks.collected']}")
    return len(rows)


# The README's proof-layer table finishes the row for this tool with the numbers
# it prints: how many claims are registered, how many of them carry a value, how
# many module rows were read.  Those three cannot be computed by ``facts()`` --
# they are outputs of a scan -- so this row is checked against the report being
# assembled, in the same run.  It is the only self-referential claim here, and it
# is what makes the registry's own size visible in the documentation.
SELF_ROW = re.compile(
    r"\| `tools/doc_numbers\.py` \|[^|]*\| *(\d+) documented claims, "
    r"(\d+) numbers, (\d+) module rows, 0 findings")


def audit_self(findings: list[str], values: int, rows: int) -> None:
    """Compare the README's row for this audit with the report being built."""
    text = _read("README.md")
    if text is None:
        findings.append("[docs.self.row] README.md is missing, so nothing states "
                        "what this audit is supposed to report")
        return
    m = SELF_ROW.search(text)
    if not m:
        findings.append("[docs.self.row] README.md no longer states this tool's "
                        "own output in the proof-layer table; the row is what "
                        "tells a reader the gate runs and how big it is")
        return
    for label, got, w in (("documented claims", int(m.group(1)), len(CLAIMS)),
                          ("numbers", int(m.group(2)), values),
                          ("module rows", int(m.group(3)), rows)):
        if got != w:
            findings.append(f"[docs.self.row] README.md says this audit reports "
                            f"{got} {label}; this run reports {w}")


def scan(blob: dict | None = None, allow_unstated: bool = False) -> dict:
    """Check every documented claim against the computed facts.

    Returns ``{"facts": ..., "findings": [...], "checked": N, "values": M}``;
    a finding is a defect in the documentation, never in the tree.
    """
    table = blob if blob is not None else facts()
    findings: list[str] = []
    checked = 0
    values = 0

    def say(rule: str, msg: str) -> None:
        findings.append(f"[{rule}] {msg}")

    for claim in CLAIMS:
        paths = sorted(ROOT.glob(claim.file)) if "*" in claim.file \
            else ([ROOT / claim.file] if (ROOT / claim.file).exists() else [])
        if not paths:
            say(claim.rule, f"{claim.file} does not exist, but the audit claims "
                            f"it states: {claim.note}")
            continue
        regex = claim.regex()
        matched = 0
        for path in paths:
            text = path.read_text(encoding="utf-8", errors="replace")
            rel = str(path.relative_to(ROOT))
            for m in regex.finditer(text):
                matched += 1
                values += len(claim.groups)
                for group, key in zip(m.groups(), claim.groups):
                    try:
                        want = _fact(key, table)
                    except KeyError:
                        say(claim.rule,
                            f"{rel}: the registry says this number is "
                            f"{key!r}, which this audit does not measure")
                        continue
                    got = int(group.replace(",", ""))
                    if got != want:
                        say(claim.rule,
                            f"{rel} says {got} but the tree says {want} "
                            f"({key}); {claim.note}")
        if matched < claim.at_least:
            say(claim.rule,
                f"{claim.file}: the claim {claim.regex().pattern!r} was not "
                f"found (matched {matched}, need >= {claim.at_least}); "
                f"{claim.note}")

    rows = audit_module_table(table, findings)
    ci = audit_workflow(findings)
    stated = {key for claim in CLAIMS for groups in [claim.groups]
              for key in groups}
    unlisted = sorted(set(table) - set(stated) - {
        k for k in table if k.endswith(".per_module")})
    # A measurement nobody reads has already started to rot: it can disagree with
    # the documentation without the documentation noticing.  Reporting it as a
    # finding is what keeps the two halves of the registry -- facts and claims --
    # the same size.
    if unlisted and not allow_unstated:
        say("docs.fact.unclaimed",
            "measured by this audit but stated by no document: "
            + ", ".join(unlisted))
    audit_self(findings, values=values, rows=rows)
    return {"facts": table, "findings": findings, "checked": len(CLAIMS),
            "values": values, "module_rows": rows, "ci": ci,
            "unstated_facts": unlisted}


# --------------------------------------------------------------------------- #
# command line
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    ap.add_argument("--show-facts", action="store_true",
                    help="print the computed facts and exit")
    ap.add_argument("--min-claims", type=int, default=30,
                    help="fail if the registry audits fewer than this many "
                         "claims; stops the gate being emptied by deletion")
    ap.add_argument("--allow-unstated", action="store_true",
                    help="report facts that no document claims as a note rather "
                         "than a finding; for a tree mid-refactor, not for CI")
    args = ap.parse_args(argv)

    if args.show_facts:
        print(json.dumps(facts(), indent=1, sort_keys=True))
        return 0

    report = scan(allow_unstated=args.allow_unstated)
    if len(CLAIMS) < args.min_claims:
        report["findings"].append(
            f"[registry.floor] the registry holds {len(CLAIMS)} claims, floor is "
            f"{args.min_claims}")
    if args.json:
        print(json.dumps(report, indent=1, sort_keys=True))
    else:
        for key in sorted(report["facts"]):
            value = report["facts"][key]
            if not isinstance(value, dict):
                print(f"  {key:28} {value}")
        print(f"documentation audit: {report['checked']} claims, "
              f"{report['values']} numbers, {report['module_rows']} module rows, "
              f"{len(report['findings'])} finding(s)")
        for finding in report["findings"]:
            print("  " + finding)
        if report["unstated_facts"]:
            print("  (measured but not claimed anywhere: "
                  + ", ".join(report["unstated_facts"]) + ")")
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

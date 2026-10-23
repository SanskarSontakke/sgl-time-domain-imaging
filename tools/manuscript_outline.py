#!/usr/bin/env python3
"""Structural audit of the manuscript: does the built paper have the shape the
repository claims?

The numeric ledger (``tools/claims.py``) answers "where did this number come
from?".  It cannot answer the outline questions a referee asks without opening
the source: is Section 4 before Section 5, is every appendix cited before the
reader reaches it, does Table 12 land after Table 11, does equation 9 exist, is
Figure 3 mentioned anywhere, is the PDF the reader downloads the PDF that this
``main.tex`` produced?  Those are the questions that decide whether a paper is
*ordered*, and an ordered paper is what the single-version revision was for.

The audit reads three things that a LaTeX build leaves behind:

``paper/main.tex``  the source, from which section order, float order, captions,
                    labels, references, bibliography keys and the hypersetup
                    metadata block are parsed.
``paper/main.aux``  what the *build* decided: the number and page of every
                    label, and every citation the text actually made.
``paper/main.log``  what the build reported: page count, unresolved references,
                    duplicate definitions, overfull boxes, errors.

The ``.aux`` is the interesting one.  A source file can list its sections in any
order and still produce a document that reads differently -- only the aux knows
that ``sec:methods`` became number 4 on page 6.  So every ordering claim in this
tool is checked against the aux, not against the source, and the source is
checked against the aux.

The aux and the log are build products, and this repository does not track them
(``.gitignore``).  To keep the ordering gate available to a job that has no TeX
installation, ``--write-record`` distills the two into
``tools/manuscript_build_record.json``: the label/number/page table, the citation
set, the log counters, and a *structure fingerprint* of the source that produced
them.  ``--check-record`` re-audits the source against that record and fails if
the fingerprint moved, so a section that was added, deleted or relabelled since
the recorded build cannot hide behind stale page numbers.  The paper job in CI
regenerates the record from its own fresh build and diffs it against the
committed one, which is the stronger statement: the evidence in the repository is
the evidence of this build.

Usage
-----
``python3 tools/manuscript_outline.py``            audit the build evidence found
                                                   in this tree (aux/log, else the
                                                   committed record); non-zero
                                                   exit on any finding
``python3 tools/manuscript_outline.py --json``      machine-readable
``python3 tools/manuscript_outline.py --build-dir DIR``
                                                   audit DIR/main.{tex,aux,log}
                                                   instead of paper/ -- what CI
                                                   uses to audit the *freshly
                                                   built* manuscript rather than
                                                   the committed one
``python3 tools/manuscript_outline.py --write-record OUT``
                                                   emit the distilled evidence
``python3 tools/manuscript_outline.py --strict-metadata``
                                                   refuse to pass a tree with no
                                                   PDF; the information
                                                   dictionary is decoded and
                                                   compared with ``\\hypersetup``
                                                   whenever a PDF is present
``python3 tools/manuscript_outline.py --pdf-text TXT``
                                                   check a pdftotext dump against
                                                   the numeric ledger: the digits
                                                   a reader downloads must be the
                                                   digits the archives produce

Every threshold lives in :data:`DOCUMENTED`, one place, so that changing the
paper means editing one dict -- and so that ``tools/doc_numbers.py`` can prove
the README, the demo app and the arXiv listing quote the same numbers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import claims as CL  # noqa: E402  (tools/ is not a package)

# --------------------------------------------------------------------------- #
# what the repository claims about its own manuscript
# --------------------------------------------------------------------------- #
# These are not preferences; they are the numbers printed in README.md, in the
# manuscript's own reproduction appendix, in submission/arxiv_metadata.txt and
# in the demo app.  A mismatch is a documentation defect, so it is a finding.
DOCUMENTED = {
    "pages": 36,
    "figures": 9,
    "tables": 16,
    "equations": 18,
    "bibitems": 28,
    "sections": 9,             # top-level headings before \appendix
    "numbered_sections": 8,    # ... of which LaTeX gave a number to
    "appendices": 4,
    "overfull": 0,
    "undefined": 0,
    "duplicate_labels": 0,
    "errors": 0,
}

# The canonical spine, in the order the argument is built.  A retitle or a
# renamed subsection is a prose decision and does not belong in a gate; this
# list is checked by *stem* only, and only against the top-level headings, so it
# fails when a chapter moves, not when a heading is reworded.
SECTION_STEMS = [
    "Introduction",
    "SGL Photometric Model",
    "Dynamic Scene",
    "Reconstruction Methods",
    "Results",
    "From Algorithm to Mission",
    "Discussion and Limitations",
    "Conclusions",
    "Data and Code Availability",
]

TITLE_FILES = [
    "paper/main.tex",
    "README.md",
    "CITATION.cff",
    "submission/arxiv_metadata.txt",
    "submission/cover_letter.tex",
    "reviews/response_to_editor.md",
    "public/docs/response_to_editor.md",
]

RECORD = ROOT / "tools" / "manuscript_build_record.json"
RECORD_KEYS = {"generated_by", "comment", "source", "fingerprint", "labels",
               "citations", "log"}


def structure_fingerprint(t: dict) -> str:
    """What the aux depends on, and nothing the prose can change freely.

    Titles, wording and every number in the paper may be revised without a
    single label moving; adding, deleting or relabelling a section or float is a
    different matter, because the recorded page numbers stop describing the
    source.  So the fingerprint covers the skeleton only.
    """
    core = {
        "sections": [[s["level"], bool(s["starred"]), s["label"]]
                     for s in t["sections"]],
        "floats": [[f["kind"], f["label"], bool(f["has_caption"])]
                   for f in t["floats"]],
        "bibitems": sorted(set(t["bibitems"])),
        "refs": sorted(set(t["refs"])),
        "equation_envs": t["equation_envs"],
        "has_appendix": t["has_appendix"],
    }
    blob = json.dumps(core, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #
LABEL_RE = re.compile(r"\\newlabel\{([^}]+)\}\{\{([^{}]*)\}\{([^{}]*)\}")
CITE_RE = re.compile(r"\\citation\{([^}]*)\}")
REF_RE = re.compile(r"\\(?:ref|eqref|pageref)\{([^}]+)\}")
BIB_RE = re.compile(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}")
SECT_RE = re.compile(r"\\(section|subsection)(\*?)\{([^{}]*)\}")
ENV_RE = r"\*?"


def strip_comments(text: str) -> str:
    """LaTeX comments gone, escaped percent signs kept."""
    return re.sub(r"(?<!\\)%.*", " ", text)


def parse_aux(text: str) -> dict:
    """Labels, numbers, pages and citations, as the build recorded them."""
    labels = {}
    for name, number, page in LABEL_RE.findall(text):
        labels[name] = {"number": number, "page": int(page)}
    citations: set[str] = set()
    for group in CITE_RE.findall(text):
        citations |= {k.strip() for k in group.split(",") if k.strip()}
    return {"labels": labels, "citations": citations}


def parse_log(text: str) -> dict:
    """The counters a reader of the PDF would never see."""
    out = re.search(r"Output written on (\S+\.pdf) \((\d+) pages?, (\d+) bytes?\)",
                    text)
    pages = int(out.group(2)) if out else None
    def count(pattern: str) -> int:
        return len(re.findall(pattern, text, re.M))
    return {
        "pdf": out.group(1) if out else None,
        "pages": pages,
        "bytes": int(out.group(3)) if out else None,
        "errors": count(r"^! "),
        "undefined_references": count(r"Reference [^\n]*undefined"),
        "undefined_citations": count(r"Citation [^\n]*undefined"),
        "multiply_defined": count(r"multiply defined"),
        "overfull": count(r"Overfull \\"),
        "underfull": count(r"Underfull \\"),
        "rerun_warnings": count(r"Rerun to get"),
        "missing_figures": count(r"File [^\n]* not found"),
    }


# The complete key set each parser returns for an empty input.  A distilled
# build record carries these fields, not the raw files, so an audit whose
# evidence is a partial record falls back on these shapes instead of raising a
# KeyError on the field the record never had -- a short record is a finding, not
# a crash.
AUX_SHAPE = parse_aux("")
LOG_SHAPE = parse_log("")


def parse_tex(text: str) -> dict:
    """Structure of the source: sections, floats, equations, bibliography."""
    full = strip_comments(text)
    src = full
    start = full.find("\\begin{document}")
    if start != -1:
        stop = full.find("\\end{document}", start)
        src = full[start:stop if stop != -1 else None]
    appendix_at = src.find("\\appendix")
    sections = []
    for m in SECT_RE.finditer(src):
        level, starred, title = m.group(1), m.group(2), m.group(3).strip()
        tail = src[m.end():m.end() + 120]
        lm = re.match(r"\s*(?:\[[^\]]*\]\s*)?\\label\{([^}]+)\}", tail)
        sections.append({
            "level": level,
            "starred": bool(starred),
            "title": title,
            "label": lm.group(1) if lm else None,
            "pos": m.start(),
            "appendix": appendix_at != -1 and m.start() > appendix_at,
        })
    floats = []
    for env, kind in (("figure", "fig"), ("table", "tab")):
        for m in re.finditer(r"\\begin\{" + env + ENV_RE + r"\}", src):
            stop = src.find("\\end{" + env, m.start())
            block = src[m.start():stop if stop != -1 else None]
            label = re.search(r"\\label\{([^}]+)\}", block)
            caption = re.search(r"\\caption\{", block)
            floats.append({
                "kind": kind,
                "label": label.group(1) if label else None,
                "has_caption": caption is not None,
                "pos": m.start(),
            })
    equations = len(re.findall(r"\\begin\{(?:equation|align|gather)\*?\}", src))
    bibitems = [m.group(1) for m in BIB_RE.finditer(src)]
    refs = [m.group(1) for m in REF_RE.finditer(src)]
    return {
        "sections": sections,
        "floats": floats,
        "equation_envs": equations,
        "bibitems": bibitems,
        "refs": refs,
        "has_appendix": appendix_at != -1,
        "pdftitle": match(r"pdftitle=\{([^{}]*)\}", full),
        "pdfauthor": match(r"pdfauthor=\{([^{}]*)\}", full),
        "pdfsubject": match(r"pdfsubject=\{([^{}]*)\}", full),
        "pdfkeywords": match(r"pdfkeywords=\{([^{}]*)\}", full),
        "typeset_title": typeset_title(src),
    }


def match(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text, re.S)
    return normalize(m.group(1)) if m else None


def typeset_title(src: str) -> str | None:
    """The title as it is printed on page one: the \\Large\\bfseries block."""
    m = re.search(r"\\begin\{center\}\s*\{\\Large\\bfseries\s*(.*?)\\par\}",
                  src, re.S)
    return normalize(m.group(1)) if m else None


def normalize(text: str) -> str:
    """One line, one space between words, braces and LaTeX padding gone.

    Commands are stripped *before* the braces: ``\\textit{Time-Domain}`` with the
    braces removed first reads ``\\textitTime-Domain``, and a greedy command
    pattern then swallows the first word of the title it was supposed to keep.
    """
    text = text.replace("\\&", "&").replace("``", '"').replace("''", '"')
    text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)
    text = re.sub(r"[{}]", "", text)
    text = re.sub(r"[\\^_~]", " ", text)
    return " ".join(text.split())


# --------------------------------------------------------------------------- #
# the PDF information dictionary
# --------------------------------------------------------------------------- #
def unescape_pdf_string(raw: bytes) -> bytes:
    """Turn ``(\\376\\377\\000T...)`` into the bytes the viewer displays."""
    out = bytearray()
    i = 0
    while i < len(raw):
        c = raw[i:i + 1]
        if c != b"\\":
            out += c
            i += 1
            continue
        nxt = raw[i + 1:i + 2]
        if nxt in b"nrtbf":
            out += {b"n": b"\n", b"r": b"\r", b"t": b"\t",
                    b"b": b"\b", b"f": b"\f"}[nxt]
            i += 2
        elif nxt in b"01234567":
            digits = re.match(rb"[0-7]{1,3}", raw[i + 1:])
            out.append(int(digits.group(0), 8))
            i += 1 + len(digits.group(0))
        elif nxt in (b"(", b")", b"\\"):
            out += nxt
            i += 2
        else:
            out += nxt or b""
            i += 2
    return bytes(out)


def pdf_info(pdf: Path) -> dict:
    """Every string in the information dictionary, decoded."""
    blob = pdf.read_bytes()
    # /Title and friends live in a dictionary object; take the first one that
    # has any of the keys we care about rather than assuming a trailer layout.
    found: dict[str, str] = {}
    for key in ("Title", "Author", "Subject", "Keywords", "Creator",
                "Producer"):
        for m in re.finditer(b"/" + key.encode() + rb"\s*\(", blob):
            raw, i, depth = bytearray(), m.end(), 1
            while i < len(blob) and depth:
                ch = blob[i:i + 1]
                if ch == b"\\":
                    raw += blob[i:i + 2]
                    i += 2
                    continue
                if ch == b"(":
                    depth += 1
                elif ch == b")":
                    depth -= 1
                    if not depth:
                        break
                raw += ch
                i += 1
            data = unescape_pdf_string(bytes(raw))
            if data[:2] in (b"\xfe\xff", b"\xff\xfe"):
                found[key] = normalize(data[2:].decode("utf-16-be", "replace"))
            else:
                found[key] = normalize(data.decode("latin-1", "replace"))
            break
    return found


# --------------------------------------------------------------------------- #
# the audit
# --------------------------------------------------------------------------- #
def pdf_flatten(text: str) -> str:
    """pdftotext output as one searchable line.

    Math mode writes a real minus (U+2212) and hyperref a non-breaking space, so
    "-0.1978" in the source is not the same byte sequence in the PDF.  Hyphenated
    line breaks inside a number are not a thing TeX does, so no separator repair
    is needed for the digits.
    """
    text = text.replace("\u2212", "-").replace("\u2013", "--")
    text = text.replace("\u00a0", " ").replace("{,}", ",")
    return " ".join(text.split())


def audit(tex: str, aux_text, log_text,
          expected: dict | None = None, pdf: Path | None = None,
          pdf_text: str | None = None,
          record: dict | None = None) -> dict:
    """Return ``{"metrics": ..., "findings": [str]}``.  A finding is a defect.

    ``aux_text`` and ``log_text`` may be the raw files or the parsed dicts (what
    a distilled build record carries).  ``record``, when given, is that record:
    its structure fingerprint is then compared with the source's, which is how a
    page number left over from an older skeleton is caught.
    """
    expected = dict(DOCUMENTED, **(expected or {}))
    src = strip_comments(tex)
    spine = expected.get("spine", SECTION_STEMS)
    a = parse_aux(aux_text) if isinstance(aux_text, str) \
        else dict(AUX_SHAPE, **(aux_text or {}))
    log = parse_log(log_text) if isinstance(log_text, str) \
        else dict(LOG_SHAPE, **(log_text or {}))
    t = parse_tex(tex)
    labels = a["labels"]
    findings: list[str] = []
    metrics: dict = {"log": log, "aux_labels": len(labels),
                    "sections": len(t["sections"]),
                    "floats": len(t["floats"]),
                    "equation_envs": t["equation_envs"],
                    "bibitems": len(t["bibitems"]),
                    "refs": len(t["refs"])}

    def say(rule: str, msg: str) -> None:
        findings.append(f"[{rule}] {msg}")

    # ---- 0. is the evidence even about this source? -----------------------
    if record is not None:
        absent = sorted(RECORD_KEYS - set(record))
        if absent:
            say("record.shape", f"build record has no {absent}")
        fp = structure_fingerprint(t)
        if record.get("fingerprint") != fp:
            say("record.stale",
                f"the recorded build was of a different skeleton (record "
                f"{record.get('fingerprint')!r}, source {fp!r}): add, delete or "
                f"relabel a float or heading and the page numbers stop "
                f"describing this paper")

    # ---- 1. section order, from the build rather than the source ----------
    heads = [s for s in t["sections"]
             if s["level"] == "section" and not s["appendix"]]
    body = [s for s in heads if not s["starred"]]
    got = [s["title"] for s in heads]
    if len(heads) != expected["sections"]:
        say("count.sections", f"{len(heads)} top-level headings before "
                              f"\\appendix, documentation says "
                              f"{expected['sections']}")
    if len(body) != expected["numbered_sections"]:
        say("count.sections", f"{len(body)} numbered sections, documentation "
                              f"says {expected['numbered_sections']}")
    if any(normalize(g) != g for g in got):
        say("order.sections", "a section title needs whitespace flattening")
    if len(got) != len(spine):
        say("order.sections", f"{len(got)} headings but {len(spine)} "
                              "documented spine entries")
    for want, have in zip(spine, [normalize(g) for g in got]):
        if not have.startswith(want[:14]):
            say("order.sections",
                f"section spine broken: expected {want!r}, found {have!r}")
            break
    numbered = [labels[s["label"]]["number"] for s in body if s["label"] in labels]
    if len(numbered) != len(body):
        say("order.sections", f"{len(body) - len(numbered)} numbered sections "
                              "carry no \\label, so the build cannot be ordered")
    if numbered and numbered != [str(i + 1) for i in range(len(numbered))]:
        say("order.sections", f"section numbers are not 1..N: {numbered}")
    labelled = [s for s in t["sections"] if s["label"] in labels]
    pages = [labels[s["label"]]["page"] for s in labelled]
    backwards = [(labelled[i]["label"], pages[i], labelled[i + 1]["label"],
                  pages[i + 1]) for i in range(len(pages) - 1)
                 if pages[i + 1] < pages[i]]
    if backwards:
        say("order.pages", "a labelled section starts before the page its "
                           "predecessor began on, so the build reordered the "
                           "paper: " + ", ".join(f"{a} p{pa} > {b} p{pb}"
                                                 for a, pa, b, pb in backwards))

    # ---- 2. appendices ----------------------------------------------------
    apps = [s for s in t["sections"]
            if s["level"] == "section" and not s["starred"] and s["appendix"]]
    if len(apps) != expected["appendices"]:
        say("count.appendices",
            f"{len(apps)} appendices, documentation says {expected['appendices']}")
    letters = [labels[s["label"]]["number"] for s in apps if s["label"] in labels]
    want = list("ABCDEF")[:len(letters)]
    if letters and letters != want:
        say("order.appendices", f"appendix letters should be {want}, are {letters}")
    if heads and apps and apps[0]["pos"] < heads[-1]["pos"]:
        say("order.appendices", "an appendix precedes the last body section")
    # An appendix is *promised* when the body asks the reader to go there, by
    # section label or through any float that lives inside it -- Appendix B is
    # routinely reached as "Table 13" rather than as "Appendix B".
    cut = src.find("\\appendix")
    pre = src[:cut] if cut != -1 else src
    starts = [s["pos"] for s in apps] + [10 ** 12]
    order = []
    for i, s in enumerate(apps):
        inside = [f["label"] for f in t["floats"]
                  if starts[i] <= f["pos"] < starts[i + 1] and f["label"]]
        names = ([s["label"]] if s["label"] else []) + inside
        hits = [pre.find("\\ref{" + n + "}") for n in names]
        hits = [h for h in hits if h >= 0]
        order.append((s["label"] or f"appendix {want[i] if i < len(want) else '?'}",
                      min(hits) if hits else -1, names))
    uncited = [lab for lab, pos, _ in order if pos < 0]
    if uncited:
        say("cites.appendices", f"appendices never promised in the body, by "
                                f"section or by any float inside them: {uncited}")
    promised = [(lab, pos) for lab, pos, _ in order if pos >= 0]
    if [p for _, p in promised] != sorted(p for _, p in promised):
        say("order.appendices",
            "appendices are promised in a different order from the one they "
            "appear in: " + ", ".join(f"{lab}@{p}" for lab, p in promised))

    # ---- 3. floats --------------------------------------------------------
    for kind, noun in (("fig", "figure"), ("tab", "table")):
        own = [f for f in t["floats"] if f["kind"] == kind]
        if len(own) != expected[noun + "s"]:
            say(f"count.{noun}s", f"{len(own)} {noun} environments in the "
                                  f"source, documentation says "
                                  f"{expected[noun + 's']}")
        missing = [f"env #{i + 1}" for i, f in enumerate(own) if not f["label"]]
        if missing:
            say("floats.labelled", f"{noun}s without a label: {missing}")
        unl = [f"env #{i + 1}" for i, f in enumerate(own) if not f["has_caption"]]
        if unl:
            say("floats.caption", f"{noun}s with no caption: {unl}")
        rows = [(labels[f["label"]]["number"], labels[f["label"]]["page"],
                 f["label"]) for f in own
                if f["label"] in labels]
        nums = [int(n) for n, _, _ in rows]
        if nums and nums != list(range(1, len(nums) + 1)):
            say("floats.numbering", f"{noun} numbers are not 1..N: {nums}")
        pgs = [p for _, p, _ in rows]
        if any(b < a for a, b in zip(pgs, pgs[1:])):
            back = [(lab, a, b) for (n, a, lab), (m, b, _)
                    in zip(rows, rows[1:]) if b < a]
            say("floats.pages", f"{noun} drifts before its predecessor: "
                                 + ", ".join(f"{l} p{a} before p{b}"
                                             for l, a, b in back))
        # every float must be promised to the reader, and not before its
        # enclosing section has begun
        for f in own:
            lab = f["label"]
            if not lab:
                continue
            hits = [r for r in t["refs"] if r == lab]
            if not hits:
                say("floats.cited", f"{noun} {lab} is never referenced")
            if lab in labels:
                sec = [s for s in t["sections"] if s["label"] in labels
                       and s["pos"] < f["pos"]]
                if sec:
                    start = labels[sec[-1]["label"]]["page"]
                    if labels[lab]["page"] < start:
                        say("floats.section_page",
                            f"{lab} is on page {labels[lab]['page']}, before "
                            f"{sec[-1]['label']} begins on page {start}")

    # ---- 4. equations -----------------------------------------------------
    # LaTeX numbers every equation, labelled or not, and an ``align`` issues one
    # number per row, so the source's environment count is not the number of
    # displayed equations.  The aux is: equation 1 may be unlabelled, 2..18 need
    # not all be labelled, but no number may be issued twice or past the total.
    eq = sorted((int(labels[l]["number"]), l) for l in labels
                if l.startswith("eq:"))
    nums = [n for n, _ in eq]
    metrics["equation_numbers"] = nums
    if nums:
        if max(nums) != expected["equations"]:
            say("count.equations", f"the build numbered {max(nums)} equations, "
                                   f"documentation says {expected['equations']}")
        dupes = sorted({n for n in nums if nums.count(n) > 1})
        if dupes:
            say("equations.unique",
                f"equation numbers used twice: {dupes}")
    if t["equation_envs"] > (max(nums) if nums else 0):
        say("equations.envs", f"{t['equation_envs']} numbered environments in "
                              f"the source but only "
                              f"{max(nums) if nums else 0} numbers issued")

    # ---- 5. references and citations resolve ------------------------------
    unresolved = sorted({r for r in t["refs"] if r not in labels})
    if unresolved:
        say("refs.resolve", f"references with no label in the build: "
                             f"{unresolved[:8]}")
    bib = set(t["bibitems"])
    uncited = sorted(bib - a["citations"])
    if uncited:
        say("cites.used", f"bibliography entries never cited: {uncited}")
    unknown = sorted(a["citations"] - bib)
    if unknown:
        say("cites.resolve", f"citations with no \\bibitem: {unknown}")
    if len(bib) != len(t["bibitems"]):
        say("cites.unique", "duplicate \\bibitem keys")

    # ---- 6. the build was clean ------------------------------------------
    ceilings = {"errors": expected["errors"],
                "undefined_references": expected["undefined"],
                "undefined_citations": expected["undefined"],
                "multiply_defined": expected["duplicate_labels"],
                "overfull": expected["overfull"],
                "rerun_warnings": 0,
                "missing_figures": 0}
    rules = {"errors": "log.errors", "undefined_references": "log.undefined",
             "undefined_citations": "log.undefined",
             "multiply_defined": "log.duplicates", "overfull": "log.overfull",
             "rerun_warnings": "log.rerun",
             "missing_figures": "log.missing_graphics"}
    for key, ceiling in ceilings.items():
        if log[key] > ceiling:
            say(rules[key], f"{log[key]} {key.replace('_', ' ')} in main.log, "
                            f"ceiling {ceiling}")
    if log["pages"] is None:
        say("log.pages", "main.log has no 'Output written on ... (N pages)' line "
                         "-- the build did not finish")
    elif log["pages"] != expected["pages"]:
        say("count.pages", f"the build is {log['pages']} pages, documentation "
                           f"says {expected['pages']}")

    # ---- 7. metadata ------------------------------------------------------
    for key in ("pdftitle", "pdfauthor", "pdfsubject", "pdfkeywords"):
        if not t[key]:
            say("metadata.present", f"\\hypersetup has no {key}")
    if t["pdftitle"] and t["typeset_title"] and \
            t["pdftitle"].rstrip(".") != t["typeset_title"].rstrip("."):
        say("metadata.title_matches_typeset",
            f"PDF title {t['pdftitle'][:60]!r} is not the typeset title "
            f"{t['typeset_title'][:60]!r}")
    if pdf is not None and pdf.exists():
        info = pdf_info(pdf)
        metrics["pdf_info"] = info
        for tex_key, pdf_key in (("pdftitle", "Title"), ("pdfauthor", "Author"),
                                 ("pdfsubject", "Subject"),
                                 ("pdfkeywords", "Keywords")):
            if not info.get(pdf_key):
                say("pdf.metadata", f"{pdf_key} is empty in the shipped PDF")
            elif t[tex_key] and info[pdf_key].rstrip(".") != t[tex_key].rstrip("."):
                say("pdf.metadata",
                    f"{pdf_key} in the shipped PDF does not match "
                    f"\\hypersetup's {tex_key}")

    # ---- 8. the built PDF says what the source says -----------------------
    # A ledger entry proves main.tex and results/ agree.  Only this check proves
    # the file a reader downloads contains the same digits -- a PDF that was not
    # rebuilt after a prose repair is exactly the defect continuous integration
    # was added to catch.
    if pdf_text is not None:
        flat = pdf_flatten(pdf_text)
        metrics["pdf_text_chars"] = len(flat)
        ledger = CL.load_ledger()
        gone = sorted({c["shown"] for c in ledger["claims"]
                       if c["shown"] not in flat})
        if gone:
            say("pdf.text_matches_ledger",
                f"{len(gone)} ledgered numbers are not in the built PDF: "
                f"{gone[:8]}")
        if t["typeset_title"]:
            head = " ".join(t["typeset_title"].split()[:5])
            if head not in flat:
                say("pdf.text", f"the typeset title ({head!r}) is not the first "
                                "page text of the built PDF")
        for needle in ("ABSTRACT", "References"):
            if needle not in flat:
                say("pdf.text", f"{needle!r} is missing from the built PDF")

    return {"metrics": metrics, "findings": findings,
            "title": t["pdftitle"], "sections": got,
            "appendices": [s["title"] for s in apps]}


def splice_inputs(base: Path, text: str) -> str:
    """``\\input{x}`` replaced by x.tex, the way LaTeX reads it.

    One generated fragment (``paper/targets_table.tex``) carries a table of its
    own, so an audit of main.tex alone would report fifteen tables in a sixteen-
    table paper.
    """
    def sub(m: re.Match) -> str:
        name = m.group(1)
        for cand in (base / f"{name}.tex", ROOT / "paper" / f"{name}.tex"):
            if cand.exists():
                return cand.read_text(encoding="utf-8")
        return m.group(0)

    return re.sub(r"\\input\{([^}]+)\}", sub, text)


def read_source(build_dir: Path | None = None) -> tuple[str, Path | None]:
    """main.tex with its generated fragment spliced in, plus the PDF if present."""
    base = Path(build_dir) if build_dir else ROOT / "paper"
    tex = splice_inputs(base, (base / "main.tex").read_text(encoding="utf-8"))
    pdf = base / "main.pdf"
    return tex, (pdf if pdf.exists() else None)


def load_trio(build_dir: Path | None = None) -> tuple[str, str, str, Path | None]:
    base = Path(build_dir) if build_dir else ROOT / "paper"
    tex, pdf = read_source(base)
    aux = (base / "main.aux").read_text(encoding="utf-8")
    log = (base / "main.log").read_text(encoding="utf-8")
    return tex, aux, log, pdf


def write_record(out: Path, build_dir: Path | None = None) -> dict:
    """Distill main.aux + main.log into a tracked, text-only evidence file."""
    tex, aux, log, pdf = load_trio(build_dir)
    a, l = parse_aux(aux), parse_log(log)
    # a PDF's byte count changes on every compile -- pdfTeX stamps a creation
    # date into the file -- so it cannot live in a tracked record that CI diffs.
    l = {k: v for k, v in l.items() if k != "bytes"}
    record = {
        "generated_by": ("python3 tools/manuscript_outline.py --write-record "
                         "tools/manuscript_build_record.json "
                         "[--build-dir <scratch>]"),
        "comment": ("Build evidence for paper/main.tex: what the LaTeX run of "
                    "this skeleton recorded. CI verifies it against a fresh "
                    "compile; nothing here is regenerated by hand, and the "
                    "fingerprint says which source skeleton it belongs to."),
        "source": str((Path(build_dir) if build_dir else ROOT / "paper")
                      / "main.tex"),
        "fingerprint": structure_fingerprint(parse_tex(tex)),
        "labels": a["labels"],
        "citations": sorted(a["citations"]),
        "log": l,
    }
    out = Path(out)
    out.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8")
    return record


def read_record(path: Path) -> dict:
    """Load a record, normalising the JSON shapes audit() expects."""
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = sorted(RECORD_KEYS - set(record))
    if missing:
        raise ValueError(f"{path}: build record is missing {missing}")
    record["citations"] = set(record["citations"])
    return record


def load_evidence(record_path: Path | None = None) -> dict:
    """The best build evidence this tree can offer, and where it came from.

    Order of preference: the real aux/log (a built tree, CI's scratch copy), then
    the tracked record.  An explicit ``record_path`` overrides that order, because
    "--record X" is the caller saying *audit X*, and a tree that happens to still
    have a stale ``main.aux`` next to it must not silently answer a different
    question.  A tree with neither cannot be structurally audited at all, and says
    so rather than quietly passing.
    """
    base = {"origin": None, "aux": None, "log": None, "record": None,
            "pdf": None, "tex": None}
    paper = ROOT / "paper"
    if record_path is None \
            and (paper / "main.aux").exists() and (paper / "main.log").exists():
        tex, aux, log, pdf = load_trio()
        base.update(origin="paper/main.aux + paper/main.log", tex=tex,
                    aux=aux, log=log, pdf=pdf)
        return base
    path = Path(record_path).resolve() if record_path else RECORD
    if not path.exists():
        raise FileNotFoundError(
            "no build evidence: this tree has neither paper/main.aux nor "
            f"{path.name}; run a build (tools/check_pdf_build.sh) or "
            "--write-record from one")
    record = read_record(path)
    tex, pdf = read_source()
    try:
        origin = str(path.relative_to(ROOT))
    except ValueError:                      # a record outside the repository
        origin = str(path)
    base.update(origin=origin, tex=tex, pdf=pdf,
                record=record, aux=({"labels": record["labels"],
                                     "citations": record["citations"]}),
                log=record["log"])
    return base


def compare_records(committed: dict, fresh: dict) -> list[str]:
    """Differences between the tracked build record and a freshly distilled one.

    Only the evidence fields are compared.  ``source``, ``comment`` and
    ``generated_by`` describe how the record was made, not what the build said,
    and a scratch build directory is allowed to have a different path.

    This is the check continuous integration runs: it turns "the record is
    current" from an assertion about a file into an assertion about a build.
    """
    out: list[str] = []
    if committed["fingerprint"] != fresh["fingerprint"]:
        out.append(f"[record.diff.fingerprint] the tracked record describes "
                   f"skeleton {committed['fingerprint']!r} but this build is "
                   f"{fresh['fingerprint']!r}: regenerate "
                   f"tools/manuscript_build_record.json")
    old, new = committed["labels"], fresh["labels"]
    gone = sorted(set(old) - set(new))
    added = sorted(set(new) - set(old))
    if gone:
        out.append(f"[record.diff.labels] the build no longer issues "
                   f"{gone[:8]}")
    if added:
        out.append(f"[record.diff.labels] the build issues labels the record "
                   f"never heard of: {added[:8]}")
    moved = sorted(k for k in set(old) & set(new) if old[k] != new[k])
    if moved:
        out.append("[record.diff.pages] " + "; ".join(
            f"{k} was {old[k]} and is now {new[k]}" for k in moved[:8]))
    old_c, new_c = set(committed["citations"]), set(fresh["citations"])
    if old_c != new_c:
        out.append(f"[record.diff.citations] the build's citation set changed: "
                   f"gone {sorted(old_c - new_c)[:6]}, new "
                   f"{sorted(new_c - old_c)[:6]}")
    counters = ("pages", "errors", "undefined_references", "undefined_citations",
                "multiply_defined", "overfull", "rerun_warnings",
                "missing_figures")
    changed = {k: (committed["log"].get(k), fresh["log"].get(k))
               for k in counters
               if committed["log"].get(k) != fresh["log"].get(k)}
    if changed:
        out.append("[record.diff.log] " + "; ".join(
            f"{k} {a} -> {b}" for k, (a, b) in sorted(changed.items())))
    return out


def title_registry() -> list[str]:
    """Files that must carry the manuscript's full title, verbatim."""
    out = []
    tex, _pdf = read_source()
    title = parse_tex(tex)["pdftitle"]
    if not title:
        return out
    for rel in TITLE_FILES:
        path = ROOT / rel
        if not path.exists():
            out.append(f"{rel}: missing")
            continue
        text = normalize(path.read_text(encoding="utf-8", errors="replace"))
        if title.rstrip(".") not in text:
            out.append(f"{rel}: title not found")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="machine-readable")
    ap.add_argument("--build-dir", type=Path, default=None,
                    help="audit main.{tex,aux,log} in this directory (CI scratch)")
    ap.add_argument("--record", type=Path, default=None,
                    help="use this build record instead of paper/main.aux")
    ap.add_argument("--write-record", type=Path, default=None,
                    help="distill the evidence into this file and exit")
    ap.add_argument("--expect", type=str, default=None,
                    help="JSON object of overrides for the documented counts")
    ap.add_argument("--strict-metadata", action="store_true",
                    help="fail if there is no built PDF to decode (the "
                         "information dictionary is checked whenever one "
                         "exists)")
    ap.add_argument("--pdf-text", type=Path, default=None,
                    help="pdftotext output of the built PDF, checked against "
                         "the ledger")
    ap.add_argument("--compare-record", type=Path, default=None,
                    help="distill a record from --build-dir and diff it against "
                         "this tracked record; report and exit non-zero on any "
                         "difference in labels, pages, citations or counters")
    args = ap.parse_args(argv)

    if args.compare_record:
        if not args.build_dir:
            ap.error("--compare-record needs --build-dir, the build to distill")
        fresh = {k: v for k, v in write_record(
            Path(args.build_dir) / "record_under_test.json",
            args.build_dir).items() if k != "bytes"}
        committed = read_record(args.compare_record)
        diffs = compare_records(committed, fresh)
        print(f"build record vs {args.build_dir}: "
              f"{len(committed['labels'])} labels, fingerprint "
              f"{committed['fingerprint']}")
        for line in diffs:
            print("  FINDING " + line)
        print(f"  {len(diffs)} finding(s)")
        return 1 if diffs else 0

    if args.write_record:
        rec = write_record(args.write_record, args.build_dir)
        print(f"wrote {args.write_record}: {len(rec['labels'])} labels, "
              f"{len(rec['citations'])} citations, fingerprint "
              f"{rec['fingerprint']}")
        return 0

    if args.build_dir:
        tex, aux, log, pdf = load_trio(args.build_dir)
        ev = {"tex": tex, "aux": aux, "log": log, "pdf": pdf, "record": None,
              "origin": f"{args.build_dir}/main.{{aux,log}}"}
    else:
        ev = load_evidence(args.record)

    pdf_text = (args.pdf_text.read_text(encoding="utf-8", errors="replace")
                if args.pdf_text else None)
    if args.strict_metadata and ev["pdf"] is None:
        print("manuscript outline: FINDING [pdf.present] no built PDF in this "
              "tree to decode")
        return 1
    expected = json.loads(args.expect) if args.expect else {}
    result = audit(ev["tex"], ev["aux"], ev["log"], expected, ev["pdf"],
                   pdf_text, ev["record"])
    result["evidence"] = ev["origin"]
    result["title_registry"] = title_registry()
    result["findings"] += [f"[title.consistent] {m}"
                           for m in result["title_registry"]]
    result["n_findings"] = len(result["findings"])

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, default=list))
    else:
        m = result["metrics"]
        print(f"manuscript outline ({result['evidence']})")
        print(f"  pages {m['log']['pages']}  figures "
              f"{DOCUMENTED['figures']}  tables {DOCUMENTED['tables']}  "
              f"bibitems {m['bibitems']}  aux labels {m['aux_labels']}")
        print("  spine: " + " -> ".join(result["sections"]))
        print("  appendices: " + ", ".join(result["appendices"]))
        for f in result["findings"]:
            print("  FINDING " + f)
        print(f"  {len(result['findings'])} finding(s)")
    return 1 if result["findings"] else 0


if __name__ == "__main__":
    sys.exit(main())

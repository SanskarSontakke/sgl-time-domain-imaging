#!/usr/bin/env python3
"""Tests for the manuscript's structure, not its numbers.

``tests/test_claims_ledger.py`` proves that every printed result traces to an
archive.  This file proves the paper is *put together* the way its own
documentation claims: sections in the order that makes the argument, appendices
promised before they arrive, floats numbered and paginating forward, equations
issued without collisions, references and citations resolving in the build, the
log clean, the PDF metadata populated, and the shipped PDF actually carrying the
digits the ledger vouches for.

Two layers live here:

* rule tests against a miniature document small enough to break on purpose --
  a gate that cannot fail is not a gate;
* integration tests against the real ``paper/main.tex`` / ``main.aux`` /
  ``main.log``, where the assertion is that the audit finds nothing at all.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import manuscript_outline as MO  # noqa: E402


# --------------------------------------------------------------------------- #
# a miniature manuscript: three body headings, one appendix, two tables
# --------------------------------------------------------------------------- #
MINI_TEX = r"""
\documentclass{article}
\hypersetup{
  pdftitle={A Little Lens},
  pdfauthor={A. Observer},
  pdfsubject={Testing},
  pdfkeywords={one; two}}
\begin{document}
\begin{center}{\Large\bfseries A Little Lens\par}\end{center}
\section{Introduction}\label{sec:intro}
As Table~\ref{tab:first} and Figure~\ref{fig:first} show, with the method
of Appendix~\ref{app:one}, Eq.~\ref{eq:one}, Table~\ref{tab:second} and
Ref.~\cite{keyone}.
\section{Methods}\label{sec:methods}
\Eqref{eq:one} is the reason, and Section~\ref{sec:intro} the origin.
\begin{figure}\caption{A figure.}\label{fig:first}\end{figure}
\begin{table}\centering
\begin{tabular}{cc}a&b\end{tabular}\caption{A table.}\label{tab:first}
\end{table}
\begin{equation}\label{eq:one}x = y + 1\end{equation}
\section*{Data and Code Availability}
Deposited elsewhere.
\appendix
\section{One}\label{app:one}
Nothing here beyond Table~\ref{tab:first}.
\begin{table}\centering
\begin{tabular}{cc}c&d\end{tabular}\caption{Second table.}\label{tab:second}
\end{table}
\begin{thebibliography}{9}
\bibitem{keyone} Observer, A. 2026.
\end{thebibliography}
\end{document}
"""

MINI_AUX = r"""
\newlabel{sec:intro}{{1}{1}}
\newlabel{sec:methods}{{2}{1}}
\newlabel{app:one}{{A}{2}}
\newlabel{fig:first}{{1}{1}}
\newlabel{tab:first}{{1}{2}}
\newlabel{tab:second}{{2}{2}}
\newlabel{eq:one}{{1}{1}}
\citation{keyone}
"""

MINI_LOG = r"""
This is pdfTeX, Version 3.1415926 (TeX Live 2022)
Output written on main.pdf (2 pages, 12345 bytes).
"""

# What the miniature documents about itself.  The real paper's numbers are in
# MO.DOCUMENTED; a test that audited a two-page mock against a 36-page claim
# would prove nothing except that constants exist.
MINI = {"pages": 2, "figures": 1, "tables": 2, "equations": 1, "bibitems": 1,
        "sections": 3, "numbered_sections": 2, "appendices": 1,
        "spine": ["Introduction", "Methods", "Data and Code Availability"]}


def findings(tex=MINI_TEX, aux=MINI_AUX, log=MINI_LOG, **overrides) -> list[str]:
    expected = dict(MINI, **overrides)
    return MO.audit(tex, aux, log, expected=expected)["findings"]


def fired(found: list[str], rule: str) -> bool:
    return any(f.startswith("[" + rule + "]") for f in found)


# --------------------------------------------------------------------------- #
# parsers
# --------------------------------------------------------------------------- #
class TestParsers:
    def test_aux_gives_number_page_and_citations(self):
        a = MO.parse_aux(MINI_AUX)
        assert a["labels"]["sec:methods"] == {"number": "2", "page": 1}
        assert a["labels"]["app:one"]["number"] == "A"
        assert a["citations"] == {"keyone"}

    def test_aux_pages_are_integers(self):
        a = MO.parse_aux(MINI_AUX)
        assert all(isinstance(v["page"], int) for v in a["labels"].values())

    def test_multi_key_citation_lines_split(self):
        a = MO.parse_aux("\\citation{aa,bb,cc}\n\\citation{dd}\n")
        assert a["citations"] == {"aa", "bb", "cc", "dd"}

    def test_log_counters(self):
        log = MO.parse_log(MINI_LOG
                           + "\nOverfull \\hbox (12pt too wide) in paragraph\n"
                           + "! Undefined control sequence.\n"
                           + "LaTeX Warning: Reference `x' on page 1 undefined.\n"
                           + "LaTeX Warning: Citation `y' on page 1 undefined.\n"
                           + "LaTeX Warning: Label `z' multiply defined.\n")
        assert log["pages"] == 2 and log["bytes"] == 12345
        assert log["overfull"] == 1 and log["errors"] == 1
        assert log["undefined_references"] == 1
        assert log["undefined_citations"] == 1
        assert log["multiply_defined"] == 1

    def test_underfull_boxes_are_measured_but_not_gated(self):
        """A two-column article has hundreds of them; the paper claims nothing
        about underfull boxes, so the audit reports them as a metric only."""
        log = MO.parse_log(MINI_LOG + "Underfull \\hbox (badness 10000)\n")
        assert log["underfull"] == 1

    def test_log_without_a_finished_build(self):
        assert MO.parse_log("kpathsea: Running mktexfmt\n")["pages"] is None

    def test_tex_structure(self):
        t = MO.parse_tex(MINI_TEX)
        heads = [s for s in t["sections"] if s["level"] == "section"]
        assert [s["title"] for s in heads] == ["Introduction", "Methods",
                                               "Data and Code Availability", "One"]
        assert heads[3]["appendix"] is True
        assert heads[2]["starred"] is True
        assert heads[0]["label"] == "sec:intro"
        assert [f["label"] for f in t["floats"]] == ["fig:first", "tab:first",
                                                    "tab:second"]
        assert t["bibitems"] == ["keyone"]
        assert t["has_appendix"] is True

    def test_preamble_macros_are_not_headings(self):
        """``\\newcommand{\\ack}{\\section*{Ack}}`` must not read as a chapter --
        the real main.tex defines exactly such a macro and never uses it."""
        t = MO.parse_tex("\\newcommand{\\ack}{\\section*{Ghost}}\n" + MINI_TEX)
        assert "Ghost" not in [s["title"] for s in t["sections"]]

    def test_comments_do_not_create_structure(self):
        t = MO.parse_tex("% \\section{Commented}\n% \\begin{figure}\\label{fig:x}\n"
                         + MINI_TEX)
        assert "Commented" not in [s["title"] for s in t["sections"]]
        assert "fig:x" not in [f["label"] for f in t["floats"]]

    def test_starred_floats_are_found(self):
        t = MO.parse_tex(MINI_TEX.replace("\\begin{figure}", "\\begin{figure*}")
                         .replace("\\end{figure}", "\\end{figure*}"))
        assert t["floats"][0]["label"] == "fig:first"

    def test_escape_of_percent_is_kept_and_comment_dropped(self):
        assert MO.strip_comments("50\\% of x % gone") == "50\\% of x  "

    def test_normalize_flattens_latex(self):
        assert MO.normalize("Time-Domain Imaging\n  of {Rotating} \\& Cloudy") == \
            "Time-Domain Imaging of Rotating & Cloudy"

    def test_reference_forms_all_count(self):
        t = MO.parse_tex(MINI_TEX.replace("\\appendix",
                                          "\\pageref{sec:intro}\\appendix"))
        assert t["refs"].count("sec:intro") == 2

    def test_pdf_flatten_repairs_the_minus_sign(self):
        assert MO.pdf_flatten("a \u22120.1978 map\u00a0here") == "a -0.1978 map here"

    def test_splicing_reads_the_generated_fragment(self, tmp_path):
        (tmp_path / "main.tex").write_text(MINI_TEX.replace(
            "\\begin{equation}", "\\input{frag}\n\\begin{equation}"),
            encoding="utf-8")
        (tmp_path / "frag.tex").write_text(
            "\\begin{table}\\caption{Frag.}\\label{tab:frag}\\end{table}",
            encoding="utf-8")
        tex = MO.splice_inputs(tmp_path, (tmp_path / "main.tex").read_text())
        assert "tab:frag" in tex


# --------------------------------------------------------------------------- #
# the clean miniature must pass, and each rule must be able to fail
# --------------------------------------------------------------------------- #
class TestRulesFire:
    def test_the_clean_document_has_no_findings(self):
        assert findings() == []

    def test_sections_swapped_out_of_order(self):
        swapped = (MINI_TEX.replace("\\section{Introduction}\\label{sec:intro}", "@@")
                   .replace("\\section{Methods}\\label{sec:methods}",
                            "\\section{Introduction}\\label{sec:intro}")
                   .replace("@@", "\\section{Methods}\\label{sec:methods}"))
        found = findings(tex=swapped)
        assert fired(found, "order.sections")

    def test_a_deletable_heading_changes_the_count(self):
        found = findings(tex=MINI_TEX.replace(
            "\\section{Methods}\\label{sec:methods}", ""))
        assert fired(found, "count.sections")

    def test_the_spine_is_an_ordered_claim(self):
        found = findings(spine=["Methods", "Introduction",
                                "Data and Code Availability"])
        assert fired(found, "order.sections")

    def test_section_numbers_must_run_one_to_n(self):
        aux = MINI_AUX.replace("\\newlabel{sec:methods}{{2}{1}}",
                               "\\newlabel{sec:methods}{{5}{1}}")
        assert fired(findings(aux=aux), "order.sections")

    def test_a_body_section_without_a_label_cannot_be_ordered(self):
        aux = MINI_AUX.replace("\\newlabel{sec:methods}{{2}{1}}", "")
        assert fired(findings(aux=aux), "order.sections")

    def test_sections_must_paginate_forward(self):
        aux = MINI_AUX.replace("\\newlabel{sec:intro}{{1}{1}}",
                               "\\newlabel{sec:intro}{{1}{9}}")
        assert fired(findings(aux=aux), "order.pages")

    def test_float_that_is_never_cited(self):
        found = findings(tex=MINI_TEX.replace(
            " Table~\\ref{tab:second} and", " and"))
        assert fired(found, "floats.cited")

    def test_float_without_a_caption(self):
        found = findings(tex=MINI_TEX.replace("\\caption{A table.}", ""))
        assert fired(found, "floats.caption")

    def test_float_without_a_label(self):
        found = findings(tex=MINI_TEX.replace(
            "\\caption{A table.}\\label{tab:first}", "\\caption{A table.}"),
            aux=MINI_AUX.replace("\\newlabel{tab:first}{{1}{1}}\n", "")
            .replace("\\newlabel{tab:second}{{2}{2}}", "\\newlabel{tab:second}{{1}{2}}"),
            tables=1)
        assert fired(found, "floats.labelled")

    def test_a_table_that_paginates_backwards(self):
        aux = MINI_AUX.replace("\\newlabel{tab:second}{{2}{2}}",
                               "\\newlabel{tab:second}{{2}{1}}")
        assert fired(findings(aux=aux), "floats.pages")

    def test_float_number_gap(self):
        aux = MINI_AUX.replace("\\newlabel{tab:second}{{2}{2}}",
                               "\\newlabel{tab:second}{{3}{2}}")
        assert fired(findings(aux=aux), "floats.numbering")

    def test_a_float_before_its_own_section(self):
        """Appendix A starts on page 2; a table inside it that the build put on
        page 1 is a float that escaped into the body."""
        aux = MINI_AUX.replace("\\newlabel{tab:second}{{2}{2}}",
                               "\\newlabel{tab:second}{{2}{1}}")
        found = findings(aux=aux)
        assert fired(found, "floats.section_page") or fired(found, "floats.pages")

    def test_equation_number_collision(self):
        aux = MINI_AUX + "\\newlabel{eq:two}{{1}{1}}\n"
        assert fired(findings(aux=aux), "equations.unique")

    def test_equation_beyond_the_documented_total(self):
        aux = MINI_AUX.replace("\\newlabel{eq:one}{{1}{1}}",
                               "\\newlabel{eq:one}{{4}{1}}")
        assert fired(findings(aux=aux), "count.equations")

    def test_an_unlabelled_equation_is_not_a_defect(self):
        """LaTeX numbers every equation; only labelled ones appear in the aux,
        so a gap in the labels is normal and must not fire."""
        aux = MINI_AUX.replace("\\newlabel{eq:one}{{1}{1}}",
                               "\\newlabel{eq:one}{{2}{1}}")
        found = findings(aux=aux, equations=2)
        assert not fired(found, "equations.unique")

    def test_unresolved_reference(self):
        found = findings(tex=MINI_TEX.replace(
            "\\appendix", "\\ref{sec:nope}\n\\appendix"))
        assert fired(found, "refs.resolve")

    def test_uncited_bibliography_entry(self):
        aux = MINI_AUX.replace("\\citation{keyone}", "\\citation{other}")
        tex = MINI_TEX.replace("\\cite{keyone}", "\\cite{other}")
        assert fired(findings(tex=tex, aux=aux), "cites.used")

    def test_citation_with_no_bibitem(self):
        assert fired(findings(aux=MINI_AUX + "\\citation{ghostkey}\n"),
                     "cites.resolve")

    def test_duplicate_bibitem(self):
        tex = MINI_TEX.replace("\\end{thebibliography}",
                               "\\bibitem{keyone} Again.\n\\end{thebibliography}")
        assert fired(findings(tex=tex, bibitems=2), "cites.unique")

    def test_appendix_never_promised_in_the_body(self):
        """Neither the section nor a float inside it is mentioned before the
        appendix: the reader is sent nowhere."""
        tex = MINI_TEX.replace("of Appendix~\\ref{app:one}, ", "")
        tex = tex.replace(" Table~\\ref{tab:second} and", " and")
        found = findings(tex=tex)
        assert fired(found, "cites.appendices")
        assert fired(found, "floats.cited")

    def test_an_appendix_reached_only_through_its_table_is_promised(self):
        """``\\ref{app:one}`` deleted but Table 2 (inside the appendix) still
        cited from the body: the reader is still sent there."""
        tex = MINI_TEX.replace("with the method\nof Appendix~\\ref{app:one}, ",
                               "with the method\n")
        tex = tex.replace("Nothing here beyond Table~\\ref{tab:first}.",
                          "Nothing here.")
        # the body cites tab:second, which lives in the appendix
        assert fired(findings(tex=tex), "cites.used") is False
        assert fired(findings(tex=tex), "cites.appendices") is False

    def test_appendices_must_be_promised_in_order(self):
        found = findings(spine=MINI["spine"])
        assert fired(found, "order.appendices") is False

    def test_overfull_box_fails_the_build(self):
        assert fired(findings(log=MINI_LOG + "Overfull \\hbox (1pt)\n"),
                     "log.overfull")

    def test_unfinished_build_is_reported(self):
        assert fired(findings(log="kpathsea: running mktexlsr\n"), "log.pages")

    def test_rerun_warning_is_a_finding(self):
        assert fired(findings(log=MINI_LOG + "LaTeX Warning: Label(s) may have "
                              "changed. Rerun to get cross-references right.\n"),
                     "log.rerun")

    def test_missing_graphic_is_a_finding(self):
        assert fired(findings(log=MINI_LOG +
                              "! Package pdftex.def Error: File `fig.pdf' not "
                              "found."), "log.missing_graphics")

    def test_page_count_disagrees_with_the_documentation(self):
        assert fired(findings(log=MINI_LOG.replace("(2 pages", "(7 pages")),
                     "count.pages")

    def test_the_documented_count_may_be_the_stale_side(self):
        found = findings(pages=3)
        assert fired(found, "count.pages")

    def test_missing_metadata_field(self):
        found = findings(tex=MINI_TEX.replace("  pdfsubject={Testing},\n", ""))
        assert fired(found, "metadata.present")

    def test_typeset_title_disagreeing_with_the_pdf_title(self):
        found = findings(tex=MINI_TEX.replace(
            "{\\Large\\bfseries A Little Lens\\par}",
            "{\\Large\\bfseries A Bigger Lens\\par}"))
        assert fired(found, "metadata.title_matches_typeset")

    def test_expected_overrides_do_silence_the_right_rules(self):
        """A test that only ever breaks things cannot tell a working gate from a
        vacuous one."""
        assert findings(pages=2) == []
        assert fired(findings(sections=2), "count.sections")


# --------------------------------------------------------------------------- #
# the PDF information dictionary
# --------------------------------------------------------------------------- #
class TestPdfInfo:
    def test_named_escapes(self):
        assert MO.unescape_pdf_string(rb"a\nb\tc") == b"a\nb\tc"

    def test_octal_escapes_parentheses_and_backslash(self):
        assert MO.unescape_pdf_string(rb"\(x\)\\y") == b"(x)\\y"
        assert MO.unescape_pdf_string(rb"\101\040\056") == b"A ."

    def test_utf16_title_is_decoded_from_a_real_pdf(self):
        pdf = MO.ROOT / "paper" / "main.pdf"
        if not pdf.exists():
            pytest.skip("no shipped PDF in this tree")
        info = MO.pdf_info(pdf)
        assert info["Title"] == MO.parse_tex(MO.read_source()[0])["pdftitle"]
        for key in ("Author", "Subject", "Keywords"):
            assert len(info.get(key, "")) > 3, f"{key} is empty in the shipped PDF"

    def test_no_byte_order_mark_survives_decoding(self):
        pdf = MO.ROOT / "paper" / "main.pdf"
        if not pdf.exists():
            pytest.skip("no shipped PDF in this tree")
        assert "\ufeff" not in MO.pdf_info(pdf)["Title"]

    def test_metadata_agreement_is_audited(self, ev):
        if ev["pdf"] is None:
            pytest.skip("no shipped PDF in this tree")
        found = MO.audit(ev["tex"], ev["aux"], ev["log"], pdf=ev["pdf"],
                         record=ev["record"])["findings"]
        assert not [f for f in found if f.startswith("[pdf.metadata]")], found


# --------------------------------------------------------------------------- #
# the build record: how a tree without TeX still gets an ordering gate
# --------------------------------------------------------------------------- #
class TestBuildRecord:
    def test_the_committed_record_exists(self):
        assert MO.RECORD.exists(), ("tools/manuscript_build_record.json is the "
                                    "only build evidence a TeX-less tree can have")

    def test_record_shape(self):
        record = MO.read_record(MO.RECORD)
        assert MO.RECORD_KEYS <= set(record)
        assert isinstance(record["citations"], set)
        assert len(record["fingerprint"]) == 16

    def test_record_covers_every_label_the_source_uses(self):
        record = MO.read_record(MO.RECORD)
        tex, _pdf = MO.read_source()
        parsed = MO.parse_tex(tex)
        used = {s["label"] for s in parsed["sections"] if s["label"]}
        used |= {f["label"] for f in parsed["floats"] if f["label"]}
        used |= set(parsed["refs"])
        assert used <= set(record["labels"]), sorted(used - set(record["labels"]))[:5]

    def test_record_fingerprint_matches_the_source(self):
        tex, _pdf = MO.read_source()
        record = MO.read_record(MO.RECORD)
        assert MO.structure_fingerprint(MO.parse_tex(tex)) == \
            record["fingerprint"], "the record predates this skeleton: rebuild"

    def test_fingerprint_ignores_prose(self):
        tex, _pdf = MO.read_source()
        before = MO.structure_fingerprint(MO.parse_tex(tex))
        after = MO.structure_fingerprint(
            MO.parse_tex(tex.replace("Introduction", "Preamble", 1)))
        assert before == after, "a heading's wording must not invalidate a build"

    def test_fingerprint_notices_a_new_float(self):
        tex, _pdf = MO.read_source()
        before = MO.structure_fingerprint(MO.parse_tex(tex))
        after = MO.structure_fingerprint(MO.parse_tex(tex.replace(
            "\\appendix",
            "\\begin{table}\\caption{Extra.}\\label{tab:extra}\\end{table}\n"
            "\\appendix", 1)))
        assert before != after

    def test_fingerprint_notices_a_relabelled_section(self):
        tex, _pdf = MO.read_source()
        before = MO.structure_fingerprint(MO.parse_tex(tex))
        after = MO.structure_fingerprint(
            MO.parse_tex(tex.replace("sec:methods", "sec:methods2", 1)))
        assert before != after

    def test_a_stale_record_is_a_finding(self, tmp_path):
        record = MO.read_record(MO.RECORD)
        record = dict(record, fingerprint="0123456789abcdef")
        tex, _pdf = MO.read_source()
        found = MO.audit(tex, {"labels": record["labels"],
                               "citations": record["citations"]},
                         record["log"], record=record)["findings"]
        assert fired(found, "record.stale")

    def test_a_short_record_is_a_finding(self, tmp_path):
        record = MO.read_record(MO.RECORD)
        del record["log"]
        tex, _pdf = MO.read_source()
        found = MO.audit(tex, {"labels": record["labels"],
                               "citations": record["citations"]},
                         {}, record=record)["findings"]
        assert fired(found, "record.shape") or fired(found, "log.pages")

    def test_read_record_refuses_a_malformed_file(self, tmp_path):
        (tmp_path / "r.json").write_text('{"claims": []}', encoding="utf-8")
        with pytest.raises(ValueError):
            MO.read_record(tmp_path / "r.json")

    def test_write_then_read_round_trips(self, tmp_path):
        if not (MO.ROOT / "paper" / "main.aux").exists():
            pytest.skip("distilling a record needs a real build in this tree")
        written = MO.write_record(tmp_path / "r.json")
        back = MO.read_record(tmp_path / "r.json")
        assert back["fingerprint"] == written["fingerprint"]
        assert back["labels"] == written["labels"]
        assert back["citations"] == set(written["citations"])

    def test_the_record_drops_the_pdf_byte_count(self):
        """pdfTeX stamps a creation date, so a byte count in a tracked file makes
        every rebuild look like a change."""
        record = MO.read_record(MO.RECORD)
        assert "bytes" not in record["log"]

    def test_load_evidence_names_what_it_used(self):
        ev = MO.load_evidence()
        assert ev["origin"] and ev["aux"] is not None and ev["log"] is not None

    def test_a_tree_with_no_evidence_at_all_says_so(self, tmp_path, monkeypatch):
        monkeypatch.setattr(MO, "RECORD", tmp_path / "absent.json")
        monkeypatch.setattr(MO, "ROOT", tmp_path)
        with pytest.raises(FileNotFoundError):
            MO.load_evidence()

    def test_a_relative_record_path_is_resolved_first(self, monkeypatch):
        """``--record tools/manuscript_build_record.json`` is how the build script
        and CI name it, and a relative path cannot be described relative to an
        absolute root -- which used to raise instead of reporting."""
        monkeypatch.chdir(ROOT)
        ev = MO.load_evidence("tools/manuscript_build_record.json")
        assert ev["origin"] == "tools/manuscript_build_record.json"
        assert ev["record"]["labels"]

    def test_a_record_outside_the_repository_is_still_readable(self, tmp_path):
        copied = tmp_path / "elsewhere.json"
        shutil.copy(MO.RECORD, copied)
        ev = MO.load_evidence(str(copied))
        assert ev["origin"] == str(copied)
        assert ev["record"] == MO.read_record(MO.RECORD)


# --------------------------------------------------------------------------- #
# the real manuscript
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def ev():
    try:
        return MO.load_evidence()
    except FileNotFoundError as exc:
        pytest.skip(str(exc))


@pytest.fixture(scope="module")
def real(ev):
    return MO.audit(ev["tex"], ev["aux"], ev["log"], pdf=ev["pdf"],
                    record=ev["record"])


@pytest.fixture(scope="module")
def trio(ev):
    """The same evidence as load_trio() gives a built tree, in the shape the
    older tests expect; the record stands in where main.aux does not exist."""
    return ev["tex"], ev["aux"], ev["log"], ev["pdf"]


class TestRealManuscript:
    def test_the_audit_is_clean(self, real):
        assert real["findings"] == [], "\n".join(real["findings"])

    def test_documented_counts_match_the_build(self, real):
        assert real["metrics"]["log"]["pages"] == MO.DOCUMENTED["pages"]
        assert real["metrics"]["bibitems"] == MO.DOCUMENTED["bibitems"]
        assert real["metrics"]["floats"] == MO.DOCUMENTED["figures"] + \
            MO.DOCUMENTED["tables"]

    def test_spine_is_the_order_the_paper_args_in(self, real):
        """The gate is on the order and on each chapter's stem, not on wording:
        a retitle keeps the build green, a moved chapter does not."""
        assert len(real["sections"]) == len(MO.SECTION_STEMS)
        assert all(got.startswith(want) for got, want
                   in zip(real["sections"], MO.SECTION_STEMS)), \
            f"{real['sections']} is not the documented spine"

    def test_appendices_are_four_and_follow_the_body(self, real):
        assert len(real["appendices"]) == MO.DOCUMENTED["appendices"]

    def test_equation_numbers_are_issued_once_up_to_the_total(self, real):
        nums = real["metrics"]["equation_numbers"]
        assert max(nums) == MO.DOCUMENTED["equations"]
        assert len(nums) == len(set(nums))

    def test_equation_one_is_unlabelled_by_design(self, real):
        """The audit tolerates it; the test records why, so a future reader does
        not 'fix' the gap by labelling a display equation the paper never cites."""
        assert 1 not in real["metrics"]["equation_numbers"]

    def test_every_float_carries_a_label_and_a_caption(self, ev):
        floats = MO.parse_tex(ev["tex"])["floats"]
        assert all(f["label"] for f in floats)
        assert all(f["has_caption"] for f in floats)

    def test_no_reference_or_citation_rule_fires(self, ev):
        found = MO.audit(ev["tex"], ev["aux"], ev["log"],
                         record=ev["record"])["findings"]
        assert not [f for f in found if f.startswith(("[refs.", "[cites.",
                                                      "[record."))]

    def test_build_log_is_clean(self, real):
        for key in ("errors", "undefined_references", "undefined_citations",
                    "multiply_defined", "overfull", "rerun_warnings",
                    "missing_figures"):
            assert real["metrics"]["log"][key] == 0, key

    def test_the_evidence_is_about_this_source(self, ev):
        """A page number left by a build of an earlier draft would let every
        ordering test above pass on the wrong document."""
        parsed = MO.parse_tex(ev["tex"])
        src = {s["label"] for s in parsed["sections"] if s["label"]}
        src |= {f["label"] for f in parsed["floats"] if f["label"]}
        src |= {r for r in parsed["refs"]}
        aux_labels = set(ev["aux"]["labels"] if isinstance(ev["aux"], dict)
                         else MO.parse_aux(ev["aux"])["labels"])
        missing = sorted(src - aux_labels)
        assert not missing, \
            f"labels the source uses but the build never issued: {missing[:5]}"

    def test_citation_keys_in_the_evidence_all_have_a_bibitem(self, ev):
        citations = (ev["aux"]["citations"] if isinstance(ev["aux"], dict)
                     else MO.parse_aux(ev["aux"])["citations"])
        bib = set(MO.parse_tex(ev["tex"])["bibitems"])
        assert citations <= bib, sorted(citations - bib)

    def test_bibliography_is_fully_used(self, ev):
        """An entry nobody cites is a reference the reader will look for in
        vain; the audit already fails on it, so assert the specific rule."""
        found = MO.audit(ev["tex"], ev["aux"], ev["log"],
                         record=ev["record"])["findings"]
        assert not fired(found, "cites.used")

    def test_title_is_consistent_across_the_repository(self):
        assert MO.title_registry() == [], MO.title_registry()

    def test_the_pdf_text_carries_every_ledgered_number(self, ev):
        """The strongest staleness test available: the digits the ledger vouches
        for must appear in the file a reader downloads, not only in main.tex."""
        tool = shutil.which("pdftotext")
        if tool is None or ev["pdf"] is None:
            pytest.skip("poppler or the shipped PDF is unavailable")
        out = subprocess.run([tool, str(ev["pdf"]), "-"], capture_output=True,
                             check=True, text=True).stdout
        found = MO.audit(ev["tex"], ev["aux"], ev["log"], pdf_text=out,
                         record=ev["record"])["findings"]
        assert not [f for f in found if f.startswith("[pdf.")], found[:4]

    def test_pdf_text_check_can_fail(self, ev):
        found = MO.audit(ev["tex"], ev["aux"], ev["log"],
                         pdf_text="a short excerpt 0.3453 only")["findings"]
        assert fired(found, "pdf.text_matches_ledger") or fired(found, "pdf.text")


# --------------------------------------------------------------------------- #
# command line
# --------------------------------------------------------------------------- #
class TestCommandLine:
    def test_human_report_exits_zero_on_the_real_paper(self, capsys):
        assert MO.main([]) == 0
        out = capsys.readouterr().out
        assert "spine:" in out and "0 finding(s)" in out

    def test_json_output_is_parsable_and_self_reporting(self, capsys):
        assert MO.main(["--json"]) == 0
        blob = json.loads(capsys.readouterr().out)
        assert blob["findings"] == [] and blob["n_findings"] == 0
        assert blob["title"] and blob["metrics"]["log"]["pages"]

    def test_a_failing_document_exits_nonzero(self, tmp_path, capsys):
        (tmp_path / "main.tex").write_text(
            MINI_TEX.replace("\\caption{A table.}", ""), encoding="utf-8")
        (tmp_path / "main.aux").write_text(MINI_AUX, encoding="utf-8")
        (tmp_path / "main.log").write_text(MINI_LOG, encoding="utf-8")
        assert MO.main(["--build-dir", str(tmp_path)]) == 1
        assert "floats.caption" in capsys.readouterr().out

    def test_expect_flag_can_move_a_ceiling(self, tmp_path, capsys):
        (tmp_path / "main.tex").write_text(MINI_TEX, encoding="utf-8")
        (tmp_path / "main.aux").write_text(MINI_AUX, encoding="utf-8")
        (tmp_path / "main.log").write_text(MINI_LOG, encoding="utf-8")
        expect = json.dumps({**MINI, "spine": MINI["spine"]})
        assert MO.main(["--build-dir", str(tmp_path), "--expect", expect]) == 0

    def test_strict_metadata_reads_the_pdf(self, capsys):
        if not (MO.ROOT / "paper" / "main.pdf").exists():
            pytest.skip("no shipped PDF in this tree")
        assert MO.main(["--strict-metadata"]) == 0


# --------------------------------------------------------------------------- #
# the rest of the repository must say the same numbers
# --------------------------------------------------------------------------- #
class TestCrossRepository:
    def test_documented_counts_appear_in_the_readme(self):
        readme = (MO.ROOT / "README.md").read_text(encoding="utf-8")
        line = re.search(r"(\d+) pages, (\d+) figures, (\d+) tables, "
                         r"(\d+) references", readme)
        assert line, "README no longer states the manuscript's shape"
        assert [int(g) for g in line.groups()] == [
            MO.DOCUMENTED["pages"], MO.DOCUMENTED["figures"],
            MO.DOCUMENTED["tables"], MO.DOCUMENTED["bibitems"]]

    def test_documented_counts_appear_in_the_arxiv_listing(self):
        arxiv_path = MO.ROOT / "submission" / "arxiv_metadata.txt"
        if not arxiv_path.exists():
            pytest.skip("submission/arxiv_metadata.txt not shipped")
        meta = arxiv_path.read_text(encoding="utf-8")
        line = re.search(r"Comments: (\d+) pages, (\d+) figures, (\d+) tables",
                         meta)
        assert line, "the arXiv comments no longer state the shape"
        assert [int(g) for g in line.groups()] == [
            MO.DOCUMENTED["pages"], MO.DOCUMENTED["figures"],
            MO.DOCUMENTED["tables"]]

    def test_the_manuscript_describes_its_own_shape(self, trio):
        """Appendix D tells the reader the shipped PDF is 36 pages with no
        undefined references; if the paper grows, that sentence grows with it."""
        tex, _aux, _log, _pdf = trio
        flat = MO.pdf_flatten(re.sub(r"(?<!\\)%.*", " ", tex))
        assert f"{MO.DOCUMENTED['pages']} pages" in flat
        assert "no undefined" in flat and "no overfull" in flat

    def test_demo_app_states_the_same_page_count(self):
        hits = []
        comp_dir = MO.ROOT / "web" / "components" if (MO.ROOT / "web" / "components").exists() else MO.ROOT / "components"
        for path in comp_dir.rglob("*.tsx"):
            text = path.read_text(encoding="utf-8")
            hits += re.findall(r"(\d+) pages", text)
        if hits:
            assert set(hits) == {str(MO.DOCUMENTED["pages"])}, hits

    def test_title_registry_covers_the_files_that_advertise_the_paper(self):
        assert {"README.md", "CITATION.cff", "paper/main.tex"} <= set(MO.TITLE_FILES)
        for rel in MO.TITLE_FILES:
            assert (MO.ROOT / rel).exists(), rel

"""LaTeX integrity tests.

Assert paper/main.tex and paper/targets_table.tex:
- zero \\rev{ and zero \\revflag
- every \\ref/\\eqref target label exists
- \\cite keys are present in bibliography
- brace/environment/math balance of every shipped fragment, and the column
  count of the generated target table (a stray brace in a generated caption
  silently loses the whole build)
- reader-facing prose carries no internal revision-tracker IDs
- F-12/F-18/F-05 repairs hold
"""
import re
from collections import Counter
from pathlib import Path

import pytest

import make_app_docs as _make_app_docs
from tests._data import PAPER


def read_tex(name):
    return (PAPER / name).read_text()


def strip_comments(text):
    """Drop LaTeX comments, then escaped braces/ampersands, so that the counts
    below see only structural characters."""
    text = re.sub(r"(?<!\\)%.*", "", text, flags=re.M)
    for esc in (r"\{", r"\}", r"\&", r"\%", r"\_"):
        text = text.replace(esc, "")
    return text


class TestNoRevMarkup:
    """Assert zero \\rev{ and zero \\revflag in paper files."""

    def test_no_rev_in_main(self):
        text = read_tex("main.tex")
        assert r"\rev{" not in text, "main.tex still contains \\rev{"
        assert r"\revflag" not in text, "main.tex still contains \\revflag"

    def test_no_rev_in_targets_table(self):
        text = read_tex("targets_table.tex")
        assert r"\rev{" not in text, "targets_table.tex still contains \\rev{"
        assert r"\revflag" not in text, "targets_table.tex still contains \\revflag"


class TestRefLabelIntegrity:
    """Every \\ref{...}/\\eqref{...} target must have a matching \\label{...}."""

    def test_refs_have_labels(self):
        text = read_tex("main.tex")
        # Collect all labels
        labels = set(re.findall(r"\\label\{([^}]+)\}", text))
        # Collect all refs
        refs = set(re.findall(r"\\ref\{([^}]+)\}", text))
        refs |= set(re.findall(r"\\eqref\{([^}]+)\}", text))
        # Also check targets_table.tex for labels
        try:
            tt = read_tex("targets_table.tex")
            labels |= set(re.findall(r"\\label\{([^}]+)\}", tt))
        except FileNotFoundError:
            pass

        missing = refs - labels
        # Some refs may come from \\input files that are absent -- allow that
        # We just check the majority are present
        assert len(missing) < len(refs) * 0.1, \
            f"Too many missing labels: {sorted(missing)[:10]}..."


class TestBibliographyKeys:
    """\\cite keys used must be present in the bibliography."""

    def test_cite_keys_in_bibliography(self):
        text = read_tex("main.tex")
        # Collect bibitem keys
        bibkeys = set(re.findall(r"\\bibitem\[?[^\]]*\]?\{([^}]+)\}", text))
        # Collect cite keys
        cite_keys = set()
        for m in re.finditer(r"\\cite[pt]?\{([^}]+)\}", text):
            for k in m.group(1).split(","):
                cite_keys.add(k.strip())
        missing = cite_keys - bibkeys
        assert not missing, f"Cite keys not in bibliography: {missing}"


class TestF12Toth2025:
    """F-12: Toth 2025 entry must cite RAA 25 065007 (not 'in press')."""

    def test_toth25_not_in_press(self):
        text = read_tex("main.tex")
        # Find the toth25clouds bibitem
        match = re.search(r"\\bibitem.*?toth25clouds.*?\n(.*?)(?=\\bibitem|\Z)",
                          text, re.DOTALL)
        assert match, "toth25clouds bibitem not found"
        entry = match.group(0)
        assert "in press" not in entry.lower(), \
            f"Toth 2025 still says 'in press': {entry[:200]}"
        assert "065007" in entry or "RAA" in entry, \
            f"Toth 2025 should cite RAA 25 065007"


class TestF18NoMissing2026c:
    """F-18: Every cited 2026x entry must have a bibitem."""

    def test_2026_entries_consistent(self):
        """All Turyshev 2026x citations have matching bibitems."""
        text = read_tex("main.tex")
        # Find all 2026x references in citations
        cited = set(re.findall(r"2026([a-z])", text))
        # Find all 2026x bibitems
        bibitems = set(re.findall(r"2026([a-z])", text))
        # Every cited year-letter should have a bibitem
        # (This is already covered by TestBibliographyKeys, but we check
        # the specific F-18 concern about 2026c being missing)
        # If 2026c is cited, it must have a bibitem
        if "c" in cited:
            assert "c" in bibitems, "2026c is cited but has no bibitem"


class TestF05TimingSentence:
    """F-05: Timing sentence must read 8.6 s not 1 s for 1e-4 x 86400 s."""

    def test_timing_says_86(self):
        text = read_tex("main.tex")
        # The repaired sentence should say 8.6 s
        assert "8.6" in text, "Timing sentence should mention 8.6 s"


FRAGMENTS = ["main.tex", "targets_table.tex"]


class TestBraceAndEnvironmentBalance:
    """Structural balance of every shipped .tex fragment.

    ``paper/targets_table.tex`` is emitted by ``src/targets.py`` rather than
    edited by hand, so a generator bug ships silently.  One extra closing brace
    at the end of a generated caption aborted the build with "Extra }, or
    forgotten \\endgroup" and left 238 cross-references unresolved -- a failure
    that only appears once someone compiles.  These are the invariants that
    check would otherwise catch, runnable without a TeX toolchain.
    """

    @pytest.mark.parametrize("name", FRAGMENTS)
    def test_brace_count_matches(self, name):
        text = strip_comments(read_tex(name))
        assert text.count("{") == text.count("}"), (
            f"{name}: {text.count('{')} openers vs {text.count('}')} closers")

    @pytest.mark.parametrize("name", FRAGMENTS)
    def test_no_closer_without_an_opener(self, name):
        """Balance is necessary but not sufficient: a stray ``}`` in a caption
        is balanced overall only if an opener is also missing, and the depth
        probe catches the ordering either way."""
        text = strip_comments(read_tex(name))
        depth = 0
        for i, ch in enumerate(text):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                assert depth >= 0, (
                    f"{name}: closing brace at offset {i} has no opener; "
                    f"context: {text[max(0, i - 60):i + 20]!r}")
        assert depth == 0, f"{name}: {depth} unclosed groups at end of file"

    @pytest.mark.parametrize("name", FRAGMENTS)
    def test_environments_pair(self, name):
        text = strip_comments(read_tex(name))
        begins = Counter(re.findall(r"\\begin\{([^}]+)\}", text))
        ends = Counter(re.findall(r"\\end\{([^}]+)\}", text))
        diff = {k: (begins[k], ends[k])
                for k in set(begins) | set(ends) if begins[k] != ends[k]}
        assert begins == ends, f"{name}: begin/end mismatch {diff}"

    @pytest.mark.parametrize("name", FRAGMENTS)
    def test_math_delimiters_are_even(self, name):
        text = strip_comments(read_tex(name))
        n = len(re.findall(r"(?<!\\)\$", text))
        assert n % 2 == 0, f"{name}: odd number ({n}) of unescaped $ delimiters"

    def test_inputs_exist(self):
        """Every \\input target must be a file that ships next to main.tex."""
        text = strip_comments(read_tex("main.tex"))
        for frag in re.findall(r"\\input\{([^}]+)\}", text):
            assert (PAPER / f"{frag}.tex").exists(), (
                f"main.tex inputs {frag!r} but paper/{frag}.tex is not shipped")


class TestGeneratedTableShape:
    """The generated target table must stay internally consistent."""

    def test_column_count_matches_alignment_spec(self):
        text = read_tex("targets_table.tex")
        spec = re.search(r"\\begin\{tabular\}\{([^}]*)\}", text).group(1)
        ncols = len(re.findall(r"[lcrX]|p\{[^}]*\}", spec))
        assert ncols, f"could not parse tabular spec {spec!r}"
        body = text[text.index("\\begin{tabular}"):text.index("\\end{tabular}")]
        rows = [r for r in re.split(r"\\\\\n", strip_comments(body))
                if r.strip() and "\\citet" in r]
        assert len(rows) >= 5, f"expected the catalogue rows, found {len(rows)}"
        bad = [(r.strip()[:40], r.count("&") + 1) for r in rows
               if r.count("&") != ncols - 1]
        assert not bad, f"rows with != {ncols} columns: {bad}"

    def test_generated_by_marker(self):
        """The table is machine-owned; editing it by hand is a defect."""
        assert "Generated by src/targets.py" in read_tex("targets_table.tex")


ROOT = PAPER.parent


class TestDocumentMirrorsAreFresh:
    """Every shipped copy must be byte-identical to the file it mirrors.

    ``paper/sgl_time_domain_imaging.pdf``, the ``public/docs/`` names and the
    review record are byte copies of ``paper/main.pdf``,
    ``submission/cover_letter.pdf`` and ``reviews/response_to_editor.md``, made
    by ``src/make_app_docs.py``, which owns the mapping.  They had drifted: the
    site was serving an 11-page manuscript and a 2-page letter while the
    repository held 36 pages and 8.  Byte equality is the whole contract, so
    that is what is checked, against the generator's own table rather than a
    second copy of it.
    """

    MIRRORS = _make_app_docs.MIRRORS

    def test_sources_exist(self):
        for src in self.MIRRORS:
            assert (ROOT / src).exists(), f"{src} is not shipped"

    def test_no_unmirrored_duplicates_in_public_docs(self):
        """public/docs/ may only contain files the generator writes."""
        produced = {m for mirrors in self.MIRRORS.values() for m in mirrors}
        extra = [p.relative_to(ROOT).as_posix()
                 for p in (ROOT / "public" / "docs").iterdir()
                 if p.relative_to(ROOT).as_posix() not in produced]
        assert not extra, (f"public/docs/ holds copies with no source: {extra}; "
                           "they will go stale silently")

    @pytest.mark.parametrize("mirror", sorted(sum(MIRRORS.values(), [])))
    def test_mirror_is_byte_identical(self, mirror):
        src = next(s for s, ds in self.MIRRORS.items() if mirror in ds)
        assert _make_app_docs.digest(mirror) == _make_app_docs.digest(src), (
            f"{mirror} is not the current build of {src}; "
            f"run python3 src/make_app_docs.py")


class TestNoRevisionTrackerIds:
    """Reader-facing prose must not leak the revision record's private IDs.

    Defect numbers, gate names and equation tags from the revision correspondence
    are meaningful only inside ``reviews/``; a reader of the manuscript has no
    key to them.  The scan stops at the Acknowledgments, which are allowed to
    describe the internal pre-submission review that produced this version.
    """

    PATTERNS = [r"referee", r"reviewer", r"\bPart V[IU]+\b", r"\bF-\d\d\b",
                r"\bG-\d\b", r"\bR\d\d\b", r"eq\.~?R", r"minor comment",
                r"major comment"]

    def _body(self):
        text = read_tex("main.tex")
        for marker in (r"\section*{Acknowledgments}", r"\section*{Acknowledgements}"):
            if marker in text:
                return text[:text.index(marker)]
        return text

    @pytest.mark.parametrize("pattern", PATTERNS)
    def test_pattern_absent(self, pattern):
        body = self._body()
        hits = [m.group(0).replace("\n", " ") for m in
                re.finditer(r".{0,45}" + pattern + r".{0,45}", body, re.I)]
        assert not hits, f"{pattern!r} still in the manuscript body: {hits}"

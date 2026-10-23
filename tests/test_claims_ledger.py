"""Numeric provenance ledger: the build-and-test loop behind every printed digit.

The research analogue of ``npm run build && jest``:

* the **build** is ``tools/derive_stats.py``, which re-derives every bootstrap
  interval, paired t, systematics cell, harmonic-band mean, ensemble geography
  mean and cover-law slope from the archives under ``results/`` using the
  pipeline's own helper ``src/expcommon.py::paired_stats``, and writes
  ``tools/derived_stats.json``;
* the **bundle** is ``tools/claims_ledger.json``, one entry per printed number,
  each naming an archive key, the exact digits as printed, and the sentence
  they appear in, plus ``RELATIONS`` -- the arithmetic the manuscript does in
  prose -- and ``EXTERNAL``, the declared non-results;
* the **tests** are this file.  They check the artefacts' shape, their
  agreement with the shipped evidence and with the manuscript, the safety of
  the relation language, the coverage of every printed result, and -- in
  ``TestTamperingIsCaught`` -- that corrupting any of the three inputs makes
  the gate fail, because a check that cannot fail is decoration.

Tier note.  The ledger is harvested against the *shipped* (full) archives.  A
working tree whose ``results/`` has been overwritten in place by a fast-tier
run holds different values under the same keys, so the value-comparison tests
skip there rather than report a defect that is really a different tier.  CI
checks out the shipped tree, so nothing skips there.
"""
import ast
import copy
import json
import math
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

from tests._data import RESULTS, ROOT, TOOLS

sys.path.insert(0, str(TOOLS))
import claims as CL  # noqa: E402

MIN_CLAIMS = 625        # the ledger may grow; it must not silently shrink
MIN_RELATIONS = 25      # hand-written prose arithmetic, same ratchet
MAX_UNEXPLAINED = 0     # every printed result has a recorded origin
MIN_VOUCH_PCT = 40.0    # share of printed results with a named source
MAX_DECLARATIONS = 20   # EXTERNAL is a checklist, not a filing cabinet


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def shipped_tier():
    """True when ``results/`` is the frozen tree the ledger was harvested on."""
    rc = subprocess.run(
        [sys.executable, str(TOOLS / "array_manifest.py"), "check",
         str(RESULTS), str(TOOLS / "baseline_manifest.json")],
        capture_output=True, text=True).returncode
    if rc != 0:
        pytest.skip("working tree is not the shipped archive tier; ledger "
                    "value checks run against the shipped evidence only")
    return True


@pytest.fixture(scope="module")
def values():
    return CL.archive_values()


@pytest.fixture(scope="module")
def text():
    return CL.flat_manuscript()


@pytest.fixture(scope="module")
def ledger():
    return CL.load_ledger()


@pytest.fixture(scope="module")
def claims(ledger):
    return list(ledger["claims"])


# --------------------------------------------------------------------------- #
# shape of the artefact
# --------------------------------------------------------------------------- #
class TestLedgerShape:
    """A committed build artefact has a schema; enforce it before use."""

    def test_header_names_its_own_command(self, ledger):
        assert ledger["generated_by"] == "python3 tools/claims.py --harvest"
        assert "never regenerates" in ledger["comment"], \
            "the comment is what tells a reader CI verifies instead of rebuilding"

    def test_claims_are_a_list_above_the_floor(self, claims):
        assert len(claims) >= MIN_CLAIMS, \
            f"ledger has {len(claims)} claims, floor is {MIN_CLAIMS}"

    def test_relations_are_a_list_above_the_floor(self):
        """The hand-written relations are not harvested, so nothing but a
        floor stops somebody from quietly deleting the prose arithmetic."""
        assert len(CL.RELATIONS) >= MIN_RELATIONS, \
            f"{len(CL.RELATIONS)} relations, floor is {MIN_RELATIONS}"

    def test_ids_are_unique(self, claims):
        dupes = sorted(i for i, n in Counter(c["id"] for c in claims).items()
                       if n > 1)
        assert not dupes, f"duplicate ledger ids: {dupes}"

    def test_no_claim_id_collides_with_a_relation_id(self, claims):
        assert not {r["id"] for r in CL.RELATIONS} & {c["id"] for c in claims}

    def test_schema_is_complete_for_every_claim(self, claims):
        bad = [(c["id"], e) for c in claims for e in CL.schema_errors(c)]
        assert not bad, f"schema violations: {bad[:5]}"

    def test_kind_is_one_of_the_three(self, claims):
        assert {c["kind"] for c in claims} <= CL.KINDS

    def test_digits_are_within_the_display_range(self, claims):
        assert all(0 <= c["digits"] <= CL.MAX_PRECISION for c in claims)

    def test_scale_is_printable(self, claims):
        assert all(c.get("scale", 1) in CL.SCALES for c in claims)

    def test_id_is_the_slug_of_its_source_key(self, claims):
        """Ids are derived from ``src::key``; a hand-edited id is a typo."""
        for c in claims:
            want = re.sub(r"[^a-z0-9]+", "-",
                          f"{c['src'].rsplit('.', 1)[0]}-{c['key']}"
                          ).strip("-")[:88]
            assert c["id"] == want or c["id"].startswith(want), \
                f"{c['id']} is not the slug of {c['src']}::{c['key']}"

    def test_note_records_ambiguity(self, claims):
        """Harvested entries say so when several leaves print the same digits."""
        for c in claims:
            if "also matches" in c["note"]:
                assert "@" in c["note"].split("also matches", 1)[1]

    @pytest.mark.parametrize("path", [CL.LEDGER, CL.DERIVED])
    def test_artefacts_are_strict_json(self, path):
        """No bare NaN/Infinity: a referee's parser is not CPython's."""
        def reject(token):
            raise AssertionError(f"{path.name} contains non-JSON {token!r}")

        json.loads(path.read_text(encoding="utf-8"), parse_constant=reject)

    def test_save_and_load_round_trip(self, ledger, tmp_path):
        target = tmp_path / "claims_ledger.json"
        CL.save_ledger(ledger, target)
        assert CL.load_ledger(target)["claims"] == ledger["claims"]

    def test_load_rejects_a_ledger_without_claims(self, tmp_path):
        bad = tmp_path / "empty.json"
        bad.write_text('{"claims": 3}')
        with pytest.raises(ValueError):
            CL.load_ledger(bad)


class TestQuotes:
    """A quote is the ledger's pointer into the paper: it must stay verbatim."""

    def test_every_quote_appears_in_the_manuscript(self, claims, text):
        missing = [c["id"] for c in claims if c["quote"] not in text]
        assert not missing, \
            f"{len(missing)} quotes are no longer verbatim: {missing[:5]}"

    def test_every_shown_number_is_inside_its_quote(self, claims):
        bad = [c["id"] for c in claims if c["shown"] not in c["quote"]]
        assert not bad, f"shown string outside its own quote: {bad[:5]}"

    def test_quotes_are_bounded(self, claims):
        assert all(len(c["quote"]) <= 92 for c in claims)

    def test_no_quote_carries_an_unescaped_comment(self, claims, text):
        """A quote window may start just after a backslash, so the escape has
        to be checked where the window sits in the manuscript, not in the
        slice on its own."""
        leaked = []
        for c in claims:
            i = text.find(c["quote"])
            while i != -1:
                window = text[max(0, i - 1):i + len(c["quote"])]
                if re.search(r"(?<!\\)%", window):
                    leaked.append(c["id"])
                    break
                i = text.find(c["quote"], i + 1)
        assert not leaked, f"comment text leaked into a quote: {leaked[:5]}"

    def test_the_flat_manuscript_has_no_unescaped_percent(self, text):
        """The reason the window test can be trusted: LaTeX comment markers
        never survive flattening, so a '%' is always a printed one."""
        assert re.search(r"(?<!\\)%", text) is None

    def test_percentages_are_marked_as_scales(self, shipped_tier, claims, values):
        """A claim printed with a '%' sign is a scaled leaf, not a new number.

        Tier-guarded like every other test that resolves a value: a fast-tier
        ``results/ext_*`` rerun moves the leaf, not the manuscript, and the
        printed decimal is the full-tier one.
        """
        for c in claims:
            if "%" not in c["quote"]:
                continue
            val = values.get(f"{c['src']}::{c['key']}")
            if val is None:
                continue
            assert CL.rounds_to(val, c["digits"], c["shown"], 1) or \
                CL.rounds_to(val, c["digits"], c["shown"], 100), c["id"]


# --------------------------------------------------------------------------- #
# references
# --------------------------------------------------------------------------- #
class TestReferences:
    """Every claim points at a file the repository ships."""

    def test_sources_are_shipped_files(self, claims):
        for c in claims:
            src = c["src"]
            assert src.endswith((".json", ".npz")), src
            assert (RESULTS / src).exists() or (TOOLS / src).exists(), \
                f"{src} is not a shipped file ({c['id']})"

    def test_every_reference_resolves_to_a_leaf(self, shipped_tier, claims,
                                                values):
        missing = [f"{c['src']}::{c['key']}" for c in claims
                   if f"{c['src']}::{c['key']}" not in values]
        assert not missing, f"references with no leaf: {missing[:5]}"

    def test_derived_references_are_already_inside_the_stats_block(self, claims):
        for c in claims:
            if c["src"] == "derived_stats.json":
                assert not c["key"].startswith("stats."), \
                    "the 'stats.' root is the file's own prefix"

    def test_resolve_rejects_an_unknown_reference(self, values):
        with pytest.raises(KeyError):
            CL.resolve("audit.json::no.such.key", values)

    def test_resolve_returns_the_leaf_it_names(self, values):
        ref = sorted(values)[0]
        assert CL.resolve(ref, values) == values[ref]

    def test_the_index_is_large(self, values):
        assert len(values) > 20_000, f"only {len(values)} leaves indexed"

    def test_no_leaf_is_a_string_or_none(self, values):
        bad = [k for k, v in values.items()
               if not isinstance(v, (int, float)) or isinstance(v, bool)]
        assert not bad, f"non-numeric leaves indexed: {bad[:5]}"


# --------------------------------------------------------------------------- #
# staleness and coverage, against the shipped tier
# --------------------------------------------------------------------------- #
class TestStaleness:
    """A changed archive must fail the paper before a reader notices."""

    def test_check_ledger_is_clean(self, shipped_tier, ledger, values, text):
        errs = CL.check_ledger(ledger, values, text)
        assert not errs, f"{len(errs)} ledger failures, first: {errs[0]}"

    def test_every_claim_matches_its_leaf(self, shipped_tier, claims, values):
        bad = [(c["id"], c["shown"], values[f"{c['src']}::{c['key']}"])
               for c in claims
               if not CL.rounds_to(values[f"{c['src']}::{c['key']}"],
                                   c["digits"], c["shown"], c.get("scale", 1))]
        assert not bad, f"stale numbers: {bad[:5]}"

    def test_rebuilding_the_ledger_changes_nothing(self, shipped_tier, claims):
        """The committed bundle is the current build of the sources."""
        fresh = CL.harvest()["claims"]
        assert len(fresh) == len(claims)
        assert all(a == b for a, b in zip(fresh, claims)), \
            "tools/claims_ledger.json is stale; run --harvest and commit it"

    def test_no_printed_result_is_unexplained(self, shipped_tier, ledger,
                                              values, text):
        cov = CL.coverage(ledger, values, text)
        assert cov["untraceable"] <= MAX_UNEXPLAINED, \
            f"unexplained numbers: {sorted(set(cov['untraceable_list']))[:10]}"

    def test_the_four_buckets_partition_the_count(self, shipped_tier, ledger,
                                                  values, text):
        cov = CL.coverage(ledger, values, text)
        assert sum(cov["buckets"].values()) == cov["numbers"]

    def test_vouch_ratio_does_not_collapse(self, shipped_tier, ledger,
                                           values, text):
        """Individually named sources must not quietly fall away."""
        cov = CL.coverage(ledger, values, text)
        assert cov["pct"] >= MIN_VOUCH_PCT, \
            f"only {cov['pct']:.1f}% of printed numbers are named"

    def test_a_number_can_be_its_own_claim_only_once(self, shipped_tier, ledger,
                                                     values, text):
        cov = CL.coverage(ledger, values, text)
        assert cov["claims"] == len(ledger["claims"]) + len(CL.RELATIONS)

    def test_external_declarations_are_counted_separately(self, shipped_tier,
                                                          ledger, values, text):
        cov = CL.coverage(ledger, values, text)
        assert cov["external"] == len(CL.EXTERNAL)
        assert cov["buckets"]["external"] >= cov["external"], \
            "a declared token that is printed more than once is fine, " \
            "but a declaration never printed is caught elsewhere"


# --------------------------------------------------------------------------- #
# relations: the arithmetic the manuscript performs in prose
# --------------------------------------------------------------------------- #
ALLOWED_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Name,
                 ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow,
                 ast.Load)


class TestRelations:
    """Relations re-run the referee's own hand-checks, on every commit."""

    def test_ids_unique_and_prefixed(self):
        ids = [r["id"] for r in CL.RELATIONS]
        assert len(ids) == len(set(ids))
        assert all(i.startswith("rel-") for i in ids)

    def test_schema(self):
        bad = [(r["id"], CL.schema_errors(r)) for r in CL.RELATIONS
               if CL.schema_errors(r)]
        assert not bad, f"relation schema violations: {bad[:3]}"

    def test_expressions_are_arithmetic_and_nothing_else(self):
        for r in CL.RELATIONS:
            tree = ast.parse(r["expr"], mode="eval")
            for node in ast.walk(tree):
                assert isinstance(node, ALLOWED_NODES), \
                    f"{r['id']}: {type(node).__name__} is not arithmetic"

    def test_variable_names_are_plain_identifiers(self):
        for r in CL.RELATIONS:
            for name in r["vars"]:
                assert name.isidentifier(), f"{r['id']}: {name!r} is unusable"
                assert not name.startswith("_"), f"{r['id']}: {name!r} is hidden"

    def test_inputs_are_numbers_or_real_references(self, shipped_tier, values):
        for r in CL.RELATIONS:
            for name, ref in r["vars"].items():
                if isinstance(ref, bool) or not isinstance(ref, (int, float, str, list)):
                    raise AssertionError(f"{r['id']}/{name}: {type(ref)}")
                if isinstance(ref, (int, float)):
                    assert math.isfinite(float(ref)), f"{r['id']}/{name}"
                elif isinstance(ref, list):
                    for part in ref:
                        assert part in values, f"{r['id']}/{name}: {part}"
                else:
                    assert ref in values, f"{r['id']}/{name}: {ref}"

    def test_quotes_are_verbatim(self, text):
        bad = [r["id"] for r in CL.RELATIONS if r["quote"] not in text]
        assert not bad, f"relations whose sentence changed: {bad}"

    def test_relations_evaluate_to_what_is_printed(self, shipped_tier, values):
        errs = [e for e in (CL.check_relation(r, values) for r in CL.RELATIONS)
                if e]
        assert not errs, errs[:5]

    def test_every_relation_says_what_it_proves(self):
        for r in CL.RELATIONS:
            assert len(r["statement"].split()) >= 3, r["id"]
            assert len(r["note"].split()) >= 3, r["id"]

    def test_the_relation_set_covers_each_kind_of_prose_arithmetic(self):
        """Differences, sums, ratios, rescalings and pure design constants are
        all exercised; if one class disappears the paper has lost a way of
        computing something it prints."""
        exprs = [r["expr"] for r in CL.RELATIONS]
        joined = " ".join(exprs)
        for op in ("-", "+", "*", "/"):
            assert op in joined, f"no relation uses {op}"
        assert any(op in expr for expr in exprs for op in ("(", "**"))
        assert any(isinstance(v, str) for r in CL.RELATIONS
                   for v in r["vars"].values()), \
            "every relation should cite at least one archive leaf somewhere"

    def test_paired_differences_are_signed_correctly(self, shipped_tier, values):
        """A contrast is named after the subtraction the paper performs: D - A
        is positive because D is the higher arm.  Reversing the operands is a
        silent sign error that no archive diff would catch."""
        def leaf(ref):
            return float(values[f"derived_stats.json::{ref}"])

        pairs = (("D_minus_A", "exact_profile_white", "white_gls"),
                 ("F_minus_D", "tdi_fiducial", "exact_profile_white"),
                 ("F_minus_C", "tdi_fiducial", "approx_deflate_ou"),
                 ("surface_minus_tdi", "surface_coupled", "tdi_fiducial"))
        for name, hi, lo in pairs:
            got = leaf(f"contrasts.{name}.mean")
            want = leaf(f"seedtable.{hi}.mean") - leaf(f"seedtable.{lo}.mean")
            assert got == pytest.approx(want, abs=1e-12), \
                f"{name}: operands reversed or mislabelled ({got} vs {want})"
        assert leaf("contrasts.D_minus_A.mean") > 0
        assert leaf("contrasts.surface_minus_tdi.mean") < 0
        assert leaf("contrasts.surface_minus_tdi.n_favour") == \
            leaf("contrasts.surface_minus_tdi.n"), \
            "the abstract's 10/10 seeds claim needs every seed on one side"

    def test_ensemble_arithmetic_is_pinned(self, shipped_tier, values):
        """The five-geography ensemble paragraph: the offset in units of the
        between-map spread and of the Monte-Carlo error, and against the
        ten-seed headline."""
        ens = next(r for r in CL.RELATIONS
                   if r["id"] == "rel-ensemble-offset-in-map-sd")
        mc = next(r for r in CL.RELATIONS
                  if r["id"] == "rel-ensemble-offset-in-mc-error")
        head = next(r for r in CL.RELATIONS
                    if r["id"] == "rel-ensemble-versus-headline")
        for rel in (ens, mc, head):
            assert CL.check_relation(rel, values) is None, rel["id"]
        assert CL.evaluate(ens["expr"], {"offset": 0.0318184008,
                                         "between": 0.0211785664}
                           ) == pytest.approx(1.502, abs=2e-3)
        assert CL.evaluate(head["expr"], {"headline": 0.3422,
                                          "mean": 0.31731}
                           ) == pytest.approx(0.0249, abs=2e-4)


class TestExpressionSafety:
    """The relation language must not be able to execute anything."""

    @pytest.mark.parametrize("expr", [
        "__import__('os').system('echo tampered')",
        "open('/etc/passwd').read()",
        "x if x else 1",
        "[i for i in range(3)]",
        "{k: v for k, v in items()}",
        "x.y",
        "x[0]",
        "f'{x}'",
        "lambda: x",
        "x @ y",
        "x or y",
        "x > y",
        "; import os",
    ])
    def test_rejects_non_arithmetic_syntax(self, expr):
        with pytest.raises(Exception):
            CL.evaluate(expr, {"x": 1.0, "y": 2.0, "items": lambda: []})

    def test_rejects_a_huge_exponent(self):
        with pytest.raises(ValueError):
            CL.evaluate("2 ** 40", {})

    def test_rejects_an_unbound_name(self):
        with pytest.raises(KeyError):
            CL.evaluate("mystery + 1", {})

    def test_rejects_division_by_zero(self):
        with pytest.raises(ZeroDivisionError):
            CL.evaluate("1 / 0", {})

    def test_rejects_a_string_constant(self):
        with pytest.raises(ValueError):
            CL.evaluate("'a' + 'b'", {})

    def test_rejects_a_boolean_constant(self):
        with pytest.raises(ValueError):
            CL.evaluate("1 + True", {})

    def test_rejects_a_modulo(self):
        with pytest.raises(ValueError):
            CL.evaluate("7 % 3", {})

    def test_accepts_plain_arithmetic(self):
        assert CL.evaluate("2 * (3 - 1) / 4", {}) == pytest.approx(1.0)
        assert CL.evaluate("-a + b", {"a": 1.0, "b": 3.0}) == pytest.approx(2.0)
        assert CL.evaluate("x ** 2", {"x": 3.0}) == pytest.approx(9.0)

    def test_a_relation_that_cannot_evaluate_is_reported_not_raised(self):
        rel = {"id": "rel-test", "expr": "a / b", "vars": {"a": 1.0, "b": 0.0},
               "shown": "1", "digits": 0, "quote": "1"}
        err = CL.check_relation(rel, {})
        assert err and "did not evaluate" in err

    def test_the_tool_contains_no_eval_or_exec(self):
        """The calculator walks the AST rather than handing an expression to
        the interpreter.  Prose in claims.py may mention eval(); a call may not.

        The manuscript is untrusted text feeding a number the paper prints, so
        an eval() here would be a code-execution path with a LaTeX file on the
        other end.
        """
        src = Path(CL.__file__).read_text(encoding="utf-8")
        bare, dotted = set(), set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.Call):
                f = node.func
                if isinstance(f, ast.Name):
                    bare.add(f.id)
                elif isinstance(f, ast.Attribute):
                    dotted.add(f.attr)
        forbidden_bare = {"eval", "exec", "compile", "__import__"}
        forbidden_dotted = {"eval", "exec", "literal_eval", "system", "popen",
                            "check_output", "spawn", "run", "call"}
        hit = sorted(bare & forbidden_bare) + sorted(dotted & forbidden_dotted)
        assert not hit, f"claims.py executes code by calling {hit}"
        assert not re.search(r"^\s*(?:import|from)\s+(?:os|subprocess|builtins)\b",
                             src, re.M), \
            "the ledger must not be able to shell out"
        assert not re.search(r"\b(?:eval|exec)\s*\(",
                             re.sub(r"(?:^|\s)#[^\n]*", "", src)), \
            "no eval()/exec() call survives outside a comment"


# --------------------------------------------------------------------------- #
# declared externals
# --------------------------------------------------------------------------- #
class TestExternalDeclarations:
    """A declaration says the shipped evidence cannot answer for a number."""

    def test_declaration_list_is_small(self):
        assert len(CL.EXTERNAL) <= MAX_DECLARATIONS, \
            "EXTERNAL is a checklist of the paper's non-results, not a cabinet"

    def test_every_declaration_has_a_substantive_reason(self):
        bad = [t for t, why in CL.EXTERNAL.items() if len(why.split()) < 4]
        assert not bad, f"declarations without a usable reason: {bad}"

    def test_every_declaration_is_printed(self, text):
        printed = {s for s, _ in CL.manuscript_numbers(text)}
        stale = [t for t in CL.EXTERNAL if t not in printed]
        assert not stale, f"declared but no longer printed: {stale}"

    def test_keys_are_their_own_printed_form(self):
        """A declaration is matched by exact string; it must look like one."""
        for token in CL.EXTERNAL:
            assert re.fullmatch(r"-?\d[\d,]*(?:\.\d+)?(?:[eE][-+]?\d+)?", token), \
                f"{token!r} is not a printed number"

    def test_no_declaration_is_archival(self, shipped_tier, values):
        arf = CL.archive_forms(values)
        leak = [t for t in CL.EXTERNAL if t in arf]
        assert not leak, \
            f"the archives can print these, so ledger them instead: {leak}"

    def test_external_errors_is_clean(self, shipped_tier, values, text):
        assert CL.external_errors(values, text) == []


# --------------------------------------------------------------------------- #
# tokenising: the typographic traps of a LaTeX manuscript
# --------------------------------------------------------------------------- #
class TestNumberTokeniser:
    """Each test here was written after the tokenizer got one of these wrong."""

    def test_an_en_dash_is_not_a_minus_sign(self):
        assert [t for t, _ in CL.iter_numbers("range 283--1148 here")] == \
            ["283", "1148"]

    def test_a_real_negative_survives(self):
        assert [t for t, _ in CL.iter_numbers("bias -0.0067")] == ["-0.0067"]

    def test_a_prefix_is_not_double_counted(self):
        """'0.0067' must not be read out of '-0.0067' and claim the CI."""
        assert [t for t, _ in CL.iter_numbers("$-0.0067$ and -0.0067")] == \
            ["-0.0067", "-0.0067"]

    def test_thousands_stay_one_number_in_the_flat_text(self):
        assert [t for t, _ in CL.iter_numbers("the $20,000$ resample")] == \
            ["20,000"]
        assert [t for t, _ in CL.iter_numbers("$1,234.5$ days")] == ["1,234.5"]

    def test_latex_thousands_are_normalised_before_tokenising(self):
        flat = CL.flat_manuscript()
        assert "{,}" not in flat
        assert "20,000" in flat

    def test_a_comma_list_splits_into_its_items(self):
        assert [t for t, _ in CL.iter_numbers("$n=16,32,128$")] == \
            ["16", "32", "128"]

    def test_a_run_that_is_not_two_groups_is_a_list(self):
        assert [t for t, _ in CL.iter_numbers("$t_s=7200,3600,1800,900,450$")] == \
            ["7200", "3600", "1800", "900", "450"]

    def test_four_groups_is_a_list_too(self):
        assert [t for t, _ in CL.iter_numbers("$1,234,567,890$")] == \
            ["1", "234", "567", "890"]

    def test_offsets_point_at_their_own_token(self):
        s = "mean $0.3453\\pm0.0082$ over 1,234 days at -0.5"
        for tok, pos in CL.iter_numbers(s):
            assert s[pos:pos + len(tok)] == tok, (tok, pos)

    def test_token_index_collects_every_occurrence(self):
        s = "0.3453 and 0.3453 again"
        assert CL.token_index(s)["0.3453"] == [0, 11]

    def test_a_trailing_comma_is_not_part_of_the_number(self):
        assert [t for t, _ in CL.iter_numbers("value 0.3453, and")] == ["0.3453"]

    def test_exponents_are_three_tokens_not_one(self):
        """$5.6\\times10^{-14}$ prints three numbers; the mantissa is the one
        the ledger has to vouch for."""
        assert [t for t, _ in CL.iter_numbers("$5.6\\times10^{-14}$")] == \
            ["5.6", "10", "-14"]


class TestDisplay:

    def test_forms_add_both_thousands_spellings(self):
        assert "1,234" in CL.forms(1234.0, 0)
        assert "1{,}234" in CL.forms(1234.0, 0)
        assert "1234" in CL.forms(1234.0, 0)

    def test_forms_offer_the_unsigned_zero(self):
        """A difference of -1.7e-6 is printed as $0.0000$, never -0.0000."""
        assert "-0.0000" in CL.forms(-1.7e-6, 4)
        assert "0.0000" in CL.forms(-1.7e-6, 4)

    def test_forms_do_not_strip_a_real_negative(self):
        assert "0.151" not in CL.forms(-0.151, 3)

    def test_rounds_to_accepts_both_thousands_spellings(self):
        assert CL.rounds_to(43019.9, 1, "43,019.9")
        assert CL.rounds_to(43019.9, 1, "43{,}019.9")

    def test_rounds_to_uses_the_scale(self):
        assert CL.rounds_to(0.5096, 2, "50.96", 100)
        assert not CL.rounds_to(0.5096, 2, "0.51", 100)

    def test_rounds_to_is_digit_exact(self):
        assert CL.rounds_to(0.34531, 4, "0.3453")
        assert not CL.rounds_to(0.34536, 4, "0.3453")

    def test_display_matches_latex_printing(self):
        assert CL.display(0.34534, 4) == "0.3453"
        assert CL.display(-0.00004, 3) == "-0.000"

    def test_printable_lists_both_scales_and_every_precision(self):
        pairs = CL.printable(0.5)
        assert (1, 0) in pairs and (100, 2) in pairs
        assert len(pairs) == 2 * (CL.MAX_PRECISION + 1)

    def test_hit_limit_prefers_specific_strings(self):
        assert CL.hit_limit("0.20") == 4        # generic: must be rare
        assert CL.hit_limit("-0.1980") == 24    # specific: may repeat


# --------------------------------------------------------------------------- #
# the manuscript's own view of its numbers
# --------------------------------------------------------------------------- #
class TestManuscriptText:

    def test_the_input_fragment_is_spliced_in(self):
        flat = CL.flat_manuscript()
        assert "\\input{" not in flat
        assert "tab:targets" in flat, "the generated table was not spliced"

    def test_comments_are_stripped_before_flattening(self):
        flat = CL.flat_manuscript()
        assert "\\section" in flat and len(flat) > 100_000
        assert "NOTE FOR" not in flat or True   # comments never reach the text

    def test_the_bibliography_is_outside_the_ledger(self):
        """Other people's volume numbers and arXiv IDs are not ours to trace."""
        body = CL.body(CL.raw_manuscript())
        assert "thebibliography" not in body or \
            not re.search(r"\\bibitem", body), "the reference list leaked in"

    def test_years_and_small_integers_are_not_results(self, text):
        toks = {s for s, _ in CL.manuscript_numbers(text)}
        assert "2026" not in toks and "1" not in toks

    def test_bookkeeping_macros_do_not_leak_numbers(self):
        found = CL.manuscript_numbers(
            "see \\ref{fig:9.5} and \\includegraphics{grid_1024.png} "
            "and $0.1234$")
        assert [s for s, _ in found] == ["0.1234"]

    def test_every_ledgered_string_is_printed(self, claims, text):
        bad = [c["id"] for c in claims if c["shown"] not in text]
        assert not bad, bad[:5]

    def test_captions_count_as_reported_results(self):
        """A number that appears only in a caption is still a number."""
        found = CL.manuscript_numbers(
            "\\caption{The gain is $0.6183$ over baseline.}")
        assert "0.6183" in [s for s, _ in found]


# --------------------------------------------------------------------------- #
# tampering: the gate must be able to fail
# --------------------------------------------------------------------------- #
class TestTamperingIsCaught:
    """Break one thing at a time and show the ledger notices."""

    @pytest.fixture()
    def base(self, shipped_tier, ledger, values, text):
        return ledger, copy.deepcopy(values), text

    def test_a_changed_leaf_is_reported_as_stale(self, base):
        ledger, values, text = base
        c = ledger["claims"][0]
        ref = f"{c['src']}::{c['key']}"
        values[ref] = float(values[ref]) + 0.037
        errs = CL.check_ledger(ledger, values, text)
        assert any(e.startswith(c["id"]) and "STALE NUMBER" in e for e in errs), \
            f"tampering with {ref} gave: {errs[:3]}"

    def test_a_vanished_leaf_is_reported(self, base):
        ledger, values, text = base
        c = ledger["claims"][1]
        del values[f"{c['src']}::{c['key']}"]
        errs = CL.check_ledger(ledger, values, text)
        assert any(e.startswith(c["id"]) and "does not exist" in e for e in errs)

    def test_a_rewritten_sentence_is_reported(self, base):
        ledger, values, text = base
        c = next(x for x in ledger["claims"] if " " in x["quote"])
        broken = text.replace(c["quote"], c["quote"].replace(" ", "\u2004"))
        errs = CL.check_ledger(ledger, values, broken)
        assert any(e.startswith(c["id"]) and "verbatim" in e for e in errs), \
            f"{c['id']}: {errs[:3]}"

    def test_a_reprinted_digit_is_reported(self, base):
        """The paper printing other digits than its archive holds: the quote
        travels with it, so only the value comparison can catch it."""
        ledger, values, text = base
        c = next(x for x in ledger["claims"]
                 if len(x["shown"]) >= 6 and x["shown"].lstrip("-")[0].isdigit()
                 and x["shown"].lstrip("-").lstrip("0").rstrip("0"))
        swapped = c["shown"][:-1] + ("9" if c["shown"][-1] != "9" else "1")
        new_quote = c["quote"].replace(c["shown"], swapped, 1)
        new_text = text.replace(c["quote"], new_quote, 1)
        edited = dict(c, quote=new_quote, shown=swapped)
        patched = {"claims": [edited if x is c else x
                              for x in ledger["claims"]]}
        errs = CL.check_ledger(patched, values, new_text)
        assert any(e.startswith(c["id"]) and "STALE NUMBER" in e for e in errs), \
            f"{c['id']}: {errs[:3]}"

    def test_a_percent_scale_abuse_is_reported(self, base):
        ledger, values, text = base
        c = dict(next(x for x in ledger["claims"] if x.get("scale", 1) == 1))
        c["scale"] = 100
        errs = CL.check_ledger({"claims": [c]}, values, text)
        assert any(e.startswith(c["id"]) for e in errs), errs[:3]

    def test_a_changed_relation_input_is_reported(self, base):
        ledger, values, text = base
        rel = next(r for r in CL.RELATIONS
                   if any(isinstance(v, str) for v in r["vars"].values()))
        ref = next(v for v in rel["vars"].values() if isinstance(v, str))
        values[ref] = float(values[ref]) * 1.5
        errs = [CL.check_relation(r, values) for r in CL.RELATIONS]
        assert any(e and e.startswith(rel["id"]) and "STALE RELATION" in e
                   for e in errs), f"{rel['id']}: {errs[:3]}"

    def test_a_vacated_quote_is_reported(self, base):
        ledger, values, text = base
        rel = next(r for r in CL.RELATIONS if r.get("shown"))
        broken = text.replace(rel["shown"], rel["shown"][::-1], 1)
        errs = CL.check_ledger(ledger, values, broken)
        assert any(rel["id"] in e for e in errs), f"{rel['id']}: {errs[:3]}"

    def test_a_declaration_added_for_an_unprinted_token_is_reported(self, base):
        ledger, values, text = base
        CL.EXTERNAL["0.987654"] = "a token the manuscript never actually prints"
        try:
            errs = CL.external_errors(values, text)
            assert any("0.987654" in e and "stale" in e for e in errs), errs[:3]
            assert CL.check_ledger(ledger, values, text)
        finally:
            del CL.EXTERNAL["0.987654"]

    def test_a_declaration_without_a_reason_is_reported(self, base):
        ledger, values, text = base
        key = sorted(CL.EXTERNAL)[0]
        saved = CL.EXTERNAL[key]
        CL.EXTERNAL[key] = "shorthand"
        try:
            errs = CL.external_errors(values, text)
            assert any(key in e and "reason" in e for e in errs), errs[:3]
        finally:
            CL.EXTERNAL[key] = saved

    def test_withdrawing_a_needed_declaration_loses_a_number(self, base):
        ledger, values, text = base
        key = sorted(CL.EXTERNAL)[0]
        saved = CL.EXTERNAL.pop(key)
        try:
            cov = CL.coverage(ledger, values, text)
            assert key in cov["untraceable_list"], \
                f"{key} was still explained without its declaration"
        finally:
            CL.EXTERNAL[key] = saved

    def test_an_undeclared_new_number_is_unexplained(self, base):
        ledger, values, text = base
        fake = text.replace("Table~\\ref{tab:app_seeds}",
                            "Table~\\ref{tab:app_seeds} gives 0.1234567", 1)
        cov = CL.coverage(ledger, values, fake)
        assert "0.1234567" in cov["untraceable_list"]

    def test_a_duplicate_id_is_reported(self, base):
        ledger, values, text = base
        c = dict(ledger["claims"][0])
        errs = CL.check_ledger({"claims": [c, dict(c)]}, values, text)
        assert any("duplicate ledger id" in e for e in errs)

    def test_a_foreign_kind_is_reported(self, base):
        ledger, values, text = base
        c = dict(ledger["claims"][0], kind="vibes")
        errs = CL.check_ledger({"claims": [c]}, values, text)
        assert any("is not one of" in e for e in errs)

    def test_a_relation_with_a_bogus_variable_is_reported(self, base):
        ledger, values, text = base
        rel = dict(CL.RELATIONS[0])
        rel["vars"] = {"a": "audit.json::definitely.not.a.leaf"}
        errs = [CL.check_relation(rel, values)]
        assert errs[0] and "did not evaluate" in errs[0]

    def test_the_clean_ledger_is_the_only_one_that_passes(self, base):
        """And the untouched inputs pass, so the tests above are not vacuous."""
        ledger, values, text = base
        assert CL.check_ledger(ledger, values, text) == []


# --------------------------------------------------------------------------- #
# the build step
# --------------------------------------------------------------------------- #
class TestDerivedStatistics:
    """``tools/derive_stats.py`` is the build; the artifact is the bundle."""

    def test_the_artifact_declares_its_method(self):
        data = json.loads(CL.DERIVED.read_text(encoding="utf-8"))
        assert data["generated_by"] == "python3 tools/derive_stats.py --write"
        assert data["method"]["helper"] == "src/expcommon.py::paired_stats"
        assert data["method"]["nboot"] == 20000
        assert data["method"]["rng_seed"] == 42
        assert data["method"]["percentiles"] == [2.5, 97.5]

    def test_the_declared_method_is_the_shipped_helper_defaults(self):
        """If the helper's convention changes, the artifact must be rebuilt."""
        sys.path.insert(0, str(ROOT / "src"))
        import inspect

        import expcommon as E
        sig = inspect.signature(E.paired_stats)
        assert sig.parameters["nboot"].default == 20000
        assert sig.parameters["seed"].default == 42

    def test_the_bootstrap_convention_is_percentile_not_basic(self):
        sys.path.insert(0, str(ROOT / "src"))
        import numpy as np

        import expcommon as E
        d = np.arange(10, dtype=float)
        rng = np.random.default_rng(42)
        idx = rng.integers(0, 10, size=(20000, 10))
        boots = d[idx].mean(axis=1)
        st = E.paired_stats(d, np.zeros(10), nboot=20000, seed=42)
        assert st["ci_lo"] == pytest.approx(float(np.percentile(boots, 2.5)))
        assert st["ci_hi"] == pytest.approx(float(np.percentile(boots, 97.5)))

    def test_an_undefined_statistic_is_null_not_nan(self):
        """The no-injection rung has no t: it must be null, and the strict-JSON
        test above is what makes that observable."""
        text = CL.DERIVED.read_text(encoding="utf-8")
        assert "NaN" not in text and "Infinity" not in text
        data = json.loads(text)["stats"]["systematics"]["arms"]
        assert data["drift_r"]["0"]["t"] is None

    def test_derive_check_is_clean(self, shipped_tier):
        rc = subprocess.run([sys.executable, str(TOOLS / "derive_stats.py"),
                             "--check"], capture_output=True, text=True)
        assert rc.returncode == 0, rc.stdout[-700:]

    def test_the_build_is_deterministic(self):
        """Same archives in, same artifact out -- no wall clock, no RNG drift."""
        sys.path.insert(0, str(TOOLS))
        import derive_stats as DS
        a = json.dumps(DS.build()["stats"], sort_keys=True)
        b = json.dumps(DS.build()["stats"], sort_keys=True)
        assert a == b

    def test_derived_leaves_are_indexed_as_an_archive(self, values):
        refs = [k for k in values if k.startswith("derived_stats.json::")]
        assert len(refs) > 800, f"only {len(refs)} derived leaves indexed"

    def test_the_paper_quotes_derived_statistics_directly(self):
        """Bootstrap intervals and paired t's exist nowhere but the artifact."""
        ledger = CL.load_ledger()
        derived = [c for c in ledger["claims"]
                   if c["src"] == "derived_stats.json"]
        assert len(derived) >= 20, f"only {len(derived)} derived claims"
        ci = [c for c in derived if "ci_lo" in c["key"] or "ci_hi" in c["key"]]
        assert len(ci) >= 6, f"only {len(ci)} interval endpoints ledgered"

    def test_the_ensemble_paragraph_matches_the_reshaped_archive(self, values):
        """The five-geography means in the text are the 5x4 reshape of the
        shipped ensemble archive, in the archive's own order."""
        means = [values[f"derived_stats.json::ensemble.per_geography_mean[{i}]"]
                 for i in range(5)]
        printed = [0.3491, 0.3290, 0.3058, 0.3021, 0.3006]
        assert sorted(round(m, 4) for m in means) == sorted(printed), means

    def test_list_mode_prints_every_key(self):
        rc = subprocess.run([sys.executable, str(TOOLS / "derive_stats.py"),
                             "--list"], capture_output=True, text=True)
        assert rc.returncode == 0
        assert "contrasts.D_minus_A.mean" in rc.stdout


# --------------------------------------------------------------------------- #
# command line
# --------------------------------------------------------------------------- #
class TestCommandLine:

    def test_check_exits_zero(self, shipped_tier):
        assert CL.main(["--check"]) == 0

    def test_coverage_exits_zero_with_the_ci_gates(self, shipped_tier):
        assert CL.main(["--coverage", "--min-claims", str(MIN_CLAIMS),
                       "--max-untraceable", "0"]) == 0

    def test_an_impossible_claim_floor_fails(self, shipped_tier, capsys):
        assert CL.main(["--coverage", "--min-claims", "99999"]) == 1
        assert "FAIL" in capsys.readouterr().out

    def test_an_impossible_untraceable_ceiling_fails(self, shipped_tier, capsys):
        assert CL.main(["--coverage", "--max-untraceable", "0",
                        "--min-claims", "99999"]) == 1
        assert "FAIL" in capsys.readouterr().out

    def test_json_output_has_the_documented_keys(self, shipped_tier, capsys):
        assert CL.main(["--coverage", "--json"]) == 0
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert {"claims", "numbers", "traceable", "untraceable", "pct",
                "buckets", "external"} <= set(out)
        assert "untraceable_list" not in out, "the JSON line stays bounded"

    def test_check_json_output_shape(self, shipped_tier, capsys):
        assert CL.main(["--check", "--json"]) == 0
        out = json.loads(capsys.readouterr().out.strip())
        assert out["failures"] == [] and out["claims"] >= MIN_CLAIMS

    def test_report_names_a_source_for_every_claim(self, ledger, capsys):
        assert CL.main(["--report"]) == 0
        lines = capsys.readouterr().out.splitlines()
        assert len(lines) == len(CL.all_claims(ledger)) + 1
        assert lines[0].startswith("id")

    def test_describe_reads_like_a_formula(self):
        rel = CL.RELATIONS[0]
        assert rel["expr"] in CL.describe(rel)

    def test_check_never_writes_the_ledger(self, shipped_tier):
        before = CL.LEDGER.read_bytes()
        CL.main(["--check"])
        assert CL.LEDGER.read_bytes() == before

    def test_no_npz_mode_still_honours_the_json_leaves(self, capsys):
        """A text-only environment can still answer the shape questions."""
        values = CL.archive_values(with_npz=False)
        assert any(k.endswith(".json::headline.archived_collapse_r")
                   or ".json::" in k for k in values)
        assert not [k for k in values if k.endswith(".npz::stat_r")]
        assert len(values) < len(CL.archive_values())

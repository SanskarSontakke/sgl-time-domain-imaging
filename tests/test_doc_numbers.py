#!/usr/bin/env python3
"""Tests for ``tools/doc_numbers.py`` -- the documentation half of the build.

The manuscript has a proof layer for its numbers (``tools/claims.py``) and one
for its structure (``tools/manuscript_outline.py``).  ``tools/doc_numbers.py``
audits the third thing a reviewer reads and a repository forgets: the prose
*about* the repository.  The README's "36 pages, 9 figures", the test suite's
per-module count table, Appendix D's census of its own checks, the archive
inventory, the stage registry, the CI comment's denominators -- each of those is
a number someone typed and something else could change.

A gate that cannot fail is not a gate, so most of this file breaks the audit on
purpose.  Two levers are used deliberately:

* the **fact table** is tampered with (a deep copy of it, never the cached
  original), which proves that a document disagreeing with the tree is caught and
  names the fact in question;
* the **document text** is swapped out through ``_read`` -- a miniature workflow,
  a miniature count table, a README whose row for this tool has gone stale --
  which proves the structural auditors fire on the specific defect each was
  written for.

The integration tests then run the whole audit against the real tree and assert
it finds nothing, that every measurement it takes is stated by some document, and
that the registry is too big to have been quietly emptied.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import doc_numbers as DN  # noqa: E402


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def table():
    """The computed facts, measured once for the whole module (~3 s)."""
    return DN.facts()


@pytest.fixture
def tampered(table):
    """A deep copy of the fact table, so a test can lie about the tree.

    The cache inside ``doc_numbers`` must never see the lie: a mutated ``facts()``
    would leak into every later test and turn one tamper proof into a suite of
    false failures.
    """
    return copy.deepcopy(table)


@pytest.fixture
def fake_read(monkeypatch):
    """Route every document read in the audit through one callable.

    Returns a setter so a test can hand the auditors a file that does not exist
    in the tree -- a workflow with a broken ceiling, a count table with a row for
    a deleted module -- and leave the repository untouched.
    """
    def setter(text, only=None):
        real = DN._read

        def _read(rel):
            if only is None or rel == only:
                return text
            return real(rel)

        monkeypatch.setattr(DN, "_read", _read)
        return real
    return setter


# A miniature workflow, small enough to break on purpose and shaped like the real
# one: a gates job that deselects the slow tier, a numbers job, a paper job whose
# ceiling is quoted in a comment, mirrors checked before the build.
MINI_WORKFLOW = """name: verify
on:
  push:
    branches: [master]
concurrency:
  group: verify-${{ github.ref }}
  cancel-in-progress: true
jobs:
  gates:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - run: python -m pytest tests -q -m "not slow" --strict-markers
  numbers:
    runs-on: ubuntu-latest
    timeout-minutes: 25
    steps:
      - run: python3 tools/claims.py --check
  paper:
    runs-on: ubuntu-latest
    # the paper job has 45 minutes because it installs a TeX Live
    # the install step carries its own 12-minute cap for the same reason
    timeout-minutes: 45
    steps:
      - name: Install TeX Live
        timeout-minutes: 12
        run: apt-get -o Acquire::Retries=3 install texlive-latex-base
      - run: python3 tools/make_app_docs.py --check
      - run: bash tools/check_pdf_build.sh
"""


def rules(findings: list[str]) -> list[str]:
    """The rule names a list of findings fired, in order."""
    return [f.split("]")[0][1:] for f in findings]


# --------------------------------------------------------------------------- #
# the registry itself
# --------------------------------------------------------------------------- #
class TestRegistry:
    """The registry is code, so its invariants are testable before its output."""

    def test_it_is_big_enough_to_be_a_gate(self):
        assert len(DN.CLAIMS) >= 33, (
            "the documentation audit has shrunk; --min-claims in CI is the floor")

    def test_rule_ids_are_unique(self):
        ids = [c.rule for c in DN.CLAIMS]
        assert len(ids) == len(set(ids))

    def test_every_claim_is_documented_by_a_note(self):
        bad = [c.rule for c in DN.CLAIMS if len(c.note) < 20]
        assert bad == [], f"claims without a reason a reader would recognise: {bad}"

    def test_group_list_matches_the_capture_groups(self):
        for claim in DN.CLAIMS:
            assert claim.regex().groups == len(claim.groups), claim.rule

    def test_only_one_claim_is_a_presence_check(self):
        empty = [c.rule for c in DN.CLAIMS if not c.groups]
        assert empty == ["tests.config.pytest"], (
            "a groupless claim only proves a sentence exists; the only one is "
            f"the pytest.ini row, found {empty}")

    def test_claim_files_exist_or_glob(self):
        for claim in DN.CLAIMS:
            paths = (sorted(ROOT.glob(claim.file)) if "*" in claim.file
                     else [ROOT / claim.file])
            assert paths, f"{claim.rule} points at {claim.file}, which is absent"

    def test_rule_namespace_follows_the_file(self):
        want = {"README.md": "readme.", "tests/README.md": "tests.",
                "paper/main.tex": "paper.", DN.WORKFLOW: "ci.",
                DN.APP_GLOB: "app."}
        for claim in DN.CLAIMS:
            prefix = want.get(claim.file)
            assert prefix is not None, \
                f"{claim.rule} audits {claim.file}, which has no namespace"
            assert claim.rule.startswith(prefix), claim.rule

    def test_patterns_are_specific_enough_to_be_movable(self):
        for claim in DN.CLAIMS:
            assert len(claim.pattern) > 15, f"{claim.rule} is one word long"
            assert claim.at_least >= 1, claim.rule

    def test_they_all_match_the_current_tree(self):
        """The positive control: no pattern has rotted into non-matching."""
        missing = [f for f in DN.scan()["findings"] if "was not found" in f]
        assert missing == [], missing


# --------------------------------------------------------------------------- #
# the fact table
# --------------------------------------------------------------------------- #
class TestFacts:
    def test_it_measures_the_things_documents_quote(self, table):
        for key in ("test.functions", "checks.collected", "checks.fast",
                    "checks.slow", "results.npz", "results.parts",
                    "results.stored_arrays", "results.audit_leaves",
                    "stages.fast", "stages.full", "manuscript.pages",
                    "ledger.entries", "stats.derived"):
            assert key in table, key

    def test_every_value_is_a_count(self, table):
        for key, value in table.items():
            if isinstance(value, dict):
                assert all(isinstance(v, int) for v in value.values()), key
            else:
                assert isinstance(value, int) and not isinstance(value, bool), key
                assert value >= 0, key

    def test_the_tiers_add_up_to_the_collection(self, table):
        assert table["checks.fast"] + table["checks.slow"] \
            == table["checks.collected"]

    def test_the_module_maps_sum_to_the_totals(self, table):
        assert sum(table["checks.per_module"].values()) == table["checks.collected"]
        assert sum(table["test.functions.per_module"].values()) \
            == table["test.functions"]

    def test_functions_never_exceed_collected_checks(self, table):
        for name, n in table["checks.per_module"].items():
            assert table["test.functions.per_module"][name] <= n, name

    def test_the_slow_tier_is_a_subset_of_the_collection(self, table):
        for name, n in table["checks.slow.per_module"].items():
            assert n <= table["checks.per_module"][name], name

    def test_the_extension_archives_are_paired(self, table):
        assert table["results.ext"] == table["results.ext.json"] \
            == table["ext.modules"]
        assert table["results.ext"] < table["results.npz"]
        assert table["results.ext.json"] < table["results.json"]

    def test_the_registry_sizes_are_ordered(self, table):
        assert table["stages.fast"] < table["stages.full"]

    def test_the_ledger_entry_count_is_a_sum_of_its_halves(self, table):
        assert table["ledger.entries"] == table["ledger.claims"] \
            + table["ledger.relations"]

    def test_the_strict_ledger_gate_is_what_the_facts_say(self, table):
        assert table["ledger.unexplained"] == 0, \
            "the README claims no printed number is left unexplained"
        assert table["ledger.examined"] > table["ledger.claims"], \
            "more numbers are printed than the ledger vouches for, by design"

    def test_statistics_are_grouped_into_families(self, table):
        assert table["stats.families"] >= 2
        assert table["stats.derived"] > 100 * table["stats.families"]

    def test_the_audit_leaves_are_a_larger_denominator_than_arrays(self, table):
        assert table["results.audit_leaves"] > table["results.stored_arrays"]

    def test_no_document_claims_a_number_this_audit_cannot_measure(self, table):
        """Every fact key the registry cites must exist, brackets and all."""
        for claim in DN.CLAIMS:
            for key in claim.groups:
                base, _, rest = key.partition("[")
                rest = rest.rstrip("]")
                assert base in table, f"{claim.rule} cites unknown fact {key!r}"
                if rest:
                    assert rest in table[base], \
                        f"{claim.rule} cites {key!r}, not a module the suite has"

    def test_measurement_is_repeatable(self, table):
        assert DN.facts(refresh=True) == table, \
            "a fact moved between two runs in one process"


# --------------------------------------------------------------------------- #
# fact lookup
# --------------------------------------------------------------------------- #
class TestFactLookup:
    def test_a_plain_key_reads_the_number(self, table):
        assert DN._fact("manuscript.pages", table) == table["manuscript.pages"]

    def test_a_bracketed_key_reads_the_module_row(self, table):
        assert DN._fact("checks.per_module[test_claims_ledger.py]", table) \
            == table["checks.per_module"]["test_claims_ledger.py"]

    def test_an_unknown_module_is_a_keyerror_not_a_none(self, table):
        with pytest.raises(KeyError):
            DN._fact("checks.per_module[test_not_there.py]", table)

    def test_an_unknown_fact_is_a_keyerror(self, table):
        with pytest.raises(KeyError):
            DN._fact("manuscript.appendix.pages", table)


# --------------------------------------------------------------------------- #
# tamper proofs on the fact side: a document out of date by one is caught
# --------------------------------------------------------------------------- #
CLAIMED_FACTS = sorted({key for claim in DN.CLAIMS for key in claim.groups})


class TestClaimsFire:
    """Each documented number, moved by one, has to make the gate red."""

    @pytest.mark.parametrize("key", CLAIMED_FACTS)
    def test_a_document_that_disagrees_by_one_is_reported(self, tampered, key):
        base = DN._fact(key, tampered)
        if "[" in key:
            head, _, rest = key.partition("[")
            tampered[head][rest.rstrip("]")] = base + 1
        else:
            tampered[key] = base + 1
        findings = DN.scan(tampered)["findings"]
        assert findings, f"{key} is claimed somewhere and tampering it was silent"
        assert any(f"({key})" in f for f in findings), \
            f"nothing named {key} as the fact in question: {findings}"

    def test_the_manuscript_shape_is_claimed_in_two_places(self, tampered):
        tampered["manuscript.pages"] += 3
        fired = [f for f in DN.scan(tampered)["findings"]
                 if "manuscript.pages" in f]
        assert len(fired) >= 2, \
            "the one-liner and the proof-layer table should both be contradicted"

    def test_the_suite_census_is_claimed_in_the_paper_and_the_tests(self, tampered):
        tampered["test.functions"] -= 1
        fired = {rules([f])[0] for f in DN.scan(tampered)["findings"]
                 if "test.functions" in f}
        assert {"tests.total", "paper.suite"} <= fired, fired

    def test_tier_counts_are_claimed_more_than_once(self, tampered):
        tampered["checks.slow"] += 1
        fired = {rules([f])[0] for f in DN.scan(tampered)["findings"]
                 if "checks.slow" in f}
        assert len(fired) >= 3, fired

    def test_the_archive_denominators_are_claimed_in_ci(self, tampered):
        tampered["results.audit_leaves"] = 2_986
        fired = [f for f in DN.scan(tampered)["findings"]
                 if "results.audit_leaves" in f]
        assert fired and "2986" in fired[0], fired

    def test_the_extension_census_is_claimed_across_the_tree(self, tampered):
        tampered["results.ext"] += 1
        fired = {rules([f])[0] for f in DN.scan(tampered)["findings"]
                 if "(results.ext)" in f}
        assert len(fired) >= 3, fired

    def test_stage_counts_reach_the_paper_table(self, tampered):
        tampered["stages.full"] += 1
        assert any("paper.modes.full" in f for f in DN.scan(tampered)["findings"])

    def test_the_proof_layer_counts_reach_the_readme(self, tampered):
        tampered["stats.derived"] -= 5
        fired = {rules([f])[0] for f in DN.scan(tampered)["findings"]
                 if "stats.derived" in f}
        assert fired == {"readme.proof.stats"}, fired

    def test_the_ledger_halves_are_claimed_together(self, tampered):
        tampered["ledger.relations"] += 1
        tampered["ledger.entries"] += 1
        findings = DN.scan(tampered)["findings"]
        fired = {r for r, f in zip(rules(findings), findings)
                 if "ledger." in f}
        assert fired == {"readme.proof.ledger"}, fired
        assert any("ledger.relations" in f for f in findings)

    def test_the_unexplained_count_is_a_claim_not_a_promise(self, tampered):
        tampered["ledger.unexplained"] = 3
        assert any("0 unexplained" in f or "ledger.unexplained" in f
                   for f in DN.scan(tampered)["findings"])

    def test_a_untouched_table_still_passes(self, table):
        assert DN.scan(table)["findings"] == []


class TestUnmeasuredFacts:
    def test_a_cited_fact_that_stops_being_measured_is_a_finding(self, tampered):
        del tampered["manuscript.pages"]
        findings = DN.scan(tampered)["findings"]
        assert any("does not measure" in f for f in findings), findings

    def test_dropping_a_measurement_never_shrinks_the_audit(self, tampered):
        del tampered["checks.fast"]
        assert DN.scan(tampered)["findings"], \
            "a fact going missing must not quietly remove the claims about it"

    def test_a_measurement_no_document_states_is_a_finding(self, tampered):
        tampered["nobody.reads.this"] = 7
        findings = DN.scan(tampered)["findings"]
        assert any("docs.fact.unclaimed" in f and "nobody.reads.this" in f
                   for f in findings), findings

    def test_allow_unstated_turns_it_back_into_a_note(self, tampered):
        tampered["nobody.reads.this"] = 7
        lenient = DN.scan(tampered, allow_unstated=True)
        assert lenient["unstated_facts"] == ["nobody.reads.this"]
        assert not any("unclaimed" in f for f in lenient["findings"])


# --------------------------------------------------------------------------- #
# registry defects: a claim can be deleted or broken, and that is a finding too
# --------------------------------------------------------------------------- #
class TestRegistryDefects:
    def test_a_pattern_that_stops_matching_is_reported(self, table, monkeypatch):
        monkeypatch.setattr(DN, "CLAIMS", [DN.Claim(
            "readme.invented", "README.md", r"(\d+) quokkas per hectare",
            ("manuscript.pages",),
            "a sentence that was deleted from the README, not a tree that changed",
            at_least=1)])
        findings = DN.scan(table)["findings"]
        assert any(f.startswith("[readme.invented]") and "was not found" in f
                   for f in findings), findings

    def test_at_least_counts_matches_not_just_presence(self, table, monkeypatch):
        monkeypatch.setattr(DN, "CLAIMS", [DN.Claim(
            "readme.self.claims", "README.md", r"(\d+) documented claims",
            ("manuscript.pages",),
            "a claim the README states once but the audit expects twice",
            at_least=2)])
        findings = DN.scan(table)["findings"]
        assert any("matched 1, need >= 2" in f for f in findings), findings

    def test_a_missing_document_is_a_finding(self, table, monkeypatch):
        monkeypatch.setattr(DN, "CLAIMS", [DN.Claim(
            "docs.absent", "CHANGELOG-NOPE.md", r"(\d+) releases",
            ("manuscript.pages",),
            "a document the registry believes exists but the tree does not have")])
        findings = DN.scan(table)["findings"]
        assert any("does not exist" in f for f in findings), findings

    def test_a_lie_in_the_document_is_a_finding(self, table, monkeypatch):
        monkeypatch.setattr(DN, "CLAIMS", [DN.Claim(
            "readme.falsified", "README.md", r"(\d+) pages",
            ("manuscript.pages",),
            "the README's own page count, asserted against a tree that disagrees")])
        tampered = copy.deepcopy(table)
        tampered["manuscript.pages"] = 999
        findings = DN.scan(tampered)["findings"]
        assert any("but the tree says 999" in f for f in findings), findings


# --------------------------------------------------------------------------- #
# the per-module count table, audited in both directions
# --------------------------------------------------------------------------- #
def mini_table(table, edits=lambda rows: rows):
    """Rebuild the README's count table from the fact table, with edits."""
    rows = edits(dict(table["checks.per_module"]))
    body = "\n".join(f"| `{name}` | some description here | {count} |"
                     for name, count in sorted(rows.items()))
    return ("# Tests\n\n| File | What it covers | Checks |\n"
            "| --- | --- | --- |\n" + body + "\n")


class TestModuleTable:
    def test_the_real_table_has_no_findings(self, table):
        findings: list[str] = []
        rows = DN.audit_module_table(table, findings)
        assert findings == [], findings
        assert rows == len(table["checks.per_module"])

    def test_rows_are_read_from_the_markdown(self, table):
        text = mini_table(table)
        assert {name: int(count)
                for name, count in DN.TABLE_ROW.findall(text)} \
            == table["checks.per_module"]

    def test_a_row_for_a_deleted_module_is_reported(self, table, fake_read):
        fake_read(mini_table(table, lambda r: dict(r, **{"test_phantom.py": 7})))
        findings: list[str] = []
        DN.audit_module_table(table, findings)
        assert any("test_phantom.py" in f and "collects nothing" in f
                   for f in findings), findings

    def test_a_wrong_row_count_is_reported(self, table, fake_read):
        text = mini_table(table, lambda r: dict(
            r, **{"test_claims_ledger.py": r["test_claims_ledger.py"] + 4}))
        findings = self.audit(table, text, fake_read)
        assert any("test_claims_ledger.py" in f and "collected checks" in f
                   for f in findings), findings

    def test_a_module_missing_from_the_table_is_reported(self, table, fake_read):
        text = mini_table(table, lambda r: {k: v for k, v in r.items()
                                            if k != "test_statistics.py"})
        findings = self.audit(table, text, fake_read)
        assert any("test_statistics.py" in f and "not in the table" in f
                   for f in findings), findings

    def test_a_table_that_does_not_sum_is_reported(self, table, fake_read):
        text = mini_table(table, lambda r: dict(
            r, **{"test_statistics.py": r["test_statistics.py"] + 1}))
        findings = self.audit(table, text, fake_read)
        assert any("sums to" in f for f in findings), findings

    def test_a_missing_readme_is_reported(self, table, fake_read):
        fake_read(None)
        findings: list[str] = []
        assert DN.audit_module_table(table, findings) == 0
        assert any(f.startswith("[tests.table]") and "missing" in f
                   for f in findings), findings

    @staticmethod
    def audit(table, text, fake_read):
        fake_read(text, only="tests/README.md")
        findings: list[str] = []
        DN.audit_module_table(table, findings)
        return findings


# --------------------------------------------------------------------------- #
# the workflow's self-consistency
# --------------------------------------------------------------------------- #
class TestWorkflowAudit:
    def audit(self, text, fake_read):
        fake_read(text, only=DN.WORKFLOW)
        findings: list[str] = []
        return DN.audit_workflow(findings), findings

    def test_the_real_workflow_is_clean(self):
        findings: list[str] = []
        ci = DN.audit_workflow(findings)
        assert findings == [], findings
        assert {"gates", "numbers", "paper"} <= set(ci["jobs"])
        assert ci["ceilings"]["paper"] >= 40
        assert ci["ceilings"]["gates"] >= 20

    def test_the_miniature_is_clean(self, fake_read):
        ci, findings = self.audit(MINI_WORKFLOW, fake_read)
        assert findings == [], findings
        assert ci["jobs"] == ["gates", "numbers", "paper"]

    def test_a_job_without_a_ceiling_is_reported(self, fake_read):
        _, findings = self.audit(
            MINI_WORKFLOW.replace("    timeout-minutes: 30\n", ""), fake_read)
        assert any("no timeout-minutes" in f for f in findings), findings

    def test_a_paper_ceiling_below_the_tex_install_is_reported(self, fake_read):
        _, findings = self.audit(
            MINI_WORKFLOW.replace("timeout-minutes: 45", "timeout-minutes: 9"),
            fake_read)
        assert any("9-minute ceiling" in f for f in findings), findings

    def test_a_comment_that_disagrees_with_the_job_is_reported(self, fake_read):
        _, findings = self.audit(
            MINI_WORKFLOW.replace("the paper job has 45 minutes",
                                  "the paper job has 60 minutes"), fake_read)
        assert any("but the job asks for 45" in f for f in findings), findings

    def test_a_removed_comment_is_a_finding_not_a_silence(self, fake_read):
        _, findings = self.audit(MINI_WORKFLOW.replace(
            "    # the paper job has 45 minutes because it installs a TeX Live\n",
            ""), fake_read)
        assert any("no longer stated where it is set" in f
                   for f in findings), findings

    def test_a_queued_series_of_builds_is_reported(self, fake_read):
        _, findings = self.audit(
            MINI_WORKFLOW.replace("  cancel-in-progress: true\n", ""), fake_read)
        assert any("cancel-in-progress" in f for f in findings), findings

    def test_ci_must_deselect_the_slow_tier(self, fake_read):
        _, findings = self.audit(
            MINI_WORKFLOW.replace('-m "not slow" ', ""), fake_read)
        assert any("deselect" in f for f in findings), findings

    def test_markers_must_be_strict(self, fake_read):
        _, findings = self.audit(
            MINI_WORKFLOW.replace(" --strict-markers", ""), fake_read)
        assert any("--strict-markers" in f for f in findings), findings

    def test_the_mirror_check_must_exist(self, fake_read):
        _, findings = self.audit(MINI_WORKFLOW.replace(
            "      - run: python3 tools/make_app_docs.py --check\n", ""), fake_read)
        assert any("no longer checks the" in f for f in findings), findings

    def test_the_mirror_check_must_precede_the_build(self, fake_read):
        _, findings = self.audit(MINI_WORKFLOW.replace(
            "      - run: python3 tools/make_app_docs.py --check\n"
            "      - run: bash tools/check_pdf_build.sh\n",
            "      - run: bash tools/check_pdf_build.sh\n"
            "      - run: python3 tools/make_app_docs.py --check\n"), fake_read)
        assert any("runs after the build" in f for f in findings), findings

    def test_building_in_the_checkout_is_reported(self, fake_read):
        _, findings = self.audit(MINI_WORKFLOW.replace(
            "      - run: bash tools/check_pdf_build.sh\n",
            "      - run: bash tools/check_pdf_build.sh\n"
            "      latexmk -pdf main.tex\n"), fake_read)
        assert any("compiles in the checkout" in f for f in findings), findings

    INSTALL_STEP = ("      - name: Install TeX Live\n"
                    "        timeout-minutes: 12\n"
                    "        run: apt-get -o Acquire::Retries=3 "
                    "install texlive-latex-base\n")

    def test_an_uncapped_tex_install_step_is_reported(self, fake_read):
        """The observed failure: apt hung for twenty minutes inside a 45."""
        _, findings = self.audit(MINI_WORKFLOW.replace(
            "        timeout-minutes: 12\n", ""), fake_read)
        assert any("install step is uncapped" in f for f in findings), findings

    def test_an_install_step_missing_entirely_is_reported(self, fake_read):
        _, findings = self.audit(MINI_WORKFLOW.replace(self.INSTALL_STEP, ""),
                                 fake_read)
        assert any("no Install TeX Live step" in f for f in findings), findings

    def test_a_cap_that_is_not_a_cap_is_reported(self, fake_read):
        """A step ceiling equal to the job ceiling bounds nothing."""
        _, findings = self.audit(
            MINI_WORKFLOW.replace("        timeout-minutes: 12",
                                  "        timeout-minutes: 45"), fake_read)
        assert any("so it caps nothing" in f for f in findings), findings

    def test_apt_without_retries_is_reported(self, fake_read):
        _, findings = self.audit(
            MINI_WORKFLOW.replace("-o Acquire::Retries=3 ", ""), fake_read)
        assert any("Acquire::Retries" in f for f in findings), findings

    def test_an_install_comment_that_disagrees_with_the_step_is_reported(self,
                                                                        fake_read):
        _, findings = self.audit(
            MINI_WORKFLOW.replace("its own 12-minute cap", "its own 8-minute cap"),
            fake_read)
        assert any("but the step asks for 12" in f for f in findings), findings

    def test_a_removed_install_comment_is_a_finding_not_a_silence(self, fake_read):
        _, findings = self.audit(MINI_WORKFLOW.replace(
            "    # the install step carries its own 12-minute cap "
            "for the same reason\n", ""), fake_read)
        assert any("install cap is no longer stated" in f
                   for f in findings), findings

    def test_a_missing_workflow_is_reported(self, fake_read):
        fake_read(None)
        findings: list[str] = []
        assert DN.audit_workflow(findings) == {}
        assert findings == [f"[ci.present] {DN.WORKFLOW} is missing"], findings

    def test_a_key_named_push_is_not_read_as_a_job(self, fake_read):
        ci, _ = self.audit(MINI_WORKFLOW, fake_read)
        assert "push" not in ci["jobs"], "the `on: push:` key is not a job"


# --------------------------------------------------------------------------- #
# the README's row about this audit
# --------------------------------------------------------------------------- #
class TestSelfRow:
    def test_the_real_readme_row_matches_a_real_run(self):
        report = DN.scan()
        assert [f for f in report["findings"] if "docs.self.row" in f] == []
        m = DN.SELF_ROW.search(DN._read("README.md"))
        assert m is not None
        assert (int(m.group(1)), int(m.group(2)), int(m.group(3))) == \
            (report["checked"], report["values"], report["module_rows"])

    def test_a_stale_claim_about_the_report_is_reported(self, fake_read):
        fake_read("| `tools/doc_numbers.py` | does it? | 12 documented claims, "
                  "34 numbers, 5 module rows, 0 findings |\n")
        findings: list[str] = []
        DN.audit_self(findings, values=34, rows=5)
        assert len(findings) == 1, findings
        assert "12 documented claims" in findings[0]

    def test_every_number_of_the_row_is_checked_separately(self, fake_read):
        fake_read("| `tools/doc_numbers.py` | does it? | 33 documented claims, "
                  "99 numbers, 8 module rows, 0 findings |\n")
        findings: list[str] = []
        DN.audit_self(findings, values=34, rows=16)
        assert len(findings) == 2, findings

    def test_a_deleted_row_is_a_finding(self, fake_read):
        fake_read("nothing here\n")
        findings: list[str] = []
        DN.audit_self(findings, values=1, rows=1)
        assert any("no longer states this tool's" in f for f in findings), findings

    def test_a_missing_readme_is_a_finding(self, fake_read):
        fake_read(None)
        findings: list[str] = []
        DN.audit_self(findings, values=1, rows=1)
        assert any("README.md is missing" in f for f in findings), findings


# --------------------------------------------------------------------------- #
# the whole audit against the real tree
# --------------------------------------------------------------------------- #
class TestRealTreeIsClean:
    def test_it_finds_nothing(self, table):
        assert DN.scan(table)["findings"] == []

    def test_every_measurement_is_stated_somewhere(self):
        report = DN.scan()
        assert report["unstated_facts"] == [], (
            "the audit measures " + ", ".join(report["unstated_facts"]) +
            " and no document states it, so those numbers cannot rot")

    def test_the_report_shape_is_stable(self, table):
        report = DN.scan(table)
        assert set(report) == {"facts", "findings", "checked", "values",
                               "module_rows", "ci", "unstated_facts"}
        assert report["checked"] == len(DN.CLAIMS)
        assert report["module_rows"] == len(table["checks.per_module"])

    def test_every_registered_group_is_counted_once_per_match(self, table):
        report = DN.scan(table)
        assert report["values"] >= sum(len(c.groups) for c in DN.CLAIMS), \
            "a claim that matches nowhere contributes numbers nobody counted"

    def test_the_json_is_strict_and_parseable(self, capsys):
        assert DN.main(["--json"]) == 0
        report = json.loads(capsys.readouterr().out)
        assert report["findings"] == [] and report["checked"] >= 33

    def test_the_human_report_counts_what_it_checked(self, capsys):
        assert DN.main([]) == 0
        out = capsys.readouterr().out
        m = re.search(r"documentation audit: (\d+) claims, (\d+) numbers, "
                      r"(\d+) module rows, (\d+) finding", out)
        assert m, out
        assert m.group(4) == "0" and int(m.group(1)) == len(DN.CLAIMS)
        assert "manuscript.pages" in out

    def test_show_facts_prints_the_tree_not_the_prose(self, capsys):
        assert DN.main(["--show-facts"]) == 0
        blob = json.loads(capsys.readouterr().out)
        assert blob["manuscript.pages"] == DN.facts()["manuscript.pages"]

    def test_allow_unstated_exits_zero_on_a_clean_tree(self, capsys):
        assert DN.main(["--allow-unstated"]) == 0


class TestCommandLineRefusesADeletedGate:
    def test_the_floor_stops_the_registry_being_emptied(self, capsys):
        assert DN.main(["--min-claims", "400"]) == 1
        out = capsys.readouterr().out
        assert "registry.floor" in out and "floor is 400" in out

    def test_the_default_floor_is_below_the_registry(self, capsys):
        assert DN.main(["--min-claims", "1"]) == 0
        assert "registry.floor" not in capsys.readouterr().out

    def test_the_registry_covers_every_documented_number_source(self):
        files = {c.file for c in DN.CLAIMS}
        for wanted in ("README.md", "tests/README.md", "paper/main.tex",
                       DN.WORKFLOW):
            assert wanted in files, f"{wanted} states counts nobody audits"

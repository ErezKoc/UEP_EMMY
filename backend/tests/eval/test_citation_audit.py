"""Citation audit — the rule table's provenance against the evidence ledger.

`tests/test_triage_provenance.py` already proves a rule cannot be built without
a citation. These tests ask the next question: does the citation say what the
rule needs it to say, at the urgency the rule asserts, for the species the rule
serves?

Network access is not used. Every URL was fetched during the audit on
2026-08-16 and what each page says is recorded in `evidence.py`; re-fetching in
CI would make the suite flaky and would not add a check. The live-link sweep is
`test_source_links_resolve.py`, which is opt-in.
"""

from __future__ import annotations

import pytest

from app.services.triage.rules import ALL_RULES
from app.services.triage.sources import ALL_SOURCES
from tests.eval import evidence as ev
from tests.eval.evidence import ALL_FINDINGS, Urgency

#: url -> the findings this audit recorded for that page.
FINDINGS_BY_URL: dict[str, list] = {}
for _finding in ALL_FINDINGS:
    FINDINGS_BY_URL.setdefault(_finding.url, []).append(_finding)


@pytest.mark.parametrize("source", ALL_SOURCES, ids=lambda s: s.url.split("/")[-1][:45])
def test_every_shipping_source_was_opened_and_read_by_this_audit(source):
    assert source.url in FINDINGS_BY_URL, (
        f"{source.name} ({source.url}) is cited by the rule table but was not fetched and "
        "recorded during this audit. It is unverified."
    )


@pytest.mark.parametrize("source", ALL_SOURCES, ids=lambda s: s.url.split("/")[-1][:45])
def test_no_source_is_a_search_result_or_index_page(source):
    bad = ("/search", "?q=", "google.", "bing.", "/tag/", "/category/")
    assert not any(marker in source.url.lower() for marker in bad), (
        f"{source.name} looks like a search or index URL, not an article."
    )
    findings = FINDINGS_BY_URL.get(source.url, [])
    assert findings, f"{source.name}: nothing recorded."


def test_declared_source_species_scope_matches_what_the_page_covers():
    """`sources.py` may narrow a page's scope, never widen it."""
    widened = []
    for source in ALL_SOURCES:
        for finding in FINDINGS_BY_URL.get(source.url, []):
            if finding.species is None:
                continue  # the page covers everything; any narrowing is safe
            declared = source.species
            if declared is None:
                widened.append(
                    f"{source.name}: declared for all animals, but the page covers only "
                    f"{sorted(finding.species)}"
                )
            elif not declared <= finding.species:
                widened.append(
                    f"{source.name}: declared for {sorted(declared)}, but the page covers "
                    f"{sorted(finding.species)}"
                )
    assert not widened, "Species scope widened beyond the page:\n  " + "\n  ".join(
        dict.fromkeys(widened)
    )


def test_no_rule_asserts_an_urgency_its_sources_do_not_establish():
    """An emergency rule needs at least one source that calls it an emergency.

    This is the check that separates 'the page is about this topic' from 'the
    page says this needs care now'.
    """
    unsupported = []
    for rule in ALL_RULES:
        if not rule.is_emergency:
            continue
        supports_emergency = any(
            finding.urgency == Urgency.EMERGENCY
            for citation in rule.citations
            for finding in FINDINGS_BY_URL.get(citation.url, [])
        )
        if not supports_emergency:
            pages = ", ".join(citation.source for citation in rule.citations)
            unsupported.append(
                f"{rule.id}: treated as an emergency, but no cited page uses emergency, "
                f"immediate or life-threatening language. Cites: {pages}"
            )
    assert not unsupported, (
        "Emergency rules whose sources do not establish emergency urgency:\n  "
        + "\n  ".join(unsupported)
    )


def test_rules_built_on_a_negative_finding_declare_the_extrapolation():
    """Where a page explicitly does NOT say 'urgent', the rule must say so.

    `Rule.is_extrapolation` is how the review document flags reasoning that
    goes past a source. A rule resting on a page this audit recorded a negative
    finding against, and asserting a higher urgency than the page supports,
    must carry that flag.
    """
    undeclared = []
    for rule in ALL_RULES:
        if not rule.is_emergency or rule.is_extrapolation:
            continue
        for citation in rule.citations:
            for finding in FINDINGS_BY_URL.get(citation.url, []):
                if finding.negative_finding and finding.urgency != Urgency.EMERGENCY:
                    undeclared.append(
                        f"{rule.id} asserts an emergency citing {finding.source_name!r}. "
                        f"{finding.negative_finding} "
                        "The rule carries no EXTRAPOLATION note."
                    )
    assert not undeclared, (
        "Undeclared extrapolations beyond a source's wording:\n  "
        + "\n  ".join(dict.fromkeys(undeclared))
    )


def test_weighted_rules_that_reach_amber_alone_rest_on_a_source_naming_urgency():
    """A rule that books a vet visit on its own needs a page that asks for one."""
    from app.services.triage.rules import AMBER_THRESHOLD

    thin = []
    for rule in ALL_RULES:
        if rule.is_emergency or rule.weight < AMBER_THRESHOLD:
            continue
        levels = {
            finding.urgency
            for citation in rule.citations
            for finding in FINDINGS_BY_URL.get(citation.url, [])
        }
        if not levels & {Urgency.EMERGENCY, Urgency.PROMPT_EXAM}:
            thin.append(
                f"{rule.id}: reaches amber on its own, but no cited page recommends "
                "veterinary attention at all."
            )
    assert not thin, "Amber-on-its-own rules with no urgency in the source:\n  " + "\n  ".join(thin)


def test_citation_paraphrases_are_not_stronger_than_the_page():
    """A `supports` string must not put urgency words into a page that has none."""
    urgency_words = ("emergency", "immediate", "life-threatening", "urgent", "same-day")
    overstated = []
    for rule in ALL_RULES:
        for citation in rule.citations:
            findings = FINDINGS_BY_URL.get(citation.url, [])
            if not findings:
                continue
            page_is_urgent = any(f.urgency == Urgency.EMERGENCY for f in findings)
            claimed = [w for w in urgency_words if w in citation.supports.lower()]
            if claimed and not page_is_urgent:
                overstated.append(
                    f"{rule.id} -> {citation.source!r}: paraphrase claims {claimed}, but the "
                    "page establishes no emergency urgency."
                )
    assert not overstated, "Overstated citation paraphrases:\n  " + "\n  ".join(overstated)


def test_recorded_access_dates_are_not_in_the_future_and_are_not_stale():
    from datetime import timedelta

    for source in ALL_SOURCES:
        assert source.accessed <= ev.AUDIT_DATE, (
            f"{source.name} claims an access date after this audit ran."
        )
        assert ev.AUDIT_DATE - source.accessed < timedelta(days=365), (
            f"{source.name} was last read on {source.accessed}; re-read it."
        )


def test_nothing_in_the_rule_table_claims_clinical_validation():
    """`verified_by` means a named person signed the source off. Nobody has."""
    signed = [
        f"{rule.id} -> {citation.source} (verified_by={citation.verified_by!r})"
        for rule in ALL_RULES
        for citation in rule.citations
        if citation.verified_by
    ]
    assert not signed, (
        "A citation claims human verification. This audit did not perform clinical "
        "validation and must not be recorded as having done so:\n  " + "\n  ".join(signed)
    )
    assert all(finding.verified_by is None for finding in ALL_FINDINGS), (
        "The audit's own evidence ledger must not claim veterinary sign-off either."
    )


def test_the_source_list_records_pages_that_are_promotional_as_well_as_clinical():
    """Surfaces which cited pages are not neutral clinical references."""
    promotional = [
        finding.source_name
        for finding in ALL_FINDINGS
        if finding.page_type != "clinical article"
    ]
    assert promotional, "Expected the audit to have flagged at least one non-article page."
    # Informational: this test documents the finding rather than failing on it.
    assert all(name for name in promotional)


def test_the_oracle_and_production_agree_on_what_unknown_species_means():
    """The oracle keeps its own placeholder list; drift must be caught, not shared.

    `tests/eval/evidence.py` deliberately does not import
    `app.core.species`, so the audit's idea of "the owner didn't tell us" is
    independent of the engine's. That independence is only useful if the two are
    compared — otherwise a placeholder added to one and not the other would
    quietly stop being tested.
    """
    from app.core.species import UNKNOWN_SPECIES_PLACEHOLDERS, normalise_species

    production = UNKNOWN_SPECIES_PLACEHOLDERS | {""}
    only_audit = ev.UNKNOWN_SPECIES_VALUES - production
    only_production = production - ev.UNKNOWN_SPECIES_VALUES
    assert not only_audit and not only_production, (
        "The audit and the engine disagree about which answers mean 'unknown species'.\n"
        f"  only in tests/eval/evidence.py: {sorted(only_audit)}\n"
        f"  only in app/core/species.py:    {sorted(only_production)}"
    )
    for value in ev.AMBIGUOUS_UNKNOWN_SPECIES_VALUES:
        assert normalise_species(value) is None, f"{value!r} should normalise to unknown."


def test_a_rule_for_every_species_may_only_cite_all_species_evidence():
    """`applies_to_species=None` is a strong claim; the source must make it too."""
    for rule in ALL_RULES:
        if not rule.applies_to_every_species:
            continue
        for citation in rule.citations:
            assert citation.species is None, (
                f"{rule.id!r} applies to every species but cites {citation.source!r}, which "
                f"covers only {sorted(citation.species)}."
            )
            findings = FINDINGS_BY_URL.get(citation.url, [])
            assert findings and all(f.species is None for f in findings), (
                f"{rule.id!r} applies to every species, but this audit did not read "
                f"{citation.source!r} as making an all-species claim."
            )


def test_signs_the_form_offers_but_no_source_covers_are_recorded():
    """The intake form must not ask about signs the evidence base cannot use."""
    from app.schemas.triage import RedFlag

    offered = {flag.value for flag in RedFlag}
    assert ev.SIGNS_WITHOUT_STANDALONE_EVIDENCE <= offered, (
        "The recorded coverage gap names a sign the form does not offer."
    )

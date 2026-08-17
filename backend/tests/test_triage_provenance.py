"""Scientific integrity, enforced by the test suite.

These tests make it impossible to add a clinical claim without recording where
it came from, and they prove the production gate that blocks unverified rules
actually works.

They do NOT check whether a rule is clinically correct — only a veterinarian
can do that. See `test_triage_vignettes.py` for the accuracy side.
"""

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from app.schemas.triage import RedFlag, TriageLevel
from app.services.triage import ALL_RULES, Citation, Rule, TriageEngine, UnverifiedRulesError
from app.services.triage.conditions import HasRedFlag
from app.services.triage.sources import ALL_SOURCES, CAT_ONLY


def _valid_citation(**overrides) -> dict:
    base = dict(
        source="Merck Veterinary Manual — What to Do in a Dog or Cat Emergency",
        url="https://www.merckvetmanual.com/special-pet-topics/emergencies",
        accessed=date(2026, 7, 30),
        supports="lists trouble breathing among emergencies",
    )
    base.update(overrides)
    return base


# --------------------------------------------------------------- the rule table


def test_every_rule_cites_a_source():
    uncited = [rule.id for rule in ALL_RULES if not rule.citations]
    assert not uncited, f"Rules with no source: {uncited}"


def test_every_citation_records_url_and_access_date():
    """A source name alone is not provenance — we must be able to re-open it."""
    for rule in ALL_RULES:
        for citation in rule.citations:
            assert citation.url.startswith("https://"), f"{rule.id} has no usable url"
            assert isinstance(citation.accessed, date), f"{rule.id} has no access date"
            assert citation.supports.strip(), f"{rule.id} does not say what its source supports"


def test_every_citation_uses_a_source_we_actually_read():
    """No rule may cite a publication that is not in the vetted source list."""
    known_urls = {source.url for source in ALL_SOURCES}
    for rule in ALL_RULES:
        for citation in rule.citations:
            assert citation.url in known_urls, (
                f"Rule {rule.id!r} cites {citation.url!r}, which is not in sources.py. "
                "Every cited page must be one we fetched and read."
            )


def test_every_rule_stays_within_each_citations_species_scope():
    for rule in ALL_RULES:
        for citation in rule.citations:
            if citation.species is not None:
                assert rule.applies_to_species <= citation.species, (
                    f"Rule {rule.id!r} applies to {sorted(rule.applies_to_species)}, but "
                    f"{citation.source!r} only covers {sorted(citation.species)}."
                )


def test_rule_ids_are_unique():
    ids = [rule.id for rule in ALL_RULES]
    assert len(ids) == len(set(ids)), "Duplicate rule ids make the audit trail ambiguous."


def test_emergency_rules_override_to_red_and_carry_no_weight():
    for rule in ALL_RULES:
        if rule.level_override is not None:
            assert rule.level_override is TriageLevel.RED
            assert rule.weight == 0


def test_weighted_rules_have_sane_weights():
    for rule in ALL_RULES:
        if rule.level_override is None:
            assert 1 <= rule.weight <= 5, f"Rule {rule.id!r} has an out-of-range weight."


def test_extrapolations_are_declared():
    """Where we reason past the source, the rule must say so for the reviewer."""
    for rule in ALL_RULES:
        if rule.is_extrapolation:
            assert "EXTRAPOLATION" in rule.describe()


def test_unsourced_candidates_cannot_reach_the_engine():
    """The rules we could not source must not affect any result."""
    from app.services.triage.candidates import CANDIDATE_RULES

    live_ids = {rule.id for rule in ALL_RULES}
    for candidate in CANDIDATE_RULES:
        assert candidate["id"] not in live_ids, (
            f"{candidate['id']!r} has no published source but is loaded in the rule table."
        )


# ------------------------------------------------------------ the citation type


def test_a_rule_cannot_be_built_without_a_citation():
    with pytest.raises(ValueError, match="no citation"):
        Rule(
            id="uncited",
            condition=HasRedFlag(RedFlag.SEIZURE),
            message="…",
            citations=(),
            level_override=TriageLevel.RED,
        )


@pytest.mark.parametrize("field", ["source", "url", "supports"])
def test_citations_reject_empty_fields(field):
    with pytest.raises(ValueError, match=f"missing {field}"):
        Citation(**_valid_citation(**{field: "  "}))


@pytest.mark.parametrize("junk", ["TODO: find a source", "see example.org", "tbd"])
def test_citations_reject_placeholders(junk):
    with pytest.raises(ValueError, match="placeholder"):
        Citation(**_valid_citation(source=junk))


def test_citations_reject_a_url_that_is_not_a_link():
    with pytest.raises(ValueError, match="real https link"):
        Citation(**_valid_citation(url="Merck Veterinary Manual, page 42"))


def test_rule_rejects_a_species_mismatch_at_construction_time():
    cat_citation = Citation(**_valid_citation(species=CAT_ONLY))
    with pytest.raises(ValueError, match="does not"):
        Rule(
            id="dog_and_cat_rule_with_cat_source",
            condition=HasRedFlag(RedFlag.SEIZURE),
            message="A seizure needs care.",
            citations=(cat_citation,),
            level_override=TriageLevel.RED,
        )


# ------------------------------------------------------------- the strict gate


def test_nothing_is_verified_yet_and_the_report_says_so():
    """Honest default: the sources were read by research, not by the team."""
    assert not any(rule.is_verified for rule in ALL_RULES)


def test_strict_mode_refuses_unverified_rules():
    with pytest.raises(UnverifiedRulesError, match="unverified"):
        TriageEngine(ALL_RULES, require_verified=True)


def test_strict_mode_accepts_a_fully_verified_table():
    verified_rule = Rule(
        id="verified_example",
        condition=HasRedFlag(RedFlag.SEIZURE),
        message="A seizure needs emergency veterinary care.",
        level_override=TriageLevel.RED,
        citations=(Citation(**_valid_citation(verified_by="Mehmet")),),
    )
    engine = TriageEngine((verified_rule,), require_verified=True)
    assert engine.fully_verified


def test_review_report_lists_sources_rules_and_open_questions():
    from app.services.triage import provenance_report

    report = provenance_report()
    for source in ALL_SOURCES:
        assert source.url in report
    for rule in ALL_RULES:
        assert rule.id in report
    assert "awaiting verification" in report
    assert "NOT IN USE" in report


def test_a_legacy_triage_snapshot_does_not_break_the_history_page():
    """Old stored verdicts must degrade, never 500 the whole list.

    Triage is stored verbatim so a past verdict stays reproducible after the
    rules change — but that means old snapshots can predate the current schema
    (`fired_rules` carried `citation` before it carried `sources`). Validating
    those strictly made one legacy row return 500 for the entire history.
    """
    from app.schemas.analysis import AnalysisHistoryItem

    legacy = {
        "level": "amber",
        "headline": "Worth a vet visit",
        "score": 3,
        "threshold": 3,
        "fired_rules": [
            {"rule_id": "self_trauma", "message": "Licking", "weight": 2, "citation": "Merck"}
        ],
        "advice": "Book an appointment.",
        "disclaimer": "Not a diagnosis.",
        "rules_fully_verified": False,
    }
    item = AnalysisHistoryItem.model_validate(
        {
            "id": uuid4(),
            "image_url": "/media/x.png",
            "created_at": datetime(2026, 7, 30, tzinfo=timezone.utc),
            "result": {
                "model_version": "m",
                "species": "dog",
                "species_confidence": 0.9,
                "breed_candidates": [],
                "age_estimate": {
                    "category": "adult",
                    "min_years": 1,
                    "max_years": 8,
                    "confidence": 0.8,
                },
                "characteristics": [],
            },
            "triage": legacy,
            "animal": None,
        }
    )
    assert item.triage is None, "An unreadable snapshot should be dropped, not raised."

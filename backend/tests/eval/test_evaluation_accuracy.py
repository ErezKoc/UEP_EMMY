"""Accuracy of the engine against the independent evidence oracle.

The gate that matters is `test_no_confirmed_under_triage`. Over-triage is
measured and printed but never fails a test — sending someone to a vet they did
not strictly need is the error this product is allowed to make.

Reproduce, with the full report on stdout:
    python -m pytest tests/eval/test_evaluation_accuracy.py -s
Write the report to a file:
    python -m tests.eval.run_audit
"""

from __future__ import annotations

from collections import Counter

import pytest

from app.schemas.triage import TriageLevel
from tests.eval.cases import CASES, GENERATOR_SEED
from tests.eval.metrics import evaluate, render_report

OUTCOMES = evaluate()
SCORED = [o for o in OUTCOMES if o.scored]


def test_the_evaluation_set_meets_the_audit_size_and_reproducibility_bar():
    assert len(CASES) >= 500, f"Only {len(CASES)} scenarios; the audit requires 500."
    assert GENERATOR_SEED == 20260816, "The generated cases must stay reproducible."
    # Rebuilding the set must produce identical cases.
    from importlib import reload

    import tests.eval.cases as module

    ids_before = [case.id for case in CASES]
    reload(module)
    assert [case.id for case in module.CASES] == ids_before


def test_every_scored_case_records_its_source_and_rationale():
    """Each label must say why, and cite the page it came from.

    The one exception is the breed-only case, which is green because no health
    question was asked. There is no clinical claim there to source.
    """
    for outcome in SCORED:
        assert outcome.label.rationale, f"{outcome.case.id}: labelled with no rationale."
        if "No health question was asked" in outcome.label.rationale:
            continue
        assert outcome.label.source_urls, f"{outcome.case.id}: labelled with no source."


def test_no_confirmed_under_triage():
    """THE safety gate. A case the evidence puts above the engine's answer.

    'Confirmed' means every step of the label is quoted from a published page,
    so the disagreement cannot be explained away as the auditor's reasoning.
    """
    failures = [o for o in SCORED if o.confirmed_under_triage]
    assert not failures, (
        f"{len(failures)} confirmed under-triaged cases (target: 0).\n\n"
        + "\n\n".join(outcome.describe() for outcome in failures[:12])
        + (f"\n\n... and {len(failures) - 12} more. Full list: python -m tests.eval.run_audit"
           if len(failures) > 12 else "")
    )


def test_no_inference_dependent_under_triage():
    """Separate, softer gate: labels that needed a step past the source.

    This carried an xfail for feline anorexia below Cornell's 24-hour mark. The
    marker said the label rested on reading that threshold as implying something
    about a shorter fast, and that only a veterinarian could settle it. Re-reading
    the page on 2026-08-22 settled it a different way: it also says a cat that is
    not eating deserves a full veterinary workup, and to consult a veterinarian
    immediately on noticing any sign of anorexia, neither of them conditioned on
    a duration. So there was no inference to adjudicate — the ledger had recorded
    one sentence off the page and missed two others, and `cat_not_eating` now
    reads them. What IS still open is the grade: the rule answers amber where
    Cornell says "immediately", and its reviewer note asks about that.
    """
    failures = [o for o in SCORED if o.under_triaged and not o.confirmed_under_triage]
    assert not failures, (
        f"{len(failures)} inference-dependent under-triaged cases. These rest on the "
        "auditor's reading rather than a source's literal words, so a veterinarian should "
        "settle them before they are treated as defects.\n\n"
        + "\n\n".join(outcome.describe() for outcome in failures[:8])
    )


def test_an_expected_red_case_never_returns_amber_or_green():
    failures = [o for o in SCORED if o.label.level is TriageLevel.RED and o.actual is not TriageLevel.RED]
    assert not failures, (
        f"{len(failures)} cases the evidence calls an emergency were not returned as red.\n\n"
        + "\n\n".join(outcome.describe() for outcome in failures[:10])
    )


def test_an_expected_amber_case_never_returns_green():
    failures = [
        o for o in SCORED if o.label.level is TriageLevel.AMBER and o.actual is TriageLevel.GREEN
    ]
    assert not failures, (
        f"{len(failures)} cases the evidence says need a vet were returned as green.\n\n"
        + "\n\n".join(outcome.describe() for outcome in failures[:10])
    )


def test_an_expected_green_case_is_never_escalated_beyond_amber():
    """Over-triage is tolerated, but a false emergency has its own costs."""
    failures = [
        o for o in SCORED if o.label.level is TriageLevel.GREEN and o.actual is TriageLevel.RED
    ]
    assert not failures, (
        f"{len(failures)} cases the evidence says can be watched were called emergencies.\n\n"
        + "\n\n".join(outcome.describe() for outcome in failures[:10])
    )


@pytest.mark.parametrize(
    "rule_id",
    sorted(rule.id for rule in __import__(
        "app.services.triage.rules", fromlist=["ALL_RULES"]
    ).ALL_RULES),
)
def test_every_shipping_rule_is_exercised_by_the_evaluation_set(rule_id):
    """A rule no case reaches is a rule this audit says nothing about."""
    fired = Counter(rid for outcome in OUTCOMES for rid in outcome.fired_rule_ids)
    assert fired[rule_id], f"No scenario in the evaluation set caused {rule_id!r} to fire."


def test_over_triage_is_reported_not_hidden(capsys):
    over = [o for o in SCORED if o.over_triaged]
    with capsys.disabled():
        print(f"\n\nover-triage: {len(over)}/{len(SCORED)} evidence-labelled cases")
        for outcome in over[:10]:
            print(
                f"  {outcome.case.id}: evidence {outcome.label.level.value} -> "
                f"engine {outcome.actual.value} via {list(outcome.fired_rule_ids)}"
            )
    assert True  # informational only


def test_print_full_report(capsys):
    with capsys.disabled():
        print("\n" + render_report(OUTCOMES))

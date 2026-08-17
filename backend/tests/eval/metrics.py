"""Scores the engine against the evidence oracle and renders the numbers.

Under-triage is the primary safety metric and is split in two:

* **confirmed** — the label rests only on findings quoted from a source. A
  disagreement here means the engine contradicts published wording.
* **inference-dependent** — the label needed a step the source does not take
  (see `Finding.inference`). Reported, but not treated as proof of a defect.

Over-triage is reported in full and never folded into a pass rate.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from app.schemas.triage import TriageAssessment, TriageLevel
from app.services.triage import TriageEngine
from tests.eval.cases import CASES, Case
from tests.eval.oracle import NEEDS_REVIEW, SEVERITY, Label, expected_label

LEVELS = (TriageLevel.RED, TriageLevel.AMBER, TriageLevel.GREEN, TriageLevel.UNASSESSED)
#: Rows of the confusion matrix — the levels an evidence label can take.
LABEL_LEVELS = (TriageLevel.RED, TriageLevel.AMBER, TriageLevel.GREEN)


@dataclass(frozen=True)
class Outcome:
    case: Case
    label: Label
    result: TriageAssessment

    @property
    def scored(self) -> bool:
        return not self.label.needs_review

    @property
    def actual(self) -> TriageLevel:
        return self.result.level

    @property
    def abstained(self) -> bool:
        """The engine declined to place this case on the urgency scale."""
        return self.actual is TriageLevel.UNASSESSED

    @property
    def agrees(self) -> bool:
        return self.scored and not self.abstained and self.actual is self.label.level

    @property
    def under_triaged(self) -> bool:
        """The answer was less urgent than the published evidence supports.

        An abstention counts here when the evidence supports red or amber: the
        sources DO cover that case, so declining to answer is a failure to apply
        evidence we hold, not honest uncertainty. `UNASSESSED` must never become
        a way to make an under-triage disappear from this number.
        """
        if not self.scored:
            return False
        if self.abstained:
            return self.label.level in (TriageLevel.RED, TriageLevel.AMBER)
        return SEVERITY[self.actual] < SEVERITY[self.label.level]

    @property
    def abstained_on_a_green_label(self) -> bool:
        """Declined to answer where the evidence would have allowed monitoring.

        Not a safety failure and not over-triage — the engine withheld
        reassurance it could arguably have given. Reported on its own so the
        cost of the no-green-without-a-rule policy stays visible.
        """
        return self.scored and self.abstained and self.label.level is TriageLevel.GREEN

    @property
    def over_triaged(self) -> bool:
        return self.scored and not self.abstained and SEVERITY[self.actual] > SEVERITY[self.label.level]

    @property
    def confirmed_under_triage(self) -> bool:
        """Under-triage where the label quotes a source rather than reasoning."""
        return self.under_triaged and not self.label.inferred

    @property
    def fired_rule_ids(self) -> tuple[str, ...]:
        return tuple(rule.rule_id for rule in self.result.fired_rules)

    def describe(self) -> str:
        expected = self.label.level.value if self.scored else NEEDS_REVIEW
        if self.abstained and self.under_triaged:
            expected += " — the engine abstained on a case the sources cover"
        return (
            f"[{self.case.id}] {self.case.description}\n"
            f"  intake:   {self.case.intake.model_dump(exclude_none=True)}\n"
            f"  expected: {expected}"
            f"{' (inference-dependent)' if self.label.inferred else ''}\n"
            f"  actual:   {self.actual.value} (score {self.result.score})\n"
            f"  fired:    {list(self.fired_rule_ids) or 'none'}\n"
            f"  headline: {self.result.headline!r}\n"
            f"  basis:    {self.label.rationale}\n"
            f"  sources:  {', '.join(self.label.source_urls) or 'n/a'}"
        )


def evaluate(engine: TriageEngine | None = None, cases=CASES) -> tuple[Outcome, ...]:
    engine = engine or TriageEngine(require_verified=False)
    return tuple(
        Outcome(case, expected_label(case.intake), engine.assess(case.intake)) for case in cases
    )


def confusion_matrix(outcomes) -> dict[TriageLevel, Counter]:
    matrix: dict[TriageLevel, Counter] = {level: Counter() for level in LABEL_LEVELS}
    for outcome in outcomes:
        if outcome.scored:
            matrix[outcome.label.level][outcome.actual] += 1
    return matrix


def _rate(part: int, whole: int) -> str:
    return f"{part}/{whole} ({(100 * part / whole if whole else 0):.1f}%)"


def _breakdown(outcomes, key) -> list[str]:
    buckets: dict[str, list[Outcome]] = defaultdict(list)
    for outcome in outcomes:
        buckets[key(outcome)].append(outcome)
    lines = []
    for name in sorted(buckets, key=str):
        group = buckets[name]
        scored = [o for o in group if o.scored]
        under = sum(1 for o in scored if o.under_triaged)
        over = sum(1 for o in scored if o.over_triaged)
        agree = sum(1 for o in scored if o.agrees)
        lines.append(
            f"    {str(name):<22} n={len(group):<4} scored={len(scored):<4} "
            f"agree={agree:<4} over={over:<4} under={under}"
        )
    return lines


def render_report(outcomes) -> str:
    from tests.eval.cases import GENERATOR_SEED

    scored = [o for o in outcomes if o.scored]
    review = [o for o in outcomes if not o.scored]
    under = [o for o in scored if o.under_triaged]
    confirmed_under = [o for o in scored if o.confirmed_under_triage]
    over = [o for o in scored if o.over_triaged]
    agree = [o for o in scored if o.agrees]
    abstained_green = [o for o in scored if o.abstained_on_a_green_label]
    review_abstained = [o for o in review if o.abstained]
    review_green = [o for o in review if o.actual is TriageLevel.GREEN]

    out = [
        "=" * 78,
        "TRIAGE EVALUATION — engine vs. independent evidence oracle",
        "=" * 78,
        f"generator seed:        {GENERATOR_SEED}",
        f"total scenarios:       {len(outcomes)}",
        f"evidence-labelled:     {len(scored)}",
        f"needs expert review:   {len(review)} (excluded from accuracy)",
        "",
        f"agreement:             {_rate(len(agree), len(scored))}",
        f"over-triage:           {_rate(len(over), len(scored))}",
        f"UNDER-TRIAGE (total):  {_rate(len(under), len(scored))}",
        f"UNDER-TRIAGE (confirmed, label quotes a source): {len(confirmed_under)}",
        "",
        "ABSTENTIONS (engine returned UNASSESSED)",
        f"    where the evidence supports red or amber: {sum(1 for o in under if o.abstained)}"
        "  <- counted as under-triage above",
        f"    where the evidence supports green:        {len(abstained_green)}"
        "  <- withheld reassurance, not a safety failure",
        f"    on needs-expert-review cases:             {len(review_abstained)} of {len(review)}",
        f"    needs-review cases still answered GREEN:  {len(review_green)}",
        "",
        "CONFUSION MATRIX (rows = evidence label, cols = engine output)",
        f"    {'':<10}{'red':>8}{'amber':>8}{'green':>8}{'unassess':>10}",
    ]
    matrix = confusion_matrix(outcomes)
    for expected in LABEL_LEVELS:
        row = matrix[expected]
        out.append(
            f"    {expected.value:<10}"
            + "".join(f"{row[actual]:>8}" for actual in LABEL_LEVELS)
            + f"{row[TriageLevel.UNASSESSED]:>10}"
        )

    out += ["", "BY ORIGIN"] + _breakdown(outcomes, lambda o: o.case.origin)
    out += ["", "BY SPECIES"] + _breakdown(
        outcomes, lambda o: repr(o.case.intake.species)
    )
    out += ["", "BY AGE CATEGORY"] + _breakdown(
        outcomes, lambda o: o.case.intake.age_category.value if o.case.intake.age_category else "none"
    )
    out += ["", "BY CONCERN"] + _breakdown(outcomes, lambda o: o.case.intake.concern.value)

    # Rule coverage.
    fired_counts: Counter = Counter()
    combos: Counter = Counter()
    for outcome in outcomes:
        ids = outcome.fired_rule_ids
        fired_counts.update(ids)
        if len(ids) > 1:
            combos[tuple(sorted(ids))] += 1

    from app.services.triage.rules import ALL_RULES

    out += ["", "RULE COVERAGE (times each rule appeared in a returned explanation)"]
    for rule in ALL_RULES:
        marker = "" if fired_counts[rule.id] else "   <-- NEVER FIRED"
        out.append(f"    {rule.id:<44} {fired_counts[rule.id]:>5}{marker}")

    out += ["", f"INTERACTING RULE COMBINATIONS ({len(combos)} distinct, top 15)"]
    for combo, n in combos.most_common(15):
        out.append(f"    {n:>4}x  {' + '.join(combo)}")

    if under:
        out += ["", "=" * 78, "UNDER-TRIAGED CASES", "=" * 78]
        for outcome in sorted(under, key=lambda o: -SEVERITY[o.label.level]):
            out += ["", outcome.describe()]

    if over:
        out += ["", "=" * 78, f"OVER-TRIAGED CASES ({len(over)}) — reported, not a failure",
                "=" * 78]
        for outcome in over[:25]:
            out += ["", outcome.describe()]
        if len(over) > 25:
            out.append(f"\n    ... and {len(over) - 25} more.")

    review_reasons = Counter(
        note for outcome in review for note in (outcome.label.notes or ("unclassified",))
    )
    out += ["", "NEEDS-EXPERT-REVIEW BREAKDOWN"]
    for reason, n in review_reasons.most_common():
        out.append(f"    {reason:<28} {n}")

    return "\n".join(out)

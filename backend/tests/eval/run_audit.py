"""Writes the evaluation metrics to a file and prints the headline numbers.

    python -m tests.eval.run_audit                    # -> reports/triage_evaluation.txt
    python -m tests.eval.run_audit somewhere/else.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

from tests.eval.metrics import evaluate, render_report

DEFAULT_OUTPUT = Path("reports/triage_evaluation.txt")


def main(argv: list[str]) -> int:
    destination = Path(argv[1]) if len(argv) > 1 else DEFAULT_OUTPUT
    destination.parent.mkdir(parents=True, exist_ok=True)

    outcomes = evaluate()
    report = render_report(outcomes)
    destination.write_text(report, encoding="utf-8")

    scored = [o for o in outcomes if o.scored]
    under = [o for o in scored if o.under_triaged]
    confirmed = [o for o in under if o.confirmed_under_triage]
    print(report.split("CONFUSION MATRIX")[0])
    print(f"written to {destination}")
    # Non-zero exit when a confirmed under-triage exists, so CI can gate on it.
    return 1 if confirmed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

"""Independent clinical-safety evaluation of the triage engine.

Nothing in this package imports `app.services.triage.rules`. The expected
levels come from `evidence.py` — a ledger of what each published source was
independently read to say — so agreement between the engine and this suite is
evidence of correctness rather than a restatement of the same table.
"""

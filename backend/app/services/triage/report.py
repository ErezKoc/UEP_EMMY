"""Print the clinical rule table as plain English.

    python -m app.services.triage.report

Hand the output to the reviewing veterinarian: it is the complete clinical
logic of the product, with every source named, and needs no programming
knowledge to read.
"""

from app.services.triage.engine import provenance_report

if __name__ == "__main__":
    print(provenance_report())

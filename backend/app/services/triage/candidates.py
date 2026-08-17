"""Rules we could NOT source. Not loaded by the engine. Not used for anything.

These started as plausible clinical common sense, and an earlier draft shipped
them citing publications nobody had read. That is exactly the failure this
system exists to prevent, so they were pulled out of the rule table.

They are kept here — as plain descriptions, deliberately not as `Rule` objects
— for one purpose: to ask a veterinarian whether any of them is worth having.

Promotion path for any item below:

1. Find a published source that supports the claim, read it, and add a proper
   rule in `rules.py` citing it; or
2. Get a named veterinarian to state the claim in writing, and add it citing
   that review as the source, clearly marked as expert opinion rather than
   published guidance.

Until one of those happens, none of this affects a single triage result.
"""

CANDIDATE_RULES: tuple[dict[str, str], ...] = (
    {
        "id": "worsening",
        "claim": "A problem that is getting worse rather than settling deserves more concern.",
        "question_for_reviewer": "Is a worsening trend on its own enough to move someone up a level?",
    },
    {
        "id": "persistent_problem",
        "claim": "A problem lasting more than a few weeks deserves a check-up even if it is mild.",
        "question_for_reviewer": "What duration would you use as the cut-off, and for which signs?",
    },
    {
        "id": "self_trauma",
        "claim": "Constant scratching or licking can turn a minor irritation into an infection.",
        "question_for_reviewer": "Is this worth scoring, and does it change with the affected area?",
    },
    {
        "id": "persistent_ear_problem",
        "claim": "Ear problems lasting more than a day or two usually need treatment to clear.",
        "question_for_reviewer": "Do ear signs justify their own rule, or fold into general duration?",
    },
    {
        "id": "other_species_not_eating",
        "claim": "Appetite loss in rabbits and other small pets deserves its own threshold.",
        "question_for_reviewer": (
            "We now have sourced rules for cats (Cornell: 24h adult, 12h kitten) and dogs (VCA: no"
            " hour threshold given). Rabbits and other species match no rule at all — gut stasis is"
            " often described as urgent. What would you use, and can you point us at a source?"
        ),
    },
    {
        "id": "senior_behaviour_change",
        "claim": "Behaviour changes in older animals often have a medical cause worth investigating.",
        "question_for_reviewer": "Would you score this, and would you separate cognitive from pain-related change?",
    },
)

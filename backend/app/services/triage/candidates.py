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
        "id": "skin_distribution",
        "claim": (
            "How widely a skin problem is spread — one area, several areas, or most of the body"
            " — should change how concerned we are."
        ),
        "question_for_reviewer": (
            "The form asks this, because Merck records distribution (focal, multifocal,"
            " symmetrical, generalized) as part of the dermatological history a diagnosis needs."
            " No page we hold attaches an urgency to any pattern, so the answer is stored for you"
            " to read and changes no result. Should a generalized pattern score, and would you"
            " treat symmetrical hair loss differently from a single patch?"
        ),
    },
    {
        "id": "respiratory_distress_composite",
        "claim": (
            "Respiratory distress is better recognised as a picture — rapid breathing together"
            " with increased effort, an abnormal posture, open-mouth breathing, a colour change,"
            " weakness or collapse — than as any single sign an owner ticks."
        ),
        "question_for_reviewer": (
            "We now ask two breathing questions ('breathing looks difficult or laboured' and"
            " 'breathing unusually fast while resting') where there was one unqualified"
            " 'breathing hard or fast', because a dog that has just run breathes hard and fast"
            " and is not an emergency. A reviewer of our output reports that Cornell's canine"
            " respiratory-distress material"
            " (https://www.vet.cornell.edu/departments-centers-and-institutes/riney-canine-health-"
            "center/canine-health-topics/recognizing-and-responding-canine-respiratory-distress)"
            " makes that point directly and describes distress as a composite, and that Cornell's"
            " ER guidance phrases the trigger as breathing faster or harder than normal"
            " ESPECIALLY AT REST. Nobody on the team has opened either page, so neither is cited"
            " and the 'at rest' qualifier is currently our own wording rather than theirs."
            " Please confirm the two questions as worded, and say whether the composite is worth"
            " asking for instead — noting the cost: every extra question is one an owner with a"
            " struggling animal has to answer before getting an answer."
            "\n      OUR RECOMMENDATION IS TO KEEP THE TWO QUESTIONS. The reviewer who raised"
            " the composite also advised against rushing to it: professional triage material"
            " describes respiratory compromise through rate, effort, pattern, posture and mucous"
            " membranes, which is a clinician assembling a picture. Asking an owner to assemble"
            " it themselves is a harder question than either of the two observable ones we now"
            " ask. This entry is here so the option is on record, not because we think the"
            " current questions are wrong."
        ),
    },
    # PROMOTED 2026-08-22 — `urinary_obstruction_outside_cats` is gone from this
    # list because it is now a real rule. A dog straining and producing nothing
    # used to match nothing and receive our abstention. The block asked someone
    # to read a non-feline source; ACVS's dog article and Merck's urethral
    # obstruction page were then read and are cited by `dog_unable_to_urinate`
    # in rules.py, which carries the questions that are still open about it.
    {
        "id": "gi_blood_emergency_breadth",
        "claim": (
            "Any owner-reported blood in vomit or stool — whatever the amount, frequency, colour,"
            " accompanying signs or species — belongs in the emergency branch."
        ),
        "question_for_reviewer": (
            "THIS IS A LIVE RULE, NOT A PARKED ONE: `blood_in_vomit_or_stool` is red today and"
            " deliberately conservative. It is recorded here because the proposition it asserts"
            " is broader than what we cited for it. Missouri lists blood or coffee-grounds"
            " material in vomit, and bloody or dark tarry stool, among situations warranting"
            " immediate attention — that is a list of situations, and our rule turns it into"
            " 'any blood at all, reported by an owner, is an emergency'. A reviewer notes that"
            " Merck's own wording is more qualified (bloody, foul-smelling or uncontrollable"
            " diarrhoea; thick black stools), and that hematemesis and melena warranting"
            " investigation is not the same claim as any single appearance of any amount"
            " justifying emergency triage. Is the blanket version the one you would sign, or"
            " should it read on amount, frequency, colour or accompanying signs? Note the cost of"
            " narrowing it: owners cannot reliably judge amount, and the current breadth is the"
            " over-triage we said we would accept. We have not changed the rule pending your"
            " answer."
        ),
    },
    {
        "id": "skin_mild_case_watch_or_examine",
        "claim": (
            "A mild, localised skin lesion — one small area, occasional licking or scratching,"
            " a few days old and not spreading — can reasonably be watched for a short period"
            " before an appointment is made."
        ),
        "question_for_reviewer": (
            "This is the gap the engine advertises on every skin result and cannot close."
            " `skin_lesion_needs_examination` fires on any lesion at all, so 'dog, one small itchy"
            " red patch on a paw, 2-7 days, unchanged, licking sometimes' and a generalised"
            " worsening one get the same recommendation, and the panel then has to admit that no"
            " page we hold says which of them should be seen rather than watched. Merck's"
            " dermatology pages record severity, distribution and duration as history a"
            " *clinician* takes; none of them sets a bar for an *owner* deciding whether to book."
            " Is there a defensible watch-first threshold for cases at the mild end — and if so,"
            " what should it read on (severity, spread, duration, or all three), and for how long"
            " should someone watch before booking anyway? A source we can cite would be better"
            " than a sign-off, but a signed-off opinion is enough to build on."
            "\n      LEAD, NOT YET READ BY US: a reviewer of our output pointed at Merck's"
            " 'When to See a Veterinarian' table"
            " (https://www.merckvetmanual.com/multimedia/table/when-to-see-a-veterinarian),"
            " reporting that it places a rash, persistent chewing or scratching and moderate"
            " itching in a 'within 24 hours' column. Nobody on the team has opened it, so it is"
            " recorded here as a lead and cites nothing. If it says what they describe it is the"
            " first timing evidence we would hold for skin at all — note that their own reading"
            " was that our worked example (occasional licking, one small localised patch) is not"
            " obviously the same presentation as 'persistent chewing' or 'moderate itching', so"
            " the mapping needs deciding as well as the source needing reading."
        ),
    },
    {
        "id": "skin_duration_threshold",
        "claim": "A skin problem that has not settled after some number of days needs seeing.",
        "question_for_reviewer": (
            "Merck's dermatology pages give no duration threshold at all — this is the gap that"
            " left 'dog, skin, paws, 2-7 days, unchanged' unassessable until the form started"
            " asking what was actually on the skin. Is there a duration at which an undescribed"
            " skin problem should be seen regardless?"
        ),
    },
    {
        "id": "paw_licking_alone",
        "claim": "Persistent paw licking with nothing visible is worth investigating on its own.",
        "question_for_reviewer": (
            "Owners report this often and describe no lesion. Merck names pruritus a presentation"
            " in its own right, but we have no source on paw licking specifically. Is it worth a"
            " rule, and does it differ from itching elsewhere?"
        ),
    },
    {
        "id": "vomiting_by_duration_alone",
        "claim": "Vomiting that has continued for several days needs prompt attention.",
        "question_for_reviewer": (
            "We had this as a red rule, reading our '2-7 days' band as Missouri's 'attempts to"
            " vomit continue for more than 24 hours'. A reviewer pointed out that a cat sick once"
            " a day for three days is not what that clause describes, and we could not tell the"
            " two apart, so the rule is gone and duration alone now supports nothing for"
            " vomiting. Is there a duration at which vomiting should be escalated regardless of"
            " frequency, and what is it?"
        ),
    },
    {
        "id": "sting_middle_ground",
        "claim": (
            "A sting with major or spreading swelling, a sting in the mouth or throat, or many"
            " stings at once needs veterinary assessment even when the animal is otherwise well."
        ),
        "question_for_reviewer": (
            "This is the gap left by rewriting the sting rule. Merck says stings are most common"
            " on the face and in the mouth and describes systemic effects from massive"
            " envenomation, but states no threshold for seeking care, so nothing here is ours to"
            " assert. Which of these situations would you escalate, and to what level? The form"
            " does not currently ask about them, because a question whose answer changes nothing"
            " should not be asked."
        ),
    },
    {
        "id": "sting_only_local_signs",
        "claim": "A sting with only mild local swelling can be watched at home.",
        "question_for_reviewer": (
            "The engine now says nothing at all about this case rather than calling it an"
            " emergency. Merck describes local reactions resolving within minutes to 24 hours."
            " Is 'watch at home, seek care if X' something you would sign off, and with what X?"
        ),
    },
    {
        "id": "senior_behaviour_change",
        "claim": "Behaviour changes in older animals often have a medical cause worth investigating.",
        "question_for_reviewer": "Would you score this, and would you separate cognitive from pain-related change?",
    },
)

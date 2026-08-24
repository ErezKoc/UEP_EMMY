import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Button, Card, CheckIcon, Select } from "./ui";
import { capitalize } from "../lib/format";
import { scrollIntoViewSafely } from "../lib/scroll";
import { BODY_AREA_LABELS, SIGN_LABELS } from "../lib/symptomLabels";
import { isSupportedSpecies } from "../lib/species";
import UnsupportedSpeciesNotice from "./UnsupportedSpeciesNotice";
import type {
  AgeCategory,
  Animal,
  BodyArea,
  Concern,
  Duration,
  ItchLevel,
  RedFlag,
  SkinSpread,
  SymptomIntake,
  TimeSinceEating,
  Trend,
} from "../types";

/*
 * The symptom questions.
 *
 * Every question here exists because a cited veterinary source uses it to
 * decide urgency — see backend/app/services/triage/rules.py. Nothing is asked
 * out of curiosity, and everything except the first three answers is skippable.
 *
 * The shape of the form follows from that. The owner's word for the problem on
 * its own tells the rule table almost nothing: "skin or coat" is a category,
 * not a description of the skin. So choosing it opens the questions that page's
 * own framework asks — what is on the skin, how much it bothers the animal, how
 * far it has spread — and those are what the rules read. Each concern below
 * carries its own follow-up list for the same reason, drawn from the signs its
 * sources actually name.
 *
 * WHY THIS IS FOUR STEPS AND NOT ONE PAGE. It used to be one page, which had
 * two problems that mattered more than the scrolling. The emergency screen
 * could be walked straight past without answering it, so "you reported none of
 * the emergency warning signs" was printed on results where the owner had
 * simply never looked at the question. And because each concern pulled its own
 * emergency signs forward into its own list, the same sign appeared as an
 * ordinary tick-box under "what are you noticing?" — losing exactly the framing
 * that makes it worth asking. The emergency screen is now its own required
 * step, holds every emergency trigger, and no other step repeats one.
 */

const CONCERNS: Array<{ value: Concern; label: string }> = [
  { value: "skin_or_coat", label: "Skin or coat" },
  { value: "eyes", label: "Eyes" },
  { value: "ears", label: "Ears" },
  { value: "mobility", label: "Limping or movement" },
  { value: "digestion", label: "Digestion" },
  { value: "breathing", label: "Breathing" },
  { value: "urination", label: "Toilet trouble" },
  { value: "behaviour", label: "Behaviour change" },
  { value: "other", label: "Something else" },
];


/*
 * Grouped so the most serious signs are read first, not buried in a list.
 *
 * The membership of this list and of ACCIDENTS below is checked against the
 * backend's EMERGENCY_SCREENING declaration by
 * `test_the_form_and_the_engine_screen_for_the_same_emergencies`. Labels and
 * ordering are ours; WHICH triggers exist is not.
 */
const URGENT_SIGNS: RedFlag[] = [
  "trouble_breathing",
  "rapid_breathing_at_rest",
  "collapse_or_unresponsive",
  "pale_gums",
  "seizure",
  "uncontrolled_bleeding",
  "severe_pain",
  "unable_to_urinate",
  "bloated_abdomen_with_retching",
  "blood_in_vomit_or_stool",
  "eye_injury",
  "limb_cannot_move",
];

/** Accidents get their own question — owners think in events, not symptoms. */
const ACCIDENTS: RedFlag[] = [
  "major_trauma",
  "overheating",
  "choking",
  "insect_sting_reaction",
  "suspected_poisoning",
];

/*
 * Everything the emergency step asks about, and the reason nothing else may
 * ask about it. A sign in here is offered once, on a screen that says what it
 * is for. Concern follow-ups used to repeat several of these as ordinary
 * chips — a dog with laboured breathing appeared under "what are you
 * noticing?" alongside "watery eye" — which is the framing this list exists to
 * prevent. `remaining()` below strips them from every other question.
 */
export const EMERGENCY_SCREEN_FLAGS: RedFlag[] = [...URGENT_SIGNS, ...ACCIDENTS];

/*
 * The ordinary eye signs, and the reason they exist.
 *
 * The form used to offer only the warning signs below, while the rule resting
 * on VCA's page described "redness and watering" back to the owner — signs
 * this form never gave them a way to report. Asking is what lets the rule
 * quote the owner instead of the source; see `eye_signs_without_injury`.
 */
const EYE_ORDINARY_SIGNS: RedFlag[] = ["eye_redness", "eye_watering", "eye_irritation"];

const EYE_WARNING_SIGNS: RedFlag[] = [
  "eye_pain_or_closed",
  "eye_cloudy_or_blue",
  "unequal_pupils_or_vision_change",
  "eye_bulging_or_severe_swelling",
  "eye_discharge_yellow_green_or_bloody",
  "eye_chemical_exposure",
];

const EAR_SIGNS: RedFlag[] = [
  "ear_head_shaking_or_scratching",
  "ear_odor",
  "ear_discharge",
  "ear_redness",
  "ear_pain",
];

const EAR_WARNING_SIGNS: RedFlag[] = [
  "ear_head_tilt",
  "ear_balance_problems",
  "ear_rapid_eye_movements",
  "ear_sudden_hearing_loss",
  "ear_facial_droop",
  "ear_bloody_or_pus_discharge",
  "ear_flap_swelling",
  "ear_self_injury",
  "ear_foreign_body",
];

const SKIN_SIGNS: RedFlag[] = [
  "skin_itching",
  "skin_redness",
  "skin_hair_loss",
  "skin_rash_or_bumps",
  "skin_scabs_or_flaking",
  "skin_swelling",
  "skin_lump",
  "skin_nail_or_pad_change",
  "skin_open_wound",
  "skin_discharge_or_pus",
  "skin_odor",
  "skin_contagion",
];

const OTHER_SIGNS: RedFlag[] = [
  "vomiting",
  "diarrhoea",
  "black_tarry_stool",
  "not_eating",
  "extreme_lethargy",
  "drinking_much_more",
];

/*
 * The follow-up question each concern opens, and the signs it offers.
 *
 * These are not new signs: they are the ones a source already covers, pulled to
 * the front for the concern they belong to. A sign shown here is removed from
 * the general lists further down the form, so nothing is ever asked twice — and
 * anything the emergency step already asked is removed from here for the same
 * reason. A concern whose list is entirely emergency signs (breathing, and
 * limping) therefore opens no sign question at all, because the screen before
 * it has already collected every one of them.
 */
const CONCERN_FOLLOW_UP: Partial<
  Record<Concern, { label: string; hint?: string; signs: RedFlag[] }>
> = {
  skin_or_coat: {
    label: "What are you noticing on the skin or coat?",
    hint: "Tap all that apply. A skin problem is identified by what is on the skin, so this is the question that decides the answer.",
    signs: SKIN_SIGNS,
  },
  eyes: {
    label: "What are you noticing with the eye?",
    hint: "Tap all that apply. The later ones can change how quickly your pet should be examined.",
    signs: [...EYE_ORDINARY_SIGNS, ...EYE_WARNING_SIGNS],
  },
  ears: {
    label: "What are you noticing with the ear?",
    hint: "Tap all that apply.",
    signs: EAR_SIGNS,
  },
  mobility: {
    label: "What are you noticing?",
    hint: "Tap all that apply.",
    signs: ["limb_cannot_move", "severe_pain", "major_trauma"],
  },
  digestion: {
    label: "What are you noticing?",
    hint: "Tap all that apply.",
    signs: [
      "vomiting",
      "vomiting_many_times",
      "diarrhoea",
      "blood_in_vomit_or_stool",
      "black_tarry_stool",
      "not_eating",
      "bloated_abdomen_with_retching",
    ],
  },
  breathing: {
    label: "What are you noticing?",
    hint: "Tap all that apply.",
    signs: [
      "trouble_breathing",
      "rapid_breathing_at_rest",
      "pale_gums",
      "choking",
      "collapse_or_unresponsive",
    ],
  },
  urination: {
    label: "What are you noticing?",
    hint: "Tap all that apply.",
    // "Blood in vomit or stool" is not offered here. Half of it is not a toilet
    // sign at all, and an owner reading it under this heading has to work out
    // which half is being asked about. It stays on the emergency step, which is
    // shown for every concern, so nothing is lost by removing it — it is still
    // reachable, just under a heading it fits.
    signs: ["unable_to_urinate", "drinking_much_more"],
  },
  behaviour: {
    label: "What are you noticing?",
    hint: "Tap all that apply.",
    signs: [
      "extreme_lethargy",
      "not_eating",
      "drinking_much_more",
      "seizure",
      "collapse_or_unresponsive",
      "ear_head_tilt",
      "ear_balance_problems",
    ],
  },
};

/*
 * Where the problem is — asked only where an answer can be used, and never
 * where the first question has already answered it. "Eyes" then "Eye" was the
 * same question twice; eye and ear concerns now fill the area in themselves.
 */

const ALL_BODY_AREAS = Object.keys(BODY_AREA_LABELS) as BodyArea[];

const BODY_AREA_QUESTION: Partial<Record<Concern, { label: string; hint?: string; areas: BodyArea[] }>> = {
  skin_or_coat: {
    label: "Where is it?",
    hint: "Whether a skin problem sits in one place or several is part of what a vet uses to narrow the cause.",
    areas: ALL_BODY_AREAS,
  },
  mobility: {
    label: "Which part is affected?",
    areas: ["legs_or_paws", "back", "tail", "all_over"],
  },
  behaviour: {
    label: "Is it focused on one part of the body?",
    hint: "Skip this if it isn't.",
    areas: ALL_BODY_AREAS,
  },
  other: {
    label: "Where on the body is it?",
    hint: "Skip this if it isn't in one place.",
    areas: ALL_BODY_AREAS,
  },
};

const DURATIONS: Array<{ value: Duration; label: string }> = [
  { value: "today", label: "Started today" },
  { value: "days_2_7", label: "2–7 days" },
  { value: "weeks_1_4", label: "1–4 weeks" },
  { value: "over_month", label: "Over a month" },
];

const TRENDS: Array<{ value: Trend; label: string }> = [
  { value: "worsening", label: "Getting worse" },
  { value: "unchanged", label: "About the same" },
  { value: "improving", label: "Getting better" },
];

const ITCH_LEVELS: Array<{ value: ItchLevel; label: string }> = [
  { value: "none", label: "Not obviously bothered" },
  { value: "occasional", label: "Licks or scratches sometimes" },
  { value: "frequent", label: "Licks or scratches a lot" },
  { value: "cannot_settle", label: "Can't settle because of it" },
];

const SKIN_SPREADS: Array<{ value: SkinSpread; label: string }> = [
  { value: "one_area", label: "One small area" },
  { value: "several_areas", label: "Several areas" },
  { value: "widespread", label: "Most of the body" },
];

const TIME_SINCE_EATING: Array<{ value: TimeSinceEating; label: string }> = [
  { value: "under_12h", label: "Less than 12 hours" },
  { value: "h12_to_24h", label: "12–24 hours" },
  { value: "over_24h", label: "More than 24 hours" },
];

/** A paw is two different problems wearing one word. Ask which. */
type PawIssue = "skin" | "limb";

const NO_PET = "";

/*
 * The bands the rules actually read, in an owner's words.
 *
 * "Not sure" is offered on purpose and means exactly that: it is submitted as
 * unknown, and the rules that need a known age simply do not apply. Forcing a
 * guess would put a wrong age into a record a veterinarian later reads, which
 * is worse than an honest gap.
 */
const AGE_OPTIONS: Array<{ value: AgeCategory | ""; label: string }> = [
  { value: "baby", label: "Puppy or kitten" },
  { value: "young", label: "Young" },
  { value: "adult", label: "Adult" },
  { value: "senior", label: "Senior" },
  { value: "unknown", label: "Not sure" },
];

const SPECIES_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "dog", label: "Dog" },
  { value: "cat", label: "Cat" },
];

// ---------------------------------------------------------------- the steps

type StepId = "identity" | "concern" | "emergency" | "details";

const STEPS: StepId[] = ["identity", "concern", "emergency", "details"];

const STEP_HEADINGS: Record<StepId, { title: string; description: string }> = {
  identity: {
    title: "Who is this about?",
    description:
      "Some of our guidance applies only to dogs, and some only to cats, so we ask before answering.",
  },
  concern: {
    title: "What is the main concern?",
    description: "Pick the one that fits best. You can add anything else in a moment.",
  },
  emergency: {
    title: "Is any of this happening right now?",
    description:
      "These need emergency care whatever else is going on, so we ask everyone. Please answer even if the answer is no.",
  },
  details: {
    title: "A little more about the problem",
    description:
      "These questions come from published veterinary guidance. Answer what you can — anything you skip is simply not used.",
  },
};

/** Which answer each step will not let you past. */
type FieldId = StepId;

// ------------------------------------------------------------------ draft

/*
 * An in-progress intake, kept for the length of the tab.
 *
 * Losing eight answers to a stray refresh, on a form someone is filling in
 * because their animal is unwell, is a bad enough moment to be worth the
 * storage. sessionStorage rather than localStorage for the same reason the
 * finished result uses it: it dies with the tab, which is the right lifetime
 * for this on a shared computer.
 */
const DRAFT_KEY = "symptom-check:draft";

interface IntakeDraft {
  step: StepId;
  petId: string;
  species: string;
  concern: Concern | null;
  bodyArea: BodyArea | null;
  duration: Duration | null;
  trend: Trend | null;
  redFlags: RedFlag[];
  emergencyAnswer: EmergencyAnswer;
  timeSinceEating: TimeSinceEating | null;
  chronicIllness: boolean | null;
  weightBearing: boolean | null;
  itchLevel: ItchLevel | null;
  skinSpread: SkinSpread | null;
  pawIssue: PawIssue | null;
}

type EmergencyAnswer = "none" | "signs" | null;

function readDraft(): Partial<IntakeDraft> | null {
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<IntakeDraft>;
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null; // Private mode, quota, or a shape from an older build.
  }
}

/** Called by the page on submit and on "Start over"; see SymptomCheckPage. */
export function clearIntakeDraft(): void {
  try {
    sessionStorage.removeItem(DRAFT_KEY);
  } catch {
    // Storage unavailable. Nothing was saved, so nothing needs clearing.
  }
}

// ------------------------------------------------------------- primitives

/** Bring a group into view and put the caret on its first control. */
function focusGroup(element: HTMLElement | null): void {
  if (!element) return;
  scrollIntoViewSafely(element, "center");
  const control = element.querySelector<HTMLElement>(
    'button:not([disabled]), select:not([disabled]), input:not([disabled])',
  );
  // preventScroll so the browser does not fight the scroll above.
  control?.focus({ preventScroll: true });
}

function Chip({
  selected,
  onClick,
  tone = "default",
  children,
}: {
  selected: boolean;
  onClick: () => void;
  /** "urgent" chips are emergency triggers; "none" is the opt-out. */
  tone?: "default" | "urgent" | "none";
  children: ReactNode;
}) {
  const palette =
    tone === "urgent"
      ? {
          on: "border-rose-500 bg-rose-100 text-rose-900",
          off: "border-rose-200 bg-white text-slate-700 hover:border-rose-400 hover:bg-rose-50",
        }
      : tone === "none"
        ? {
            on: "border-emerald-500 bg-emerald-100 text-emerald-900",
            off: "border-emerald-300 bg-white text-emerald-800 hover:border-emerald-500 hover:bg-emerald-50",
          }
        : {
            on: "border-primary-500 bg-primary-100 text-primary-900",
            off: "border-slate-300 bg-white text-slate-700 hover:border-primary-400 hover:bg-slate-50",
          };

  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      // min-h-11 is 44px: the smallest target that is comfortable on a phone,
      // which is where this form is mostly used.
      className={`inline-flex min-h-11 items-center gap-2 rounded-full border-2 px-4 py-2 text-left text-sm transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600 ${
        selected ? `${palette.on} font-semibold` : palette.off
      }`}
    >
      {/*
        A tick as well as the colour change. Selected state carried by fill
        alone is the first thing to disappear for a colour-blind owner, and the
        chips were previously a pale tint away from unselected.
      */}
      <span
        aria-hidden
        className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${
          selected ? "border-current bg-white/70" : "border-slate-300"
        }`}
      >
        {selected && <CheckIcon className="h-3 w-3" />}
      </span>
      {children}
    </button>
  );
}

function Question({
  label,
  hint,
  error,
  groupRef,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  groupRef?: React.Ref<HTMLFieldSetElement>;
  children: ReactNode;
}) {
  return (
    <fieldset
      ref={groupRef}
      className={`border-t border-slate-100 pt-4 first:border-t-0 first:pt-0 ${
        error ? "rounded-lg border border-rose-300 bg-rose-50/60 p-4" : ""
      }`}
    >
      <legend className="mb-2 text-sm font-medium text-slate-700">{label}</legend>
      {hint && <p className="mb-2 -mt-1 text-xs text-slate-500">{hint}</p>}
      {/*
        Beside the question, not at the foot of the page. The species error used
        to render under the submit button, several screens below the field it
        was about.
      */}
      {error && (
        <p className="mb-3 flex items-start gap-2 text-sm font-medium text-rose-700" role="alert">
          <span aria-hidden>!</span>
          {error}
        </p>
      )}
      <div className="flex flex-wrap gap-2">{children}</div>
    </fieldset>
  );
}

function StepProgress({ current }: { current: StepId }) {
  const index = STEPS.indexOf(current);
  return (
    <div className="mb-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Step {index + 1} of {STEPS.length}
        </p>
        <p className="text-xs text-slate-400">{Math.round(((index + 1) / STEPS.length) * 100)}%</p>
      </div>
      <div
        className="mt-2 flex gap-1.5"
        role="progressbar"
        aria-valuemin={1}
        aria-valuemax={STEPS.length}
        aria-valuenow={index + 1}
        aria-valuetext={`Step ${index + 1} of ${STEPS.length}: ${STEP_HEADINGS[current].title}`}
      >
        {STEPS.map((step, position) => (
          <span
            key={step}
            className={`h-1.5 flex-1 rounded-full ${
              position <= index ? "bg-primary-600" : "bg-slate-200"
            }`}
          />
        ))}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------- form

interface SymptomIntakeFormProps {
  onSubmit: (intake: SymptomIntake) => void;
  /** Disables the controls while an assessment is in flight. */
  busy?: boolean;
  /*
   * Step 1 is owned by the page, because its answer decides two things the
   * form does not handle: which pet the saved check is linked to, and which
   * species scope the rule table applies.
   */
  pets: Animal[];
  selectedPetId: string;
  onSelectPet: (petId: string) => void;
  species: string;
  onSelectSpecies: (species: string) => void;
  ageCategory: AgeCategory | "";
  onSelectAge: (age: AgeCategory | "") => void;
  /** Set when a submit failed, so the answers stay put behind a retry. */
  submitError?: string | null;
}

export default function SymptomIntakeForm({
  onSubmit,
  busy = false,
  pets,
  selectedPetId,
  onSelectPet,
  species,
  onSelectSpecies,
  ageCategory,
  onSelectAge,
  submitError = null,
}: SymptomIntakeFormProps) {
  const draft = useRef<Partial<IntakeDraft> | null>(readDraft()).current;

  const [step, setStep] = useState<StepId>(draft?.step ?? "identity");
  const [concern, setConcern] = useState<Concern | null>(draft?.concern ?? null);
  const [bodyArea, setBodyArea] = useState<BodyArea | null>(draft?.bodyArea ?? null);
  const [duration, setDuration] = useState<Duration | null>(draft?.duration ?? null);
  const [trend, setTrend] = useState<Trend | null>(draft?.trend ?? null);
  const [redFlags, setRedFlags] = useState<RedFlag[]>(draft?.redFlags ?? []);
  const [emergencyAnswer, setEmergencyAnswer] = useState<EmergencyAnswer>(
    draft?.emergencyAnswer ?? null,
  );
  const [timeSinceEating, setTimeSinceEating] = useState<TimeSinceEating | null>(
    draft?.timeSinceEating ?? null,
  );
  const [chronicIllness, setChronicIllness] = useState<boolean | null>(draft?.chronicIllness ?? null);
  const [weightBearing, setWeightBearing] = useState<boolean | null>(draft?.weightBearing ?? null);
  const [itchLevel, setItchLevel] = useState<ItchLevel | null>(draft?.itchLevel ?? null);
  const [skinSpread, setSkinSpread] = useState<SkinSpread | null>(draft?.skinSpread ?? null);
  const [pawIssue, setPawIssue] = useState<PawIssue | null>(draft?.pawIssue ?? null);

  const [errors, setErrors] = useState<Partial<Record<FieldId, string>>>({});

  const identityRef = useRef<HTMLFieldSetElement>(null);
  const concernRef = useRef<HTMLFieldSetElement>(null);
  const emergencyRef = useRef<HTMLFieldSetElement>(null);
  const urgentPanelRef = useRef<HTMLDivElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  // Skipped on the very first render so the page does not steal focus from the
  // top of the document the moment it loads.
  const hasRendered = useRef(false);

  const selectedPet = pets.find((pet) => pet.id === selectedPetId);

  // Keep the draft current. Everything the owner has answered, including which
  // step they were on, so a refresh puts them back where they were.
  useEffect(() => {
    const payload: IntakeDraft = {
      step,
      petId: selectedPetId,
      species,
      concern,
      bodyArea,
      duration,
      trend,
      redFlags,
      emergencyAnswer,
      timeSinceEating,
      chronicIllness,
      weightBearing,
      itchLevel,
      skinSpread,
      pawIssue,
    };
    try {
      sessionStorage.setItem(DRAFT_KEY, JSON.stringify(payload));
    } catch {
      // Storage unavailable; the form still works for this visit.
    }
  }, [
    step,
    selectedPetId,
    species,
    concern,
    bodyArea,
    duration,
    trend,
    redFlags,
    emergencyAnswer,
    timeSinceEating,
    chronicIllness,
    weightBearing,
    itchLevel,
    skinSpread,
    pawIssue,
  ]);

  // A restored draft may name a pet this account no longer has.
  useEffect(() => {
    if (draft?.petId && draft.petId !== selectedPetId && pets.some((p) => p.id === draft.petId)) {
      onSelectPet(draft.petId);
    }
    if (draft?.species && !species) onSelectSpecies(draft.species);
    // Once, from the draft that was read at mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pets]);

  // Moving between steps puts focus on the new step's heading, so a keyboard or
  // screen-reader user is told where they landed instead of being left on a
  // button that has just been replaced.
  useEffect(() => {
    if (!hasRendered.current) {
      hasRendered.current = true;
      return;
    }
    scrollIntoViewSafely(headingRef.current, "start");
    headingRef.current?.focus({ preventScroll: true });
  }, [step]);

  const isEyeConcern = concern === "eyes";
  const isEarConcern = concern === "ears";

  // A paw problem is either dermatology or locomotion, and the rules for the
  // two come from different sources. Asking which keeps the branches clean —
  // and an owner who says "limping" is answering the mobility questions, not
  // the skin ones, whichever chip they started from.
  const asksPawRouting = concern === "skin_or_coat" && bodyArea === "legs_or_paws";
  const effectiveConcern: Concern | null =
    asksPawRouting && pawIssue === "limb" ? "mobility" : concern;

  const isSkinContext = effectiveConcern === "skin_or_coat";
  const isMobilityContext = effectiveConcern === "mobility";

  const followUp = effectiveConcern ? CONCERN_FOLLOW_UP[effectiveConcern] : undefined;
  // Keyed on the effective concern so that routing a paw problem to "limping"
  // also relabels the location question, instead of leaving it asking where
  // the skin problem is.
  const areaQuestion = effectiveConcern ? BODY_AREA_QUESTION[effectiveConcern] : undefined;

  // The emergency step has asked about every trigger already, so no later
  // question may offer one; and anything the concern asks about is dropped
  // from the general lists below it. No sign is offered twice in the flow.
  const emergencyAsked = new Set<RedFlag>(EMERGENCY_SCREEN_FLAGS);
  const followUpSigns = (followUp?.signs ?? []).filter((sign) => !emergencyAsked.has(sign));
  const asked = new Set<RedFlag>([...EMERGENCY_SCREEN_FLAGS, ...followUpSigns]);
  const remaining = (signs: RedFlag[]) => signs.filter((sign) => !asked.has(sign));

  const reportedEmergency = EMERGENCY_SCREEN_FLAGS.some((flag) => redFlags.includes(flag));

  /*
   * Bring the urgent shortcut into view the moment it appears — once, on the
   * first sign ticked, not on every subsequent one. Seventeen chips is more
   * than a phone screen, so an owner who ticks the first one and stops has the
   * offer of an immediate answer sitting below the fold otherwise. Focus is
   * deliberately not moved: they may still be ticking.
   */
  const hadUrgent = useRef(reportedEmergency);
  useEffect(() => {
    if (reportedEmergency && !hadUrgent.current) {
      scrollIntoViewSafely(urgentPanelRef.current, "nearest");
    }
    hadUrgent.current = reportedEmergency;
  }, [reportedEmergency]);

  const toggleFlag = (flag: RedFlag) =>
    setRedFlags((current) =>
      current.includes(flag) ? current.filter((f) => f !== flag) : [...current, flag],
    );

  /*
   * The emergency step and its opt-out are one answer with two shapes, so they
   * are set together. Ticking a sign retracts "none of these"; ticking "none of
   * these" clears the signs. Removing the last sign puts the question back to
   * unanswered rather than silently meaning "no" — the whole point of the step
   * is that "no emergency signs" is something the owner said, not something we
   * inferred from an untouched question.
   */
  const toggleEmergencyFlag = (flag: RedFlag) => {
    const next = redFlags.includes(flag)
      ? redFlags.filter((f) => f !== flag)
      : [...redFlags, flag];
    setRedFlags(next);
    setEmergencyAnswer(EMERGENCY_SCREEN_FLAGS.some((f) => next.includes(f)) ? "signs" : null);
    setErrors((current) => ({ ...current, emergency: undefined }));
  };

  const chooseNoEmergency = () => {
    setRedFlags((current) => current.filter((flag) => !emergencyAsked.has(flag)));
    setEmergencyAnswer("none");
    setErrors((current) => ({ ...current, emergency: undefined }));
  };

  const chips = (signs: RedFlag[]) =>
    signs.map((sign) => (
      <Chip key={sign} selected={redFlags.includes(sign)} onClick={() => toggleFlag(sign)}>
        {SIGN_LABELS[sign] ?? sign}
      </Chip>
    ));

  const validate = (target: StepId): boolean => {
    if (target === "identity" && !selectedPet && !species) {
      setErrors((current) => ({
        ...current,
        identity: "Tell us whether this is a dog or a cat — some guidance applies to only one.",
      }));
      focusGroup(identityRef.current);
      return false;
    }
    if (target === "concern" && !concern) {
      setErrors((current) => ({
        ...current,
        concern: "Choose the main concern so we know which questions to ask.",
      }));
      focusGroup(concernRef.current);
      return false;
    }
    if (target === "emergency" && emergencyAnswer === null) {
      setErrors((current) => ({
        ...current,
        emergency:
          "Please answer this one. Tap any that apply, or tap “None of these” if none do.",
      }));
      focusGroup(emergencyRef.current);
      return false;
    }
    setErrors((current) => ({ ...current, [target]: undefined }));
    return true;
  };

  const goNext = () => {
    if (!validate(step)) return;
    const index = STEPS.indexOf(step);
    if (index < STEPS.length - 1) setStep(STEPS[index + 1]);
  };

  const goBack = () => {
    const index = STEPS.indexOf(step);
    // Answers are state, not step-scoped, so going back shows them as they were.
    if (index > 0) setStep(STEPS[index - 1]);
  };

  const handleSubmit = () => {
    // A second press while the first is in flight would assess and, for a
    // signed-in owner, STORE the same check twice.
    if (busy) return;
    // Re-checked at submit as well as at each Continue, because the emergency
    // step can submit directly and because a restored draft could arrive in any
    // shape.
    for (const field of STEPS) {
      if (field === "details") continue;
      if (!validate(field)) {
        setStep(field);
        return;
      }
    }
    if (!concern || !effectiveConcern) return;
    onSubmit({
      concern: effectiveConcern,
      body_area:
        bodyArea ?? (concern === "eyes" ? "eye" : concern === "ears" ? "ear" : null),
      duration,
      trend,
      red_flags: redFlags,
      time_since_eating: redFlags.includes("not_eating") ? timeSinceEating : null,
      // Display-only, and the reason the result may say "you did not select any
      // of the emergency warning signs": that sentence is a claim about what
      // the owner did, and an empty red_flags list cannot carry it.
      emergency_screen_answered: emergencyAnswer !== null,
      has_chronic_illness: chronicIllness,
      weight_bearing: isMobilityContext ? weightBearing : null,
      itch_level: isSkinContext ? itchLevel : null,
      skin_spread: isSkinContext ? skinSpread : null,
    });
  };

  const heading = STEP_HEADINGS[step];
  const isLastStep = step === "details";
  const urgentShortcut = step === "emergency" && reportedEmergency;
  /*
   * A saved pet the evidence base does not cover.
   *
   * The species CHIPS only offer dog and cat, so this can only be reached by
   * picking a saved rabbit or bird from the dropdown above them — and until
   * now that was allowed straight through to the end, where the engine
   * abstained and the owner had answered four steps for nothing.
   *
   * Checked here rather than in `validate` because there is no answer that
   * would fix it. Validation exists to tell somebody what to change; this
   * cannot be changed, so the step stops offering a way forward instead of
   * showing an error under a question.
   */
  const blockedSpecies = Boolean(selectedPet && !isSupportedSpecies(selectedPet.species));

  return (
    <Card>
      <StepProgress current={step} />

      <h2
        ref={headingRef}
        tabIndex={-1}
        className="text-lg font-semibold text-slate-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-primary-600"
      >
        {heading.title}
      </h2>
      <p className="mt-1 text-sm text-slate-500">{heading.description}</p>

      <div className="mt-5 space-y-5">
        {step === "identity" && (
          <>
            {pets.length > 0 && (
              <div className="border-b border-slate-100 pb-4">
                <Select
                  label="Pet"
                  value={selectedPetId}
                  onChange={(event) => {
                    onSelectPet(event.target.value);
                    setErrors((current) => ({ ...current, identity: undefined }));
                  }}
                  options={[
                    { value: NO_PET, label: "Not one of my saved pets" },
                    ...pets.map((pet) => ({
                      value: pet.id,
                      label: `${pet.name} (${capitalize(pet.species)})`,
                    })),
                  ]}
                  hint="Picking a saved pet fills in their species and age for you."
                />
              </div>
            )}

            {selectedPet && blockedSpecies ? (
              <UnsupportedSpeciesNotice
                species={selectedPet.species}
                petName={selectedPet.name}
                feature="symptom-checker"
              />
            ) : selectedPet ? (
              <p className="rounded-lg bg-slate-100 px-4 py-3 text-sm text-slate-600">
                Using {selectedPet.name}&apos;s details: {capitalize(selectedPet.species)},{" "}
                {selectedPet.age_category}.
              </p>
            ) : (
              <Question
                label="Is this a dog or a cat?"
                hint={
                  pets.length === 0
                    ? "You can add a pet under My Pets to have this filled in next time."
                    : undefined
                }
                error={errors.identity}
                groupRef={identityRef}
              >
                {SPECIES_OPTIONS.map((option) => (
                  <Chip
                    key={option.value}
                    selected={species === option.value}
                    // No toggle-off. Species is required, and the other
                    // single-choice answers that do untoggle are all optional;
                    // letting a second tap empty this one hands the owner a
                    // blocked Continue with no obvious cause.
                    onClick={() => {
                      onSelectSpecies(option.value);
                      setErrors((current) => ({ ...current, identity: undefined }));
                    }}
                  >
                    {option.label}
                  </Chip>
                ))}
              </Question>
            )}

            {/*
              Only when no saved pet is selected — a pet's record already holds
              this, and asking again invites two different answers for the same
              animal.
            */}
            {!selectedPet && (
              <Question
                label="How old are they?"
                hint="Some guidance differs for the very young and the very old, so we ask rather than assume."
              >
                {AGE_OPTIONS.map((option) => (
                  <Chip
                    key={option.value}
                    selected={ageCategory === option.value}
                    onClick={() => onSelectAge(option.value)}
                  >
                    {option.label}
                  </Chip>
                ))}
              </Question>
            )}
          </>
        )}

        {step === "concern" && (
          <Question
            label="What brings you here?"
            hint="Whichever is closest. Nothing here is a diagnosis."
            error={errors.concern}
            groupRef={concernRef}
          >
            {CONCERNS.map((option) => (
              <Chip
                key={option.value}
                selected={concern === option.value}
                onClick={() => {
                  setConcern(option.value);
                  setErrors((current) => ({ ...current, concern: undefined }));
                }}
              >
                {option.label}
              </Chip>
            ))}
          </Question>
        )}

        {step === "emergency" && (
          <>
            <Question
              label="Is your pet showing any of these right now?"
              hint="Tap all that apply."
              error={errors.emergency}
              groupRef={emergencyRef}
            >
              {URGENT_SIGNS.map((sign) => (
                <Chip
                  key={sign}
                  tone="urgent"
                  selected={redFlags.includes(sign)}
                  onClick={() => toggleEmergencyFlag(sign)}
                >
                  {SIGN_LABELS[sign] ?? sign}
                </Chip>
              ))}
            </Question>

            <Question
              label="Has anything happened to them recently?"
              hint="An accident can matter even if your pet seems fine afterwards."
            >
              {ACCIDENTS.map((sign) => (
                <Chip
                  key={sign}
                  tone="urgent"
                  selected={redFlags.includes(sign)}
                  onClick={() => toggleEmergencyFlag(sign)}
                >
                  {SIGN_LABELS[sign] ?? sign}
                </Chip>
              ))}
            </Question>

            <Question label="Or, if none of the above apply:">
              <Chip tone="none" selected={emergencyAnswer === "none"} onClick={chooseNoEmergency}>
                None of these
              </Chip>
            </Question>

            {/*
              The whole reason this step is separate. An owner who has just
              ticked "collapsed" should not have to answer how long the skin
              problem has been going on before we will tell them anything.
            */}
            {reportedEmergency && (
              <div ref={urgentPanelRef} className="rounded-xl border-2 border-rose-300 bg-rose-50 p-4">
                <p className="text-sm font-semibold text-rose-900">
                  You have reported an emergency warning sign.
                </p>
                <p className="mt-1 text-sm text-rose-800">
                  You do not need to answer anything else. Use{" "}
                  <span className="font-semibold">Get urgent guidance now</span> below.
                </p>
              </div>
            )}
          </>
        )}

        {step === "details" && (
          <>
            {areaQuestion && (
              <Question label={areaQuestion.label} hint={areaQuestion.hint}>
                {areaQuestion.areas.map((area) => (
                  <Chip
                    key={area}
                    selected={bodyArea === area}
                    onClick={() => setBodyArea(bodyArea === area ? null : area)}
                  >
                    {BODY_AREA_LABELS[area]}
                  </Chip>
                ))}
              </Question>
            )}

            {asksPawRouting && (
              <Question
                label="Is this mainly a skin, nail or pad problem, or are they limping?"
                hint="A paw can be either, and the guidance is different for each."
              >
                <Chip selected={pawIssue === "skin"} onClick={() => setPawIssue("skin")}>
                  Skin, nail, or pad
                </Chip>
                <Chip selected={pawIssue === "limb"} onClick={() => setPawIssue("limb")}>
                  Limping or not using the leg
                </Chip>
              </Question>
            )}

            {followUp && followUpSigns.length > 0 && (
              <Question label={followUp.label} hint={followUp.hint}>
                {chips(followUpSigns)}
              </Question>
            )}

            {isSkinContext && (
              <>
                <Question label="How much is it bothering them?">
                  {ITCH_LEVELS.map((option) => (
                    <Chip
                      key={option.value}
                      selected={itchLevel === option.value}
                      onClick={() => setItchLevel(itchLevel === option.value ? null : option.value)}
                    >
                      {option.label}
                    </Chip>
                  ))}
                </Question>

                <Question
                  label="How widespread is it?"
                  hint="Recorded for the vet: whether a skin problem is in one place or many is part of how the cause is narrowed down."
                >
                  {SKIN_SPREADS.map((option) => (
                    <Chip
                      key={option.value}
                      selected={skinSpread === option.value}
                      onClick={() =>
                        setSkinSpread(skinSpread === option.value ? null : option.value)
                      }
                    >
                      {option.label}
                    </Chip>
                  ))}
                </Question>
              </>
            )}

            {isEarConcern && (
              <details className="rounded-lg border border-rose-200 bg-rose-50/60 px-4 py-3">
                <summary className="min-h-11 cursor-pointer py-2 text-sm font-semibold text-rose-700">
                  Check urgent ear warning signs
                </summary>
                <div className="mt-3">
                  <Question label="Select any that apply">
                    {chips(remaining(EAR_WARNING_SIGNS))}
                  </Question>
                </div>
              </details>
            )}

            {isMobilityContext && (
              <Question label="Can they put weight on the leg?">
                <Chip selected={weightBearing === true} onClick={() => setWeightBearing(true)}>
                  Yes
                </Chip>
                <Chip selected={weightBearing === false} onClick={() => setWeightBearing(false)}>
                  No
                </Chip>
              </Question>
            )}

            <Question label="How long has this been going on?">
              {DURATIONS.map((option) => (
                <Chip
                  key={option.value}
                  selected={duration === option.value}
                  onClick={() => setDuration(duration === option.value ? null : option.value)}
                >
                  {option.label}
                </Chip>
              ))}
            </Question>

            <Question label="Since it started, is it…">
              {TRENDS.map((option) => (
                <Chip
                  key={option.value}
                  selected={trend === option.value}
                  onClick={() => setTrend(trend === option.value ? null : option.value)}
                >
                  {option.label}
                </Chip>
              ))}
            </Question>

            {redFlags.includes("not_eating") && (
              <Question label="How long since they last ate?">
                {TIME_SINCE_EATING.map((option) => (
                  <Chip
                    key={option.value}
                    selected={timeSinceEating === option.value}
                    onClick={() =>
                      setTimeSinceEating(timeSinceEating === option.value ? null : option.value)
                    }
                  >
                    {option.label}
                  </Chip>
                ))}
              </Question>
            )}

            {(effectiveConcern === "digestion" ||
              redFlags.includes("vomiting") ||
              redFlags.includes("diarrhoea")) && (
              <Question
                label="Does your pet have a long-term illness?"
                hint="Such as kidney disease, diabetes, or heart disease — it changes how urgent some signs are."
              >
                <Chip selected={chronicIllness === true} onClick={() => setChronicIllness(true)}>
                  Yes
                </Chip>
                <Chip selected={chronicIllness === false} onClick={() => setChronicIllness(false)}>
                  No
                </Chip>
              </Question>
            )}

            {/*
              Everything above is about the problem the owner came with. This is
              a separate question — signs somewhere else on the animal — and it
              stays closed, because it is the longest list in the form and the
              least likely to be needed.
            */}
            <details className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
              <summary className="min-h-11 cursor-pointer py-2 text-sm font-semibold text-slate-700">
                Anything else going on, elsewhere in the body?{" "}
                <span className="font-normal text-slate-500">(optional)</span>
              </summary>
              <div className="mt-3 space-y-4">
                <Question
                  label="Other symptoms, unrelated to what you described above"
                  hint="Tap all that apply."
                >
                  {chips(remaining(OTHER_SIGNS))}
                </Question>
                {!isEyeConcern && (
                  <Question label="Anything with the eyes?">
                    {chips(remaining([...EYE_ORDINARY_SIGNS, ...EYE_WARNING_SIGNS]))}
                  </Question>
                )}
                {!isEarConcern && (
                  <Question label="Anything with the ears?">
                    {chips(remaining([...EAR_SIGNS, ...EAR_WARNING_SIGNS]))}
                  </Question>
                )}
                {!isSkinContext && (
                  <Question label="Anything on the skin?">{chips(remaining(SKIN_SIGNS))}</Question>
                )}
              </div>
            </details>
          </>
        )}
      </div>

      {/*
        The API refused the last submit. The answers are all still here, so the
        only thing to offer is another go.
      */}
      {submitError && (
        <p
          className="mt-5 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700"
          role="alert"
        >
          {submitError}
        </p>
      )}

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
        {step === "identity" ? (
          <span />
        ) : (
          <Button
            variant="secondary"
            className="min-h-11"
            onClick={goBack}
            disabled={busy}
            /*
              The visible word stays "Back" — but on the limping step one of the
              body-area chips is also called "Back", because that is where the
              problem is. Two controls with the same accessible name and
              different meanings is a bad enough moment for a screen-reader user
              that the step control spells itself out. The visible label is kept
              inside the accessible name so voice control still matches it.
            */
            aria-label="Back to the previous step"
          >
            Back
          </Button>
        )}

        {/*
          One forward action, always. While an emergency sign is selected the
          ordinary Continue is not rendered: offering "carry on answering
          questions" beside "get urgent guidance now" asks an owner whose animal
          may be collapsing to choose between them, and the wrong choice costs
          them the rest of the form.
        */}
        {urgentShortcut ? (
          <Button
            variant="danger"
            className="min-h-11"
            onClick={handleSubmit}
            loading={busy}
            disabled={busy}
          >
            {submitError ? "Try again" : "Get urgent guidance now"}
          </Button>
        ) : isLastStep ? (
          <Button className="min-h-11" onClick={handleSubmit} loading={busy} disabled={busy}>
            {submitError ? "Try again" : "Get advice"}
          </Button>
        ) : blockedSpecies ? (
          /*
            Nothing here. The notice on this step already offers the two things
            that do work for this pet, and a disabled Continue beside it would
            read as a thing to unlock rather than a scope the product has —
            leaving the owner hunting for the answer that turns it back on.
          */
          <span />
        ) : (
          <Button className="min-h-11" onClick={goNext} disabled={busy}>
            Continue
          </Button>
        )}
      </div>
    </Card>
  );
}

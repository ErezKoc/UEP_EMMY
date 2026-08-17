import { useState } from "react";
import { Button, Card } from "./ui";
import type {
  BodyArea,
  Concern,
  Duration,
  RedFlag,
  SymptomIntake,
  TimeSinceEating,
  Trend,
} from "../types";

/*
 * The symptom questions.
 *
 * Every question here exists because a cited veterinary source uses it to
 * decide urgency — see backend/app/services/triage/rules.py. Nothing is asked
 * out of curiosity, and everything except the first question is skippable.
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

const BODY_AREAS: Array<{ value: BodyArea; label: string }> = [
  { value: "head_or_face", label: "Head or face" },
  { value: "ear", label: "Ear" },
  { value: "eye", label: "Eye" },
  { value: "mouth", label: "Mouth" },
  { value: "chest", label: "Chest" },
  { value: "belly", label: "Belly" },
  { value: "back", label: "Back" },
  { value: "legs_or_paws", label: "Legs or paws" },
  { value: "tail", label: "Tail" },
  { value: "all_over", label: "All over" },
];

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

/** Grouped so the most serious signs are read first, not buried in a list. */
const URGENT_SIGNS: Array<{ value: RedFlag; label: string }> = [
  { value: "trouble_breathing", label: "Breathing hard or fast" },
  { value: "collapse_or_unresponsive", label: "Collapsed, can't stand, or unresponsive" },
  { value: "pale_gums", label: "Gums look pale or white" },
  { value: "seizure", label: "Had a seizure" },
  { value: "uncontrolled_bleeding", label: "Bleeding that won't stop" },
  { value: "severe_pain", label: "Seems to be in severe pain" },
  { value: "unable_to_urinate", label: "Straining to urinate, producing little or nothing" },
  { value: "bloated_abdomen_with_retching", label: "Swollen belly with retching" },
  { value: "blood_in_vomit_or_stool", label: "Blood in vomit or stool" },
  { value: "eye_injury", label: "Injury to the eye" },
  { value: "limb_cannot_move", label: "A limb can't move / possible broken bone" },
];

const EYE_WARNING_SIGNS: Array<{ value: RedFlag; label: string }> = [
  { value: "eye_pain_or_closed", label: "Squinting, keeping the eye closed, or seems painful" },
  { value: "eye_cloudy_or_blue", label: "Cloudy, blue, or white area on the eye" },
  { value: "unequal_pupils_or_vision_change", label: "Unequal pupils or not seeing normally" },
  { value: "eye_bulging_or_severe_swelling", label: "Bulging eye or marked swelling" },
  {
    value: "eye_discharge_yellow_green_or_bloody",
    label: "Yellow-green or bloody discharge",
  },
  { value: "eye_chemical_exposure", label: "Possible chemical exposure" },
];

const EAR_SIGNS: Array<{ value: RedFlag; label: string }> = [
  { value: "ear_head_shaking_or_scratching", label: "Head shaking or scratching the ear" },
  { value: "ear_odor", label: "Unusual or bad smell" },
  { value: "ear_discharge", label: "Discharge, wax, or debris" },
  { value: "ear_redness", label: "Redness inside or around the ear" },
  { value: "ear_pain", label: "Pain when the ear is touched" },
];

const EAR_WARNING_SIGNS: Array<{ value: RedFlag; label: string }> = [
  { value: "ear_head_tilt", label: "New head tilt" },
  { value: "ear_balance_problems", label: "Stumbling, circling, or losing balance" },
  { value: "ear_rapid_eye_movements", label: "Rapid side-to-side eye movements" },
  { value: "ear_sudden_hearing_loss", label: "Sudden hearing loss" },
  { value: "ear_facial_droop", label: "One side of the face is drooping" },
  { value: "ear_bloody_or_pus_discharge", label: "Bloody or pus-like discharge" },
  { value: "ear_flap_swelling", label: "Major or fluid-filled swelling of the ear flap" },
  { value: "ear_self_injury", label: "Scratching or shaking is causing an injury" },
  { value: "ear_foreign_body", label: "Possible grass seed or other object in the ear" },
];

/** Accidents get their own question — owners think in events, not symptoms. */
const ACCIDENTS: Array<{ value: RedFlag; label: string }> = [
  { value: "major_trauma", label: "Hit by a car, a fall, or attacked" },
  { value: "overheating", label: "Got too hot / left somewhere hot" },
  { value: "choking", label: "Choking or gagging non-stop" },
  { value: "insect_sting_reaction", label: "Stung, with swelling" },
  { value: "suspected_poisoning", label: "Ate something poisonous" },
];

const OTHER_SIGNS: Array<{ value: RedFlag; label: string }> = [
  { value: "vomiting", label: "Vomiting" },
  { value: "diarrhoea", label: "Diarrhoea" },
  { value: "black_tarry_stool", label: "Black or tarry stool" },
  { value: "not_eating", label: "Not eating" },
  { value: "extreme_lethargy", label: "Very tired, won't move much" },
  { value: "drinking_much_more", label: "Drinking much more than usual" },
];

const TIME_SINCE_EATING: Array<{ value: TimeSinceEating; label: string }> = [
  { value: "under_12h", label: "Less than 12 hours" },
  { value: "h12_to_24h", label: "12–24 hours" },
  { value: "over_24h", label: "More than 24 hours" },
];

function Chip({
  selected,
  onClick,
  children,
}: {
  selected: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
        selected
          ? "border-primary-500 bg-primary-50 font-medium text-primary-700"
          : "border-slate-300 bg-white text-slate-600 hover:border-primary-300 hover:bg-slate-50"
      }`}
    >
      {children}
    </button>
  );
}

function Question({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <fieldset className="border-t border-slate-100 pt-4 first:border-t-0 first:pt-0">
      <legend className="mb-2 text-sm font-medium text-slate-700">{label}</legend>
      {hint && <p className="mb-2 -mt-1 text-xs text-slate-500">{hint}</p>}
      <div className="flex flex-wrap gap-2">{children}</div>
    </fieldset>
  );
}

interface SymptomIntakeFormProps {
  onSubmit: (intake: SymptomIntake) => void;
  /** Omit to hide the escape hatch — the symptom checker has nothing to skip to. */
  onSkip?: () => void;
  title?: string;
  description?: string;
  submitLabel?: string;
  skipLabel?: string;
  /** Disables the submit button while an assessment is in flight. */
  busy?: boolean;
}

export default function SymptomIntakeForm({
  onSubmit,
  onSkip,
  title = "What's going on?",
  description = "These questions come from published veterinary guidance. Answer what you can — anything you skip is simply not used.",
  submitLabel = "Get advice",
  skipLabel = "Skip",
  busy = false,
}: SymptomIntakeFormProps) {
  const [concern, setConcern] = useState<Concern | null>(null);
  const [bodyArea, setBodyArea] = useState<BodyArea | null>(null);
  const [duration, setDuration] = useState<Duration | null>(null);
  const [trend, setTrend] = useState<Trend | null>(null);
  const [redFlags, setRedFlags] = useState<RedFlag[]>([]);
  const [timeSinceEating, setTimeSinceEating] = useState<TimeSinceEating | null>(null);
  const [chronicIllness, setChronicIllness] = useState<boolean | null>(null);
  const [weightBearing, setWeightBearing] = useState<boolean | null>(null);
  const isEyeConcern = concern === "eyes" || bodyArea === "eye";
  const isEarConcern = concern === "ears" || bodyArea === "ear";
  const isFocusedConcern = isEyeConcern || isEarConcern;

  const toggleFlag = (flag: RedFlag) =>
    setRedFlags((current) =>
      current.includes(flag) ? current.filter((f) => f !== flag) : [...current, flag],
    );

  const handleSubmit = () => {
    if (!concern) return;
    onSubmit({
      concern,
      body_area:
        bodyArea ?? (concern === "eyes" ? "eye" : concern === "ears" ? "ear" : null),
      duration,
      trend,
      red_flags: redFlags,
      time_since_eating: redFlags.includes("not_eating") ? timeSinceEating : null,
      has_chronic_illness: chronicIllness,
      weight_bearing: concern === "mobility" ? weightBearing : null,
    });
  };

  return (
    <Card title={title} description={description}>
      <div className="mt-5 space-y-5">
        <Question label="What brings you here?">
          {CONCERNS.map((option) => (
            <Chip
              key={option.value}
              selected={concern === option.value}
              onClick={() => setConcern(option.value)}
            >
              {option.label}
            </Chip>
          ))}
        </Question>

        {concern && (
          <>
            {!isFocusedConcern && (
              <Question label="Is your pet showing any of these right now?" hint="Tap all that apply.">
                {URGENT_SIGNS.map((option) => (
                  <Chip
                    key={option.value}
                    selected={redFlags.includes(option.value)}
                    onClick={() => toggleFlag(option.value)}
                  >
                    {option.label}
                  </Chip>
                ))}
              </Question>
            )}

            {isEyeConcern && (
              <Question
                label="Are any of these happening with the eye?"
                hint="These signs can change how quickly your pet should be examined."
              >
                {EYE_WARNING_SIGNS.map((option) => (
                  <Chip
                    key={option.value}
                    selected={redFlags.includes(option.value)}
                    onClick={() => toggleFlag(option.value)}
                  >
                    {option.label}
                  </Chip>
                ))}
              </Question>
            )}

            {isEarConcern && (
              <>
                <Question label="What are you noticing with the ear?" hint="Tap all that apply.">
                  {EAR_SIGNS.map((option) => (
                    <Chip
                      key={option.value}
                      selected={redFlags.includes(option.value)}
                      onClick={() => toggleFlag(option.value)}
                    >
                      {option.label}
                    </Chip>
                  ))}
                </Question>

                <details className="rounded-lg border border-rose-200 bg-rose-50/60 px-4 py-3">
                  <summary className="cursor-pointer text-sm font-semibold text-rose-700">
                    Check urgent ear warning signs
                  </summary>
                  <div className="mt-3">
                    <Question label="Select any that apply">
                      {EAR_WARNING_SIGNS.map((option) => (
                        <Chip
                          key={option.value}
                          selected={redFlags.includes(option.value)}
                          onClick={() => toggleFlag(option.value)}
                        >
                          {option.label}
                        </Chip>
                      ))}
                    </Question>
                  </div>
                </details>
              </>
            )}

            {isFocusedConcern ? (
              <details className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                <summary className="cursor-pointer text-sm font-semibold text-slate-700">
                  Other symptoms or a recent accident
                </summary>
                <div className="mt-3 space-y-4">
                  <Question label="Other urgent signs">
                    {URGENT_SIGNS.map((option) => (
                      <Chip
                        key={option.value}
                        selected={redFlags.includes(option.value)}
                        onClick={() => toggleFlag(option.value)}
                      >
                        {option.label}
                      </Chip>
                    ))}
                  </Question>
                  <Question label="Recent accidents or exposures">
                    {ACCIDENTS.map((option) => (
                      <Chip
                        key={option.value}
                        selected={redFlags.includes(option.value)}
                        onClick={() => toggleFlag(option.value)}
                      >
                        {option.label}
                      </Chip>
                    ))}
                  </Question>
                  <Question label="Other symptoms">
                    {OTHER_SIGNS.map((option) => (
                      <Chip
                        key={option.value}
                        selected={redFlags.includes(option.value)}
                        onClick={() => toggleFlag(option.value)}
                      >
                        {option.label}
                      </Chip>
                    ))}
                  </Question>
                </div>
              </details>
            ) : (
              <>
                <Question
                  label="Has anything happened to them?"
                  hint="An accident can matter even if your pet seems fine afterwards."
                >
                  {ACCIDENTS.map((option) => (
                    <Chip
                      key={option.value}
                      selected={redFlags.includes(option.value)}
                      onClick={() => toggleFlag(option.value)}
                    >
                      {option.label}
                    </Chip>
                  ))}
                </Question>

                <Question label="And any of these?">
                  {OTHER_SIGNS.map((option) => (
                    <Chip
                      key={option.value}
                      selected={redFlags.includes(option.value)}
                      onClick={() => toggleFlag(option.value)}
                    >
                      {option.label}
                    </Chip>
                  ))}
                </Question>
              </>
            )}

            {redFlags.includes("not_eating") && (
              <Question label="How long since they last ate?">
                {TIME_SINCE_EATING.map((option) => (
                  <Chip
                    key={option.value}
                    selected={timeSinceEating === option.value}
                    onClick={() => setTimeSinceEating(option.value)}
                  >
                    {option.label}
                  </Chip>
                ))}
              </Question>
            )}

            {concern !== "eyes" && concern !== "ears" && (
              <Question label="Where on the body?">
                {BODY_AREAS.map((option) => (
                  <Chip
                    key={option.value}
                    selected={bodyArea === option.value}
                    onClick={() => setBodyArea(bodyArea === option.value ? null : option.value)}
                  >
                    {option.label}
                  </Chip>
                ))}
              </Question>
            )}

            <Question label="How long has this been going on?">
              {DURATIONS.map((option) => (
                <Chip
                  key={option.value}
                  selected={duration === option.value}
                  onClick={() => setDuration(option.value)}
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
                  onClick={() => setTrend(option.value)}
                >
                  {option.label}
                </Chip>
              ))}
            </Question>

            {concern === "mobility" && (
              <Question label="Can they put weight on the leg?">
                <Chip selected={weightBearing === true} onClick={() => setWeightBearing(true)}>
                  Yes
                </Chip>
                <Chip selected={weightBearing === false} onClick={() => setWeightBearing(false)}>
                  No
                </Chip>
              </Question>
            )}

            {(concern === "digestion" ||
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
          </>
        )}
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
        {onSkip ? (
          <button
            type="button"
            onClick={onSkip}
            className="text-sm font-medium text-slate-500 underline hover:text-slate-700"
          >
            {skipLabel}
          </button>
        ) : (
          <span />
        )}
        <Button onClick={handleSubmit} disabled={!concern || busy}>
          {busy ? "Checking…" : submitLabel}
        </Button>
      </div>
    </Card>
  );
}

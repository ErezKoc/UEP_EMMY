import type {
  BodyArea,
  Concern,
  Duration,
  ItchLevel,
  SkinSpread,
  TimeSinceEating,
  Trend,
} from "../types";

/*
 * The owner-facing name for every answer the intake collects.
 *
 * Lifted out of SymptomIntakeForm so the result card can play answers back
 * under "Your answers" without owning a second copy of sixty strings. One list
 * means the summary cannot drift from the question that produced it — which is
 * the whole value of a confirmation summary, and the first thing that breaks
 * when the labels are duplicated.
 *
 * The sign lists themselves stay in the form: `URGENT_SIGNS` and `ACCIDENTS`
 * are checked against the backend's EMERGENCY_SCREENING declaration by a test
 * that reads that file.
 */

export const SIGN_LABELS: Record<string, string> = {
  // Emergency screen
  // Two questions, not one. "Breathing hard or fast" collected a dog in
  // respiratory distress and a dog that had just been running in the same
  // answer, and it fired an unconditional emergency rule.
  trouble_breathing: "Breathing looks difficult or laboured",
  rapid_breathing_at_rest: "Breathing unusually fast while resting",
  collapse_or_unresponsive: "Collapsed, can't stand, or unresponsive",
  pale_gums: "Gums look pale or white",
  seizure: "Had a seizure",
  uncontrolled_bleeding: "Bleeding that won't stop",
  severe_pain: "Seems to be in severe pain",
  unable_to_urinate: "Straining to urinate, producing little or nothing",
  bloated_abdomen_with_retching: "Swollen belly with retching",
  blood_in_vomit_or_stool: "Blood in vomit or stool",
  eye_injury: "Injury to the eye",
  limb_cannot_move: "A limb can't move / possible broken bone",
  // Eye
  eye_redness: "Redness in or around the eye",
  eye_watering: "Watery or runny eye",
  eye_irritation: "Rubbing or pawing at the eye",
  eye_pain_or_closed: "Squinting, keeping the eye closed, or seems painful",
  eye_cloudy_or_blue: "Cloudy, blue, or white area on the eye",
  unequal_pupils_or_vision_change: "Unequal pupils or not seeing normally",
  eye_bulging_or_severe_swelling: "Bulging eye or marked swelling",
  eye_discharge_yellow_green_or_bloody: "Yellow-green or bloody discharge",
  eye_chemical_exposure: "Possible chemical exposure",
  // Ear
  ear_head_shaking_or_scratching: "Head shaking or scratching the ear",
  ear_odor: "Unusual or bad smell",
  ear_discharge: "Discharge, wax, or debris",
  ear_redness: "Redness inside or around the ear",
  ear_pain: "Pain when the ear is touched",
  ear_head_tilt: "New head tilt",
  ear_balance_problems: "Stumbling, circling, or losing balance",
  ear_rapid_eye_movements: "Rapid side-to-side eye movements",
  ear_sudden_hearing_loss: "Sudden hearing loss",
  ear_facial_droop: "One side of the face is drooping",
  ear_bloody_or_pus_discharge: "Bloody or pus-like discharge",
  ear_flap_swelling: "Major or fluid-filled swelling of the ear flap",
  ear_self_injury: "Scratching or shaking is causing an injury",
  ear_foreign_body: "Possible grass seed or other object in the ear",
  // Skin
  skin_itching: "Itching, licking, or chewing at it",
  skin_redness: "Redness",
  skin_hair_loss: "Hair loss or bald patches",
  skin_rash_or_bumps: "Rash or bumps",
  skin_scabs_or_flaking: "Scabs, crusts, or flaking",
  skin_swelling: "Swelling",
  skin_lump: "A lump or nodule",
  skin_nail_or_pad_change: "Change to a nail or paw pad",
  skin_open_wound: "Open, raw skin or a wound that isn't healing",
  skin_discharge_or_pus: "Discharge or pus",
  skin_odor: "A bad smell",
  skin_contagion: "Another pet or someone at home has one too",
  // Accidents
  major_trauma: "Hit by a car, a fall, or attacked",
  overheating: "Got too hot / left somewhere hot",
  choking: "Choking or gagging non-stop",
  // Not "stung, with swelling": the source names an insect sting without
  // qualification, and a chip that only fits stings with visible swelling
  // quietly narrows an emergency criterion nothing we hold narrows.
  insect_sting_reaction: "Stung by an insect",
  suspected_poisoning: "Ate something poisonous",
  // Elsewhere
  vomiting: "Vomiting",
  vomiting_many_times: "Being sick many times in one day",
  diarrhoea: "Diarrhoea",
  black_tarry_stool: "Black or tarry stool",
  not_eating: "Not eating",
  extreme_lethargy: "Very tired, won't move much",
  drinking_much_more: "Drinking much more than usual",
};

export const BODY_AREA_LABELS: Record<BodyArea, string> = {
  head_or_face: "Head or face",
  ear: "Ear",
  eye: "Eye",
  mouth: "Mouth",
  chest: "Chest",
  belly: "Belly",
  back: "Back",
  legs_or_paws: "Legs or paws",
  tail: "Tail",
  all_over: "All over",
};

export const CONCERN_LABELS: Record<Concern, string> = {
  skin_or_coat: "Skin or coat",
  eyes: "Eyes",
  ears: "Ears",
  mobility: "Limping or movement",
  digestion: "Digestion",
  breathing: "Breathing",
  urination: "Toilet trouble",
  behaviour: "Behaviour change",
  other: "Something else",
  breed_only: "Breed estimate only",
};

export const DURATION_LABELS: Record<Duration, string> = {
  today: "Started today",
  days_2_7: "2–7 days",
  weeks_1_4: "1–4 weeks",
  over_month: "Over a month",
};

export const TREND_LABELS: Record<Trend, string> = {
  worsening: "Getting worse",
  unchanged: "About the same",
  improving: "Getting better",
};

export const ITCH_LEVEL_LABELS: Record<ItchLevel, string> = {
  none: "Not obviously bothered",
  occasional: "Licks or scratches sometimes",
  frequent: "Licks or scratches a lot",
  cannot_settle: "Can't settle because of it",
};

export const SKIN_SPREAD_LABELS: Record<SkinSpread, string> = {
  one_area: "One small area",
  several_areas: "Several areas",
  widespread: "Most of the body",
};

export const TIME_SINCE_EATING_LABELS: Record<TimeSinceEating, string> = {
  under_12h: "Less than 12 hours",
  h12_to_24h: "12–24 hours",
  over_24h: "More than 24 hours",
};

/** Falls back to the raw value, so an older stored answer still reads. */
export function labelFor<T extends string>(
  labels: Record<string, string>,
  value: T | null | undefined,
): string | null {
  if (!value) return null;
  return labels[value] ?? String(value).replace(/_/g, " ");
}

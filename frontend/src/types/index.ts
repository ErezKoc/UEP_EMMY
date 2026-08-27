// TypeScript mirrors of the backend Pydantic schemas (backend/app/schemas).
// Field names are snake_case to match the JSON payloads exactly.

export type UserRole = "owner" | "veterinarian" | "admin";

export type VerificationStatus = "unverified" | "pending" | "verified" | "rejected";

export type AgeCategory = "baby" | "young" | "adult" | "senior" | "unknown";

/** Moderation state of an account, set by an admin when deciding a report. */
export type AccountStatus = "active" | "suspended" | "banned";

export interface User {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  bio: string | null;
  avatar_url: string | null;
  clinic_name: string | null;
  license_number: string | null;
  verification_status: VerificationStatus;
  /** True only for veterinarians an admin approved. Drives the trusted badge. */
  is_verified_vet: boolean;
  account_status: AccountStatus;
  created_at: string;
}

/**
 * The signed-in user's own account. The suspension deadline and the moderator's
 * note are only ever returned to the account they concern, never on a public
 * author profile — so they live here rather than on `User`.
 */
export interface CurrentUser extends User {
  /**
   * The practice details, on the account rather than only on the public
   * directory entry — this is what the profile form edits. Null for owners,
   * and null for a veterinarian who has not filled them in.
   */
  clinic_phone: string | null;
  clinic_emergency_phone: string | null;
  clinic_email: string | null;
  clinic_website: string | null;
  clinic_address_line: string | null;
  clinic_city: string | null;
  clinic_postcode: string | null;
  clinic_country: string | null;
  clinic_hours: string | null;
  /** The directory fields a practice edits on its own profile. */
  clinic_hours_grid: Record<string, string[][]> | null;
  clinic_timezone: string | null;
  clinic_latitude: number | null;
  clinic_longitude: number | null;
  specialties: string[];
  consultation_fee_min: number | null;
  consultation_fee_max: number | null;
  fee_currency: string | null;
  accepts_appointments: boolean;
  notify_in_app: boolean;
  notify_email: boolean;
  /** Days ahead a reminder is announced. 0 means on the day itself. */
  notify_lead_days: number;
  /** "09:00:00" — the hour alerts go out, on this person's own clock. */
  notify_time: string;
  /** IANA zone the hour above is read in. Null means UTC, and the settings
   *  page says so rather than pretending a preference was honoured. */
  notify_timezone: string | null;
  suspended_until: string | null;
  moderation_note: string | null;
  /** False while suspended or banned: posting, commenting and reporting are off. */
  can_participate: boolean;
}

export interface SignupPayload {
  email: string;
  password: string;
  display_name: string;
  // Admin accounts are never self-registered (backend rejects the value).
  role: Exclude<UserRole, "admin">;
  clinic_name?: string;
  license_number?: string;
}

export interface VetVerification {
  id: string;
  status: VerificationStatus;
  document_url: string;
  license_number: string | null;
  review_note: string | null;
  created_at: string;
  reviewed_at: string | null;
  /** Which administrator decided this — decisions are attributable. */
  reviewed_by_name: string | null;
  user: Veterinarian;
}

export interface ProfileUpdatePayload {
  display_name?: string;
  bio?: string;
  email?: string;
  clinic_name?: string;
  license_number?: string;
  /*
   * Listed even though the profile form builds this object with a spread,
   * which skips TypeScript's excess-property check: without these here a
   * misspelt field name would compile, send, and be silently dropped by the
   * backend, and the veterinarian would just see their details not save.
   */
  clinic_phone?: string;
  clinic_emergency_phone?: string;
  clinic_email?: string;
  clinic_website?: string;
  clinic_address_line?: string;
  clinic_city?: string;
  clinic_postcode?: string;
  clinic_country?: string;
  clinic_hours?: string;
  clinic_hours_grid?: Record<string, string[][]> | null;
  clinic_timezone?: string | null;
  clinic_latitude?: number | null;
  clinic_longitude?: number | null;
  specialties?: string[] | null;
  consultation_fee_min?: number | null;
  consultation_fee_max?: number | null;
  fee_currency?: string | null;
  accepts_appointments?: boolean;
  notify_in_app?: boolean;
  notify_email?: boolean;
  notify_lead_days?: number;
  notify_time?: string;
  notify_timezone?: string | null;
}

export interface AuthResponse {
  token: string;
  user: CurrentUser;
}

// ------------------------------------------------------- community reporting

/** Checklist a reporter ticks; at least one is required per report. */
export type ReportReason =
  | "offensive_language"
  | "harassment"
  | "spam"
  | "impersonating_vet"
  | "harmful_advice"
  | "animal_welfare"
  | "graphic_content"
  | "other";

export type ReportTargetType = "post" | "comment" | "user";

export type ReportStatus = "pending" | "dismissed" | "actioned";

export type ModerationAction = "suspend" | "ban" | "reinstate";

/** Compact identity used in moderation views. */
export interface UserSummary {
  id: string;
  display_name: string;
  role: UserRole;
  avatar_url: string | null;
  is_verified_vet: boolean;
}

/** A reported member, with the account state an admin needs to decide. */
export interface ReportedUser extends UserSummary {
  email: string;
  clinic_name: string | null;
  license_number: string | null;
  verification_status: VerificationStatus;
  account_status: AccountStatus;
  suspended_until: string | null;
  created_at: string;
}

export interface UserReport {
  id: string;
  target_type: ReportTargetType;
  post_id: string | null;
  comment_id: string | null;
  /** The reported text as it read when reported, kept if the author edits it. */
  content_snapshot: string | null;
  reasons: ReportReason[];
  details: string | null;
  status: ReportStatus;
  action_taken: ModerationAction | null;
  review_note: string | null;
  created_at: string;
  reviewed_at: string | null;
  reviewed_by_name: string | null;
  reporter: UserSummary;
  reported_user: ReportedUser;
}

export interface ReportPayload {
  target_type: ReportTargetType;
  target_id: string;
  reasons: ReportReason[];
  details?: string | null;
}

export interface Animal {
  id: string;
  name: string;
  species: string;
  breed: string | null;
  birth_date: string | null;
  photo_url: string | null;
  photo_position_x: number;
  photo_position_y: number;
  photo_zoom: number;
  age_category: AgeCategory;
  owner_id: string;
  created_at: string;
}

export interface AnimalPayload {
  name: string;
  species: string;
  breed?: string | null;
  birth_date?: string | null;
  age_category?: AgeCategory | null;
  photo_position_x?: number;
  photo_position_y?: number;
  photo_zoom?: number;
}

export type ReminderType = "vaccine" | "checkup" | "other";
export type ReminderRecurrence = "none" | "daily" | "weekly" | "monthly" | "yearly";

export interface Reminder {
  id: string;
  title: string;
  reminder_type: ReminderType;
  due_date: string;
  recurrence: ReminderRecurrence;
  /** How many of `recurrence` between occurrences — 3 + monthly is quarterly. */
  recurrence_interval: number;
  repeat_until: string | null;
  /**
   * Computed by the server, not the browser. The calendar could work it out
   * itself, but a notification email cannot, and the two must never disagree
   * about when something is due — so the server is the single answer.
   */
  next_occurrence: string | null;
  /**
   * The scheduled date behind `next_occurrence` — the two differ only when it
   * has been snoozed. Every done/snooze call is keyed on THIS one, because the
   * recurrence rule keeps producing it and a snooze must stay recognisably the
   * same instance.
   */
  next_scheduled_date: string | null;
  next_is_snoozed: boolean;
  /** How many days ahead this one is announced. Null means the account default. */
  notify_lead_days: number | null;
  /** How many instances have been ticked off. */
  completed_count: number;
  /** The most recent tick, by its scheduled date. What "undo" acts on. */
  last_completed_date: string | null;
  /** Nothing left to do: a done one-off, or a series past its end date. */
  is_finished: boolean;
  /** The rule in words: "every 3 months, until 01 Dec 2026". */
  recurrence_description: string;
  notes: string | null;
  animal_id: string;
  owner_id: string;
  created_at: string;
  animal: Animal;
}

/**
 * One dated instance, as the server resolved it.
 *
 * The calendar draws these rather than working the dates out itself. It used
 * to mirror the recurrence rules in the browser; that was affordable while the
 * answer was pure arithmetic, and stopped being so once an instance could be
 * ticked off or pushed back.
 */
export interface ReminderOccurrence {
  reminder_id: string;
  /** What the rule produced. The identity the done/snooze endpoints take. */
  scheduled_date: string;
  /** Where it actually lands — the same, unless it was snoozed. */
  date: string;
  done: boolean;
  snoozed: boolean;
}

/** Reminders that say exactly the same thing. `keep_id` is the oldest. */
export interface DuplicateGroup {
  title: string;
  reminder_type: ReminderType;
  due_date: string;
  animal_id: string;
  animal_name: string;
  keep_id: string;
  duplicate_ids: string[];
  reminders: Reminder[];
}

export interface ReminderPayload {
  title: string;
  reminder_type: ReminderType;
  due_date: string;
  recurrence: ReminderRecurrence;
  recurrence_interval?: number;
  repeat_until?: string | null;
  notify_lead_days?: number | null;
  notes?: string | null;
  animal_id: string;
}

export type NotificationKind =
  | "reminder_due"
  | "appointment_requested"
  | "appointment_confirmed"
  | "appointment_declined"
  | "appointment_cancelled"
  | "appointment_reschedule_proposed"
  | "appointment_rescheduled"
  | "appointment_reschedule_declined"
  | "appointment_message";

/**
 * One thing the platform wants to tell you.
 *
 * One row per thing-worth-saying, whatever channels carried it: an in-app
 * alert and an email about the same appointment are the same notification, so
 * "mark as read" means one thing rather than depending on where you read it.
 */
export interface AppNotification {
  id: string;
  kind: NotificationKind;
  title: string;
  body: string;
  link: string | null;
  read_at: string | null;
  /** Whether the email half went out — so "I never got the email" has an answer. */
  emailed: boolean;
  created_at: string;
}

export interface BreedCandidate {
  breed: string;
  confidence: number;
}

export interface AgeEstimate {
  category: AgeCategory;
  min_years: number;
  max_years: number;
  confidence: number;
}

export interface AnalysisResult {
  model_version: string;
  species: string;
  species_confidence: number;
  breed_candidates: BreedCandidate[];
  age_estimate: AgeEstimate;
  characteristics: string[];
}

// ------------------------------------------------------------------ triage
// Mirrors backend/app/schemas/triage.py. Every question exists because a cited
// source uses it to decide urgency — see backend/app/services/triage/rules.py.

export type Concern =
  | "breed_only"
  | "skin_or_coat"
  | "eyes"
  | "ears"
  | "mobility"
  | "digestion"
  | "breathing"
  | "urination"
  | "behaviour"
  | "other";

export type BodyArea =
  | "head_or_face"
  | "ear"
  | "eye"
  | "mouth"
  | "chest"
  | "belly"
  | "back"
  | "legs_or_paws"
  | "tail"
  | "all_over";

export type Duration = "today" | "days_2_7" | "weeks_1_4" | "over_month";

export type Trend = "worsening" | "unchanged" | "improving";

export type RedFlag =
  | "trouble_breathing"
  | "rapid_breathing_at_rest"
  | "severe_pain"
  | "uncontrolled_bleeding"
  | "suspected_poisoning"
  | "eye_injury"
  | "eye_pain_or_closed"
  | "eye_cloudy_or_blue"
  | "unequal_pupils_or_vision_change"
  | "eye_bulging_or_severe_swelling"
  | "eye_discharge_yellow_green_or_bloody"
  | "eye_chemical_exposure"
  | "eye_redness"
  | "eye_watering"
  | "eye_irritation"
  | "ear_head_shaking_or_scratching"
  | "ear_odor"
  | "ear_discharge"
  | "ear_redness"
  | "ear_pain"
  | "ear_flap_swelling"
  | "ear_head_tilt"
  | "ear_balance_problems"
  | "ear_rapid_eye_movements"
  | "ear_sudden_hearing_loss"
  | "ear_facial_droop"
  | "ear_bloody_or_pus_discharge"
  | "ear_self_injury"
  | "ear_foreign_body"
  // Merck integumentary system — what is actually on the skin. "Skin or coat"
  // on its own is the owner's category for the problem, not a description of
  // it, and the rule table reads these instead.
  | "skin_itching"
  | "skin_redness"
  | "skin_hair_loss"
  | "skin_rash_or_bumps"
  | "skin_scabs_or_flaking"
  | "skin_swelling"
  | "skin_lump"
  | "skin_nail_or_pad_change"
  | "skin_open_wound"
  | "skin_discharge_or_pus"
  | "skin_odor"
  | "skin_contagion"
  | "limb_cannot_move"
  | "seizure"
  | "collapse_or_unresponsive"
  | "pale_gums"
  | "major_trauma"
  | "choking"
  | "insect_sting_reaction"
  | "overheating"
  | "unable_to_urinate"
  | "bloated_abdomen_with_retching"
  | "blood_in_vomit_or_stool"
  | "black_tarry_stool"
  | "vomiting"
  | "vomiting_many_times"
  | "diarrhoea"
  | "extreme_lethargy"
  | "not_eating"
  | "drinking_much_more";

export type TimeSinceEating = "under_12h" | "h12_to_24h" | "over_24h";

/**
 * `unassessed` is not a fourth point on the urgency scale — it is the engine
 * refusing to place a case on the scale at all, because no published source it
 * holds covers what the owner described (an unsupported species, or a symptom
 * combination outside the rules). It must never be styled like `green`: absence
 * of evidence is not evidence that monitoring at home is safe.
 *
 * Stored verdicts predate this value, so anything reading historical data
 * should treat an unrecognised level defensively rather than assuming three.
 */
export type TriageLevel = "red" | "amber" | "green" | "unassessed";

/** How much a skin problem is bothering the animal. Our bands, not Merck's. */
export type ItchLevel = "none" | "occasional" | "frequent" | "cannot_settle";

/** How widely a skin problem is distributed. Recorded for the vet; scores nothing. */
export type SkinSpread = "one_area" | "several_areas" | "widespread";

/**
 * "not_assessed" is deliberately not "low". Low means we looked and the sources
 * do not support it; not_assessed means the question was never in scope for the
 * rule that answered. They were rendered in the same word ("None"), which told
 * an owner that evidence had been sought and found missing.
 */
export type ConfidenceLevel = "high" | "moderate" | "low" | "not_assessed";

/**
 * Which question a dimension answers. Three unrelated ones share the panel and
 * they were rated in one shared vocabulary, so "Match to your answers: Strong"
 * read as confidence in the advice when it only meant a rule's conditions were
 * met. Each kind is now worded in its own terms.
 */
export type ConfidenceKind = "match" | "evidence" | "review";

/** One thing we can be more or less sure of, rated on its own. */
export interface ConfidenceDimension {
  name: string;
  level: ConfidenceLevel;
  detail: string;
  /** Absent on checks stored before the kinds existed; treated as evidence. */
  kind?: ConfidenceKind;
}

/*
 * How far the answer can be relied on — deliberately not one number.
 * "Moderate confidence" reads as "moderately sure something is wrong with your
 * pet", which is a claim about the animal rather than about our evidence, and it
 * buries the dimension an owner might actually act on: a case can match our
 * rules perfectly and still rest on no urgency evidence at all.
 */
export interface ConfidenceReport {
  dimensions: ConfidenceDimension[];
  based_on: string[];
  /** Questions left unanswered whose answers would have changed the level. */
  would_change_the_answer: string[];
}

/** One "get help now" line, with the page that states it. */
export interface UrgentSign {
  text: string;
  sources: Array<{ name: string; url: string }>;
}

export interface SymptomIntake {
  concern: Concern;
  body_area?: BodyArea | null;
  duration?: Duration | null;
  trend?: Trend | null;
  red_flags: RedFlag[];
  time_since_eating?: TimeSinceEating | null;
  itch_level?: ItchLevel | null;
  skin_spread?: SkinSpread | null;
  has_chronic_illness?: boolean | null;
  weight_bearing?: boolean | null;
  /**
   * Whether the owner actually answered the emergency screen. Display-only:
   * it decides whether the result may say they selected none of the emergency
   * signs, and never affects the level. Absent on checks stored before it.
   */
  emergency_screen_answered?: boolean | null;
  /** Filled from the linked pet by the backend for historical records. */
  species?: string | null;
  age_category?: AgeCategory | null;
}

export interface FiredRule {
  rule_id: string;
  message: string;
  weight: number;
  sources: string[];
  source_links: Array<{ name: string; url: string }>;
}

export interface TriageAssessment {
  level: TriageLevel;
  headline: string;
  /**
   * Whether what the owner described tripped an emergency rule, said before
   * anything else. Null on a red result and on checks stored before it existed.
   */
  screening_note?: string | null;
  score: number;
  threshold: number;
  fired_rules: FiredRule[];
  advice: string;
  urgent_care_signs: UrgentSign[];
  /** Set when the urgent-care list is the general one, not the fired rules' own. */
  urgent_care_note?: string | null;
  care_instructions: string[];
  /** Explanatory notes about the appointment — not instructions to follow. */
  what_to_expect?: string[];
  disclaimer: string;
  rules_fully_verified: boolean;
  /** Absent on checks stored before confidence reporting existed. */
  confidence?: ConfidenceReport | null;
}

/** A symptom check saved to the owner's history (no photo involved). */
export interface SymptomCheck {
  id: string;
  created_at: string;
  species: string | null;
  age_category: AgeCategory | null;
  intake: SymptomIntake | null;
  triage: TriageAssessment | null;
  animal: Animal | null;
}

/**
 * One thing an analysis and the linked pet's profile do not agree about.
 *
 * A DISAGREEMENT, not an error, and the wording everywhere follows from that.
 * Neither side is presumed right: the profile is typed by a person who may
 * have guessed a rescue's breed, and the model's real-world accuracy has never
 * been measured. So the panel names what each side claims and offers both ways
 * out — correct the analysis, or fix the profile.
 *
 * Computed by the server on every read, never stored, so it disappears the
 * moment the owner settles it either way.
 */
export interface ProfileConflict {
  field: "species" | "breed" | "age";
  /**
   * "high" changes what other features do, or is too large to be a boundary
   * case. "low" is worth a look, not a worry.
   */
  severity: "high" | "low";
  profile_says: string;
  analysis_says: string;
  message: string;
  /** True when the analysis's side is the owner's own correction. */
  from_correction: boolean;
}

export interface AnalysisResponse {
  analysis_id: string;
  animal_id: string | null;
  image_url: string;
  created_at: string;
  result: AnalysisResult;
  /** Present only when the owner answered the symptom questions. */
  triage: TriageAssessment | null;
  /** Empty when no pet is linked — there is nothing to contradict. */
  conflicts: ProfileConflict[];
}

/**
 * What the owner says the animal actually is, when the model got it wrong.
 *
 * Stored beside the model's output, never over it: the analysis record exists
 * to show what was predicted, and a prediction edited to be correct records
 * nothing. Every field is independently settable and independently clearable.
 */
export interface AnalysisCorrection {
  species?: string | null;
  breed?: string | null;
  age_category?: AgeCategory | null;
  note?: string | null;
}

export interface AnalysisUpdatePayload {
  correction?: AnalysisCorrection | null;
  /** Omit to leave the link alone; `null` to unlink. The two differ. */
  animal_id?: string | null;
}

export interface AnalysisHistoryItem {
  id: string;
  image_url: string;
  created_at: string;
  result: AnalysisResult;
  triage: TriageAssessment | null;
  animal: Animal | null;
  /**
   * The owner's correction, once they have made one. On the list type as well
   * as the detail type, so the history can mark a row as corrected without
   * fetching each record to find out.
   */
  correction: AnalysisCorrection | null;
  corrected_at: string | null;
  /** Recomputed on every read against the profile as it is right now. */
  conflicts: ProfileConflict[];
}

export interface AnalysisDetail extends AnalysisHistoryItem {
  intake: SymptomIntake | null;
}

/**
 * Route state passed to /community/new by the "Share to community" action
 * (Member 4 → Member 5 contract): read it via useLocation().state?.prefill
 * and pre-fill the new-post form.
 */
/**
 * A community post opened with its body already written.
 *
 * `analysis_id` and `image_url` are nullable because not every prefill comes
 * from a photo analysis: a symptom check that the triage engine could not
 * assess produces one too, and it has answers to carry rather than an image.
 */
/**
 * One thing worth doing, already ranked by the server.
 *
 * `severity` is about consequence, not loudness. "urgent" means an animal may
 * need seeing or an appointment may be lost; "soon" has a deadline; "info" is
 * worth knowing. The ranking is done once on the server so this page and the
 * calendar can never disagree about what matters most.
 */
export interface DashboardTask {
  kind: string;
  severity: "urgent" | "soon" | "info";
  title: string;
  detail: string;
  link: string;
  pet_name: string | null;
  due: string | null;
}

export interface AppointmentBrief {
  id: string;
  scheduled_date: string | null;
  scheduled_time: string | null;
  practice: string;
  pet_name: string | null;
  /** A suggested move is still waiting on somebody, so the date may change. */
  move_pending: boolean;
}

export interface PetSummary {
  animal: Animal;
  overdue_reminders: number;
  next_reminder_title: string | null;
  next_reminder_date: string | null;
  next_appointment: AppointmentBrief | null;
  /** Kept as a plain string: a stored verdict this build does not recognise
   *  must render as unknown rather than break the page. */
  last_check_level: string | null;
  last_check_headline: string | null;
  last_check_at: string | null;
  last_analysis_at: string | null;
  profile_conflicts: number;
  tasks: DashboardTask[];
}

export interface DashboardData {
  pets: PetSummary[];
  tasks: DashboardTask[];
  next_appointment: AppointmentBrief | null;
  urgent_count: number;
}

export interface PostPrefill {
  analysis_id: string | null;
  image_url: string | null;
  title: string;
  content: string;
}

export interface Post {
  id: string;
  title: string;
  content: string;
  analysis_id: string | null;
  image_url: string | null;
  author: User;
  comment_count: number;
  /** Answered by a VERIFIED veterinarian — the list's most useful signal. */
  has_vet_answer: boolean;
  /** Last reply, or when it was asked. Not the same as `created_at`. */
  last_activity_at: string | null;
  created_at: string;
}

/**
 * One opening a practice has published on this platform.
 *
 * Not a window into their diary — this app has no connection to whatever
 * software runs a clinic's calendar. It is the practice declaring here that
 * this time is free, which is real because they said it, and it still produces
 * a request the practice answers rather than a booking.
 */
export interface AvailabilitySlot {
  id: string;
  vet_id: string;
  slot_date: string;
  start_time: string;
  end_time: string;
  capacity: number;
  note: string | null;
  /** Confirmed bookings against it. Sent with capacity so an open surgery can
   *  read as "2 of 6 taken" rather than a bare number. */
  taken: number;
  is_open: boolean;
}

export interface SpecialtyOption {
  value: string;
  label: string;
}

export interface Veterinarian {
  id: string;
  display_name: string;
  role: "veterinarian";
  bio: string | null;
  avatar_url: string | null;
  clinic_name: string | null;
  license_number: string | null;
  /**
   * How to reach the practice. All nullable, because a profile written before
   * these fields existed has none of them and a directory that hides such a
   * vet entirely would be worse than one showing a name with no phone number.
   * Every consumer has to handle the empty case.
   */
  clinic_phone: string | null;
  clinic_emergency_phone: string | null;
  clinic_email: string | null;
  clinic_website: string | null;
  clinic_address_line: string | null;
  clinic_city: string | null;
  clinic_postcode: string | null;
  clinic_country: string | null;
  clinic_hours: string | null;
  /**
   * The same hours as a weekly grid, for filtering. Sits BESIDE the sentence
   * above rather than replacing it: a grid cannot express alternate Saturdays
   * or a seasonal closure, so the practice's own wording stays what a human
   * reads. Null when the practice has not filled it in.
   */
  clinic_hours_grid: Record<string, string[][]> | null;
  clinic_timezone: string | null;
  clinic_latitude: number | null;
  clinic_longitude: number | null;
  specialties: string[];
  /** The same list in words, so no client holds its own copy of the catalogue. */
  specialty_labels: string[];
  consultation_fee_min: number | null;
  consultation_fee_max: number | null;
  fee_currency: string | null;
  /** Whether this practice takes appointment requests through the platform. */
  accepts_appointments: boolean;

  /**
   * Straight-line kilometres from the point you searched from. Null means
   * unknown — one end has no coordinates — and never "far".
   */
  distance_km: number | null;
  /**
   * True, false, or **null for "no hours published"**. The third state is the
   * important one: a clinic nobody entered hours for is not a closed clinic,
   * and treating null as false is how a real practice gets hidden.
   */
  open_now: boolean | null;
  closes_at: string | null;
  opens_at: string | null;
  opens_day: string | null;
  /** The soonest opening the practice has PUBLISHED HERE. Not their diary. */
  next_slot_date: string | null;
  next_slot_time: string | null;
  published_slot_count: number;
  verification_status: VerificationStatus;
  is_verified_vet: boolean;
}

/** One service to call when no practice is open, with the page it came from. */
export interface EmergencyContact {
  name: string;
  /** As published — the form a person reads and dials by hand. */
  phone: string;
  /** The `tel:` target, which is not the same string as `phone`. */
  dial: string;
  when: string;
  caveat: string | null;
  coverage: string;
  source_name: string;
  source_url: string;
  accessed: string;
}

export interface EmergencyContacts {
  /** Shown above the list, always. It says what these services cannot do. */
  note: string;
  contacts: EmergencyContact[];
}

export type AppointmentStatus =
  | "requested"
  | "confirmed"
  /** A move has been suggested; the appointment below it still stands. */
  | "reschedule_proposed"
  | "declined"
  | "cancelled";

/**
 * A request for an appointment, and the practice's answer.
 *
 * Not a booked slot: `preferred_date` is what the owner asked for and
 * `scheduled_date` is what the practice confirmed, and they are kept apart so a
 * moved appointment can never be mistaken for the day that was chosen.
 */
export interface Appointment {
  id: string;
  status: AppointmentStatus;
  reason: string;
  preferred_date: string;
  /** "14:30". Null when the owner had no preference, which is common. */
  preferred_time: string | null;
  /** Free text from before `preferred_time` existed. Read-only now. */
  preferred_time_note: string | null;
  scheduled_date: string | null;
  /** The exact time the practice confirmed. Null only on pre-feature rows. */
  scheduled_time: string | null;
  vet_note: string | null;
  created_at: string;
  responded_at: string | null;
  owner: User;
  vet: Veterinarian;
  animal: Animal | null;
  reminder_id: string | null;
  /** A move somebody has suggested. The appointment has NOT moved yet. */
  proposed_date: string | null;
  proposed_time: string | null;
  proposed_note: string | null;
  /** Only the side that did NOT propose may answer, so the client needs this. */
  proposed_by_id: string | null;
  message_count: number;
  /** Unread by YOU — the total is shared, this is personal. */
  unread_message_count: number;
}

export interface AppointmentMessage {
  id: string;
  body: string;
  sender: User;
  created_at: string;
  read_at: string | null;
}

export interface AppointmentPayload {
  vet_id: string;
  reason: string;
  preferred_date: string;
  preferred_time?: string | null;
  animal_id?: string | null;
  /** A published opening. When set, the server takes the date and time from it. */
  slot_id?: string | null;
}

export interface Comment {
  id: string;
  content: string;
  author: User;
  /** Where the answer came from, when the person answering said. */
  source_url: string | null;
  source_title: string | null;
  /** How many distinct people marked this helpful. */
  helpful_count: number;
  /** Whether YOU already did — the count is public, this is personal. */
  viewer_found_helpful: boolean;
  created_at: string;
}

export interface PostDetail extends Post {
  comments: Comment[];
}

// ------------------------------------------------------------- AI Assistant

export type AssistantActionType =
  | "create_reminder"
  | "delete_reminder"
  | "create_pet"
  | "delete_pet"
  | "update_pet"
  | "navigate"
  | "create_post"
  | "search_vets"
  | "submit_verification"
  | "query_pets"
  | "general_reply";

export interface AssistantAction {
  action_type: AssistantActionType;
  summary: string;
  params: Record<string, any>;
  nav_target: string | null;
  execution_result?: Record<string, any> | null;
}

export interface AssistantProcessResponse {
  transcript: string;
  response_text: string;
  actions: AssistantAction[];
  action: AssistantAction;
  execution_result: Record<string, any> | null;
}


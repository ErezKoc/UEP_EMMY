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
  accepts_appointments: boolean;
  notify_in_app: boolean;
  notify_email: boolean;
  /** Days ahead a reminder is announced. 0 means on the day itself. */
  notify_lead_days: number;
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
  accepts_appointments?: boolean;
  notify_in_app?: boolean;
  notify_email?: boolean;
  notify_lead_days?: number;
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
  /** The rule in words: "every 3 months, until 01 Dec 2026". */
  recurrence_description: string;
  notes: string | null;
  animal_id: string;
  owner_id: string;
  created_at: string;
  animal: Animal;
}

export interface ReminderPayload {
  title: string;
  reminder_type: ReminderType;
  due_date: string;
  recurrence: ReminderRecurrence;
  recurrence_interval?: number;
  repeat_until?: string | null;
  notes?: string | null;
  animal_id: string;
}

export type NotificationKind =
  | "reminder_due"
  | "appointment_requested"
  | "appointment_confirmed"
  | "appointment_declined"
  | "appointment_cancelled";

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

export interface AnalysisResponse {
  analysis_id: string;
  animal_id: string | null;
  image_url: string;
  created_at: string;
  result: AnalysisResult;
  /** Present only when the owner answered the symptom questions. */
  triage: TriageAssessment | null;
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
  /** Whether this practice takes appointment requests through the platform. */
  accepts_appointments: boolean;
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

export type AppointmentStatus = "requested" | "confirmed" | "declined" | "cancelled";

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
  preferred_time_note: string | null;
  scheduled_date: string | null;
  vet_note: string | null;
  created_at: string;
  responded_at: string | null;
  owner: User;
  vet: Veterinarian;
  animal: Animal | null;
  reminder_id: string | null;
}

export interface AppointmentPayload {
  vet_id: string;
  reason: string;
  preferred_date: string;
  preferred_time_note?: string | null;
  animal_id?: string | null;
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
}

export interface AssistantProcessResponse {
  transcript: string;
  response_text: string;
  action: AssistantAction;
  execution_result: Record<string, any> | null;
}


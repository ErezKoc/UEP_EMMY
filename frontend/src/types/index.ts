// TypeScript mirrors of the backend Pydantic schemas (backend/app/schemas).
// Field names are snake_case to match the JSON payloads exactly.

export type UserRole = "owner" | "veterinarian" | "admin";

export type VerificationStatus = "unverified" | "pending" | "verified" | "rejected";

export type AgeCategory = "baby" | "young" | "adult" | "senior" | "unknown";

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
  created_at: string;
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
}

export interface AuthResponse {
  token: string;
  user: User;
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
  photo_position_x?: number;
  photo_position_y?: number;
  photo_zoom?: number;
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

export interface SymptomIntake {
  concern: Concern;
  body_area?: BodyArea | null;
  duration?: Duration | null;
  trend?: Trend | null;
  red_flags: RedFlag[];
  time_since_eating?: TimeSinceEating | null;
  has_chronic_illness?: boolean | null;
  weight_bearing?: boolean | null;
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
  score: number;
  threshold: number;
  fired_rules: FiredRule[];
  advice: string;
  urgent_care_signs: string[];
  care_instructions: string[];
  disclaimer: string;
  rules_fully_verified: boolean;
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

export interface AnalysisHistoryItem {
  id: string;
  image_url: string;
  created_at: string;
  result: AnalysisResult;
  triage: TriageAssessment | null;
  animal: Animal | null;
}

export interface AnalysisDetail extends AnalysisHistoryItem {
  intake: SymptomIntake | null;
}

/**
 * Route state passed to /community/new by the "Share to community" action
 * (Member 4 → Member 5 contract): read it via useLocation().state?.prefill
 * and pre-fill the new-post form.
 */
export interface PostPrefill {
  analysis_id: string;
  image_url: string;
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
  verification_status: VerificationStatus;
  is_verified_vet: boolean;
}

export interface Comment {
  id: string;
  content: string;
  author: User;
  created_at: string;
}

export interface PostDetail extends Post {
  comments: Comment[];
}

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
export type ReminderRecurrence = "none" | "monthly" | "yearly";

export interface Reminder {
  id: string;
  title: string;
  reminder_type: ReminderType;
  due_date: string;
  recurrence: ReminderRecurrence;
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
  notes?: string | null;
  animal_id: string;
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

export interface AnalysisResponse {
  analysis_id: string;
  animal_id: string | null;
  image_url: string;
  created_at: string;
  result: AnalysisResult;
}

export interface AnalysisHistoryItem {
  id: string;
  image_url: string;
  created_at: string;
  result: AnalysisResult;
  animal: Animal | null;
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

// ------------------------------------------------------------- AI Assistant

export type AssistantActionType =
  | "create_reminder"
  | "create_pet"
  | "navigate"
  | "create_post"
  | "search_vets"
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


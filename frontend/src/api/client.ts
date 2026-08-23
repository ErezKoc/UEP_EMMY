import type {
  AnalysisDetail,
  AnalysisHistoryItem,
  AnalysisResponse,
  Animal,
  AnimalPayload,
  AssistantProcessResponse,
  AuthResponse,
  CurrentUser,
  Post,
  PostDetail,
  ProfileUpdatePayload,
  Reminder,
  ReminderPayload,
  ReportPayload,
  ReportStatus,
  SignupPayload,
  SymptomCheck,
  SymptomIntake,
  TriageAssessment,
  UserReport,
  UserRole,
  VerificationStatus,
  Veterinarian,
  VetVerification,
} from "../types";

// In development the Vite dev server proxies /v1 and /media to FastAPI
// (see vite.config.ts), so the base URL can stay origin-relative.
const API_BASE = "/v1";

// ---------------------------------------------------------------------------
// Session token (persisted so refreshing the page keeps the user signed in).
// SessionContext owns the lifecycle; other code only reads via authHeaders().

const TOKEN_STORAGE_KEY = "uep-emmy.token";

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string | null): void {
  if (token === null) localStorage.removeItem(TOKEN_STORAGE_KEY);
  else localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

function authHeaders(): Record<string, string> {
  const token = getStoredToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ---------------------------------------------------------------------------

// A request that never settles leaves the UI spinning with nothing to act on,
// which is worse than a visible failure. Every call gets an upper bound.
const REQUEST_TIMEOUT_MS = 20_000;

// Uploads carry a file over the wire and then wait on model inference, so they
// need a far bigger budget than a JSON read. Twenty seconds used to abort real
// in-flight analyses and report them as "the backend is down".
const UPLOAD_TIMEOUT_MS = 120_000;

export async function apiFetch(
  path: string,
  init: RequestInit = {},
  timeoutMs: number = REQUEST_TIMEOUT_MS,
): Promise<Response> {
  try {
    return await fetch(path, { ...init, signal: AbortSignal.timeout(timeoutMs) });
  } catch (error) {
    if (error instanceof DOMException && error.name === "TimeoutError") {
      // Deliberately does not blame the server. A timeout here means no
      // response arrived within the window, which covers a slow server AND a
      // request that never reached one — a connection dropped underneath us,
      // for instance. Asserting the first sent two people reading backend
      // logs for a request the backend had never been sent.
      throw new ApiError(
        0,
        `No response after ${Math.round(timeoutMs / 1000)}s. The server may be busy or still ` +
          "starting up, or the connection may have dropped. Please try again.",
      );
    }
    // fetch() rejects with a plain TypeError when it cannot reach the server
    // at all. That is the genuine "backend is down" case.
    if (error instanceof TypeError) {
      throw new ApiError(0, "Could not reach the server. Is the backend running?");
    }
    throw error;
  }
}

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
  }
}

/*
 * A 5xx is our fault, not the caller's, and nothing it carries is actionable by
 * an owner: FastAPI's default body is the bare string "Internal Server Error",
 * and a proxy in front of a stopped backend sends no JSON at all, which used to
 * surface as "Request failed with status 500". Both become a retry prompt, so
 * the server detail is deliberately dropped above 499 rather than shown.
 */
function serverErrorMessage(status: number): string {
  if (status === 503 || status === 502 || status === 504) {
    return "The service is temporarily unavailable. Please try again in a moment.";
  }
  return "Something went wrong on our side. Please try again in a moment.";
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    if (response.status >= 500) {
      throw new ApiError(response.status, serverErrorMessage(response.status));
    }
    let detail = "Something went wrong with that request. Please try again.";
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
      // Pydantic validation errors arrive as a list; surface the first message.
      else if (Array.isArray(body.detail) && body.detail.length > 0) {
        const first = body.detail[0] as { msg?: unknown };
        if (typeof first.msg === "string") detail = first.msg;
      }
    } catch {
      // Non-JSON error body; keep the generic message.
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function requestJson<T>(path: string, method: string, body?: unknown): Promise<T> {
  return apiFetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then((response) => parseResponse<T>(response));
}

// --------------------------------------------------------------------- auth

export function signup(payload: SignupPayload): Promise<AuthResponse> {
  return requestJson<AuthResponse>("/auth/signup", "POST", payload);
}

export function login(email: string, password: string): Promise<AuthResponse> {
  return requestJson<AuthResponse>("/auth/login", "POST", { email, password });
}

/** Restore the session for the stored token (401 → token invalid/expired). */
export async function fetchCurrentUser(): Promise<CurrentUser> {
  const response = await apiFetch(`${API_BASE}/auth/me`, { headers: authHeaders() });
  return parseResponse<CurrentUser>(response);
}

export function updateProfile(payload: ProfileUpdatePayload): Promise<CurrentUser> {
  return requestJson<CurrentUser>("/users/me", "PATCH", payload);
}

export function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  return requestJson<void>("/users/me/password", "POST", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export async function uploadAvatar(file: File): Promise<CurrentUser> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiFetch(
    `${API_BASE}/users/me/avatar`,
    { method: "POST", headers: authHeaders(), body: formData },
    UPLOAD_TIMEOUT_MS,
  );
  return parseResponse<CurrentUser>(response);
}

// --------------------------------------------------------------------- pets

export async function getAnimals(): Promise<Animal[]> {
  const response = await apiFetch(`${API_BASE}/animals`, { headers: authHeaders() });
  return parseResponse<Animal[]>(response);
}

export async function getAnimal(animalId: string): Promise<Animal> {
  const response = await apiFetch(`${API_BASE}/animals/${animalId}`, { headers: authHeaders() });
  return parseResponse<Animal>(response);
}

export function createAnimal(payload: AnimalPayload): Promise<Animal> {
  return requestJson<Animal>("/animals", "POST", payload);
}

export function updateAnimal(animalId: string, payload: Partial<AnimalPayload>): Promise<Animal> {
  return requestJson<Animal>(`/animals/${animalId}`, "PATCH", payload);
}

export function deleteAnimal(animalId: string): Promise<void> {
  return requestJson<void>(`/animals/${animalId}`, "DELETE");
}

// --------------------------------------------------------------- reminders

export async function getReminders(animalId?: string): Promise<Reminder[]> {
  const suffix = animalId ? `?animal_id=${encodeURIComponent(animalId)}` : "";
  const response = await fetch(`${API_BASE}/reminders${suffix}`, { headers: authHeaders() });
  return parseResponse<Reminder[]>(response);
}

export function createReminder(payload: ReminderPayload): Promise<Reminder> {
  return requestJson<Reminder>("/reminders", "POST", payload);
}

export function updateReminder(id: string, payload: Partial<ReminderPayload>): Promise<Reminder> {
  return requestJson<Reminder>(`/reminders/${id}`, "PATCH", payload);
}

export function deleteReminder(id: string): Promise<void> {
  return requestJson<void>(`/reminders/${id}`, "DELETE");
}

export async function uploadAnimalPhoto(animalId: string, file: File): Promise<Animal> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiFetch(
    `${API_BASE}/animals/${animalId}/photo`,
    { method: "POST", headers: authHeaders(), body: formData },
    UPLOAD_TIMEOUT_MS,
  );
  return parseResponse<Animal>(response);
}

// --------------------------------------------------------- notifications

export async function getNotifications(
  unreadOnly = false,
): Promise<import("../types").AppNotification[]> {
  const suffix = unreadOnly ? "?unread_only=true" : "";
  const response = await apiFetch(`${API_BASE}/notifications${suffix}`, {
    headers: authHeaders(),
  });
  return parseResponse<import("../types").AppNotification[]>(response);
}

/** Just the digit for the badge — polled, so it must stay small. */
export async function getUnreadCount(): Promise<number> {
  const response = await apiFetch(`${API_BASE}/notifications/unread-count`, {
    headers: authHeaders(),
  });
  const data = await parseResponse<{ unread: number }>(response);
  return data.unread;
}

export function markNotificationRead(
  id: string,
): Promise<import("../types").AppNotification> {
  return requestJson<import("../types").AppNotification>(`/notifications/${id}/read`, "POST");
}

export function markAllNotificationsRead(): Promise<{ unread: number }> {
  return requestJson<{ unread: number }>("/notifications/read-all", "POST");
}

// ------------------------------------------------------------- analyses

export function updateAnalysis(
  analysisId: string,
  payload: import("../types").AnalysisUpdatePayload,
): Promise<import("../types").AnalysisDetail> {
  return requestJson<import("../types").AnalysisDetail>(
    `/analysis/${analysisId}`,
    "PATCH",
    payload,
  );
}

export function deleteAnalysis(analysisId: string): Promise<void> {
  return requestJson<void>(`/analysis/${analysisId}`, "DELETE");
}

// -------------------------------------------------------------------- posts

export interface PostQuery {
  limit?: number;
  offset?: number;
  q?: string;
  authorRole?: UserRole | "";
}

export async function getPosts(query: PostQuery = {}): Promise<Post[]> {
  const params = new URLSearchParams({
    limit: String(query.limit ?? 20),
    offset: String(query.offset ?? 0),
  });
  if (query.q?.trim()) params.set("q", query.q.trim());
  if (query.authorRole) params.set("author_role", query.authorRole);
  const response = await apiFetch(`${API_BASE}/posts?${params}`);
  return parseResponse<Post[]>(response);
}

export function getPost(postId: string): Promise<PostDetail> {
  return requestJson<PostDetail>(`/posts/${postId}`, "GET");
}

export function createPost(payload: {
  title: string;
  content: string;
  analysis_id?: string | null;
}): Promise<PostDetail> {
  return requestJson<PostDetail>("/posts", "POST", payload);
}

export function createComment(postId: string, content: string) {
  return requestJson<import("../types").Comment>(`/posts/${postId}/comments`, "POST", { content });
}

export async function getVeterinarians(
  q = "",
  verifiedOnly = false,
  acceptingOnly = false,
): Promise<Veterinarian[]> {
  const params = new URLSearchParams();
  if (q.trim()) params.set("q", q.trim());
  if (verifiedOnly) params.set("verified_only", "true");
  if (acceptingOnly) params.set("accepting_only", "true");
  const suffix = params.size > 0 ? `?${params}` : "";
  const response = await apiFetch(`${API_BASE}/vets${suffix}`);
  return parseResponse<Veterinarian[]>(response);
}

/** Unauthenticated on purpose: an emergency number is no use behind a login. */
export async function getEmergencyContacts(): Promise<
  import("../types").EmergencyContacts
> {
  const response = await apiFetch(`${API_BASE}/vets/emergency-contacts`);
  return parseResponse<import("../types").EmergencyContacts>(response);
}

// ----------------------------------------------------------- appointments

export async function getAppointments(openOnly = false): Promise<
  import("../types").Appointment[]
> {
  const suffix = openOnly ? "?open_only=true" : "";
  const response = await apiFetch(`${API_BASE}/appointments${suffix}`, {
    headers: authHeaders(),
  });
  return parseResponse<import("../types").Appointment[]>(response);
}

export function requestAppointment(
  payload: import("../types").AppointmentPayload,
): Promise<import("../types").Appointment> {
  return requestJson<import("../types").Appointment>("/appointments", "POST", payload);
}

export function respondToAppointment(
  id: string,
  decision: { confirm: boolean; scheduled_date?: string | null; vet_note?: string | null },
): Promise<import("../types").Appointment> {
  return requestJson<import("../types").Appointment>(
    `/appointments/${id}/respond`,
    "POST",
    decision,
  );
}

export function cancelAppointment(id: string): Promise<import("../types").Appointment> {
  return requestJson<import("../types").Appointment>(`/appointments/${id}/cancel`, "POST");
}

// ------------------------------------------------- veterinarian verification

/** Submit (or resubmit) licence proof for admin review. */
export async function submitVerification(file: File): Promise<VetVerification> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await apiFetch(
    `${API_BASE}/verification`,
    { method: "POST", headers: authHeaders(), body: formData },
    UPLOAD_TIMEOUT_MS,
  );
  return parseResponse<VetVerification>(response);
}

/** The caller's own submissions, newest first. */
export async function getMyVerifications(): Promise<VetVerification[]> {
  const response = await apiFetch(`${API_BASE}/verification/me`, { headers: authHeaders() });
  return parseResponse<VetVerification[]>(response);
}

/** Admin review queue, oldest first; pass a status to filter. */
export async function getVerifications(status?: VerificationStatus): Promise<VetVerification[]> {
  const suffix = status ? `?status=${status}` : "";
  const response = await apiFetch(`${API_BASE}/verification${suffix}`, { headers: authHeaders() });
  return parseResponse<VetVerification[]>(response);
}

/** Admin decision: approve or reject a pending submission. */
export function decideVerification(
  verificationId: string,
  status: Extract<VerificationStatus, "verified" | "rejected">,
  reviewNote?: string,
): Promise<VetVerification> {
  return requestJson<VetVerification>(`/verification/${verificationId}`, "PATCH", {
    status,
    review_note: reviewNote?.trim() || null,
  });
}

// ------------------------------------------------- reporting & moderation

/** Report a post, comment, or profile for administrator review. */
export function createReport(payload: ReportPayload): Promise<UserReport> {
  return requestJson<UserReport>("/reports", "POST", payload);
}

/** Reports the signed-in user has filed, newest first. */
export async function getMyReports(): Promise<UserReport[]> {
  const response = await fetch(`${API_BASE}/reports/me`, { headers: authHeaders() });
  return parseResponse<UserReport[]>(response);
}

/** Admin moderation queue, oldest first; pass a status to filter. */
export async function getReports(status?: ReportStatus): Promise<UserReport[]> {
  const suffix = status ? `?status=${status}` : "";
  const response = await fetch(`${API_BASE}/reports${suffix}`, { headers: authHeaders() });
  return parseResponse<UserReport[]>(response);
}

export interface ReportDecisionPayload {
  /** "Reviewed, nothing wrong here" — mutually exclusive with `action`. */
  dismiss?: boolean;
  action?: import("../types").ModerationAction;
  /** Required for `suspend`: how long the restriction lasts. */
  suspend_days?: number;
  /** Required for every action; optional when dismissing. */
  review_note?: string;
}

/** Admin decision: dismiss the report, or suspend/ban/reinstate the account. */
export function decideReport(
  reportId: string,
  payload: ReportDecisionPayload,
): Promise<UserReport> {
  return requestJson<UserReport>(`/reports/${reportId}`, "PATCH", {
    dismiss: payload.dismiss ?? false,
    action: payload.action ?? null,
    suspend_days: payload.suspend_days ?? null,
    review_note: payload.review_note?.trim() || null,
  });
}

// ----------------------------------------------------------------- analysis

export async function uploadForAnalysis(
  file: File,
  animalId?: string | null,
  intake?: SymptomIntake | null,
): Promise<AnalysisResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (animalId) formData.append("animal_id", animalId);
  // Multipart request, so the answers travel as a JSON string.
  if (intake) formData.append("intake", JSON.stringify(intake));

  const response = await apiFetch(
    `${API_BASE}/analysis/upload`,
    { method: "POST", headers: authHeaders(), body: formData },
    UPLOAD_TIMEOUT_MS,
  );
  return parseResponse<AnalysisResponse>(response);
}

// ---------------------------------------------------------- symptom checks

/** Assess symptoms without uploading a photo or storing anything. */
export function assessSymptoms(intake: SymptomIntake): Promise<TriageAssessment> {
  return requestJson<TriageAssessment>("/triage", "POST", intake);
}

/** Assess symptoms and save the result to the signed-in owner's history. */
export function createSymptomCheck(
  intake: SymptomIntake,
  animalId?: string | null,
): Promise<SymptomCheck> {
  return requestJson<SymptomCheck>("/symptom-checks", "POST", {
    ...intake,
    animal_id: animalId || null,
  });
}

/** The signed-in user's saved checks, newest first, optionally per pet. */
export async function getSymptomChecks(animalId?: string | null): Promise<SymptomCheck[]> {
  const query = animalId ? `?animal_id=${animalId}` : "";
  const response = await apiFetch(`${API_BASE}/symptom-checks${query}`, { headers: authHeaders() });
  return parseResponse<SymptomCheck[]>(response);
}

/** One saved check owned by the signed-in user. */
export async function getSymptomCheck(checkId: string): Promise<SymptomCheck> {
  const response = await apiFetch(`${API_BASE}/symptom-checks/${checkId}`, {
    headers: authHeaders(),
  });
  return parseResponse<SymptomCheck>(response);
}

export function deleteSymptomCheck(checkId: string): Promise<void> {
  return requestJson<void>(`/symptom-checks/${checkId}`, "DELETE");
}

/** The signed-in user's past analyses, newest first, optionally per pet. */
export async function getAnalyses(animalId?: string | null): Promise<AnalysisHistoryItem[]> {
  const query = animalId ? `?animal_id=${animalId}` : "";
  const response = await apiFetch(`${API_BASE}/analysis${query}`, { headers: authHeaders() });
  return parseResponse<AnalysisHistoryItem[]>(response);
}

/** One complete analysis owned by the signed-in user. */
export async function getAnalysis(analysisId: string): Promise<AnalysisDetail> {
  const response = await apiFetch(`${API_BASE}/analysis/${analysisId}`, { headers: authHeaders() });
  return parseResponse<AnalysisDetail>(response);
}

// ------------------------------------------------------------- AI Assistant

export async function processAssistantCommand(
  audioBlob?: Blob | null,
  text?: string | null,
): Promise<AssistantProcessResponse> {
  const formData = new FormData();
  if (audioBlob) {
    formData.append("file", audioBlob, "recording.webm");
  }
  if (text?.trim()) {
    formData.append("text", text.trim());
  }

  const response = await fetch(`${API_BASE}/assistant/process`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  return parseResponse<AssistantProcessResponse>(response);
}

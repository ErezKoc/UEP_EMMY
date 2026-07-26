import type {
  AnalysisResponse,
  Animal,
  AnimalPayload,
  AuthResponse,
  Post,
  PostDetail,
  ProfileUpdatePayload,
  SignupPayload,
  User,
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

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
  }
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
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
  return fetch(`${API_BASE}${path}`, {
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
export async function fetchCurrentUser(): Promise<User> {
  const response = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders() });
  return parseResponse<User>(response);
}

export function updateProfile(payload: ProfileUpdatePayload): Promise<User> {
  return requestJson<User>("/users/me", "PATCH", payload);
}

export function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  return requestJson<void>("/users/me/password", "POST", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export async function uploadAvatar(file: File): Promise<User> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/users/me/avatar`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  return parseResponse<User>(response);
}

// --------------------------------------------------------------------- pets

export async function getAnimals(): Promise<Animal[]> {
  const response = await fetch(`${API_BASE}/animals`, { headers: authHeaders() });
  return parseResponse<Animal[]>(response);
}

export async function getAnimal(animalId: string): Promise<Animal> {
  const response = await fetch(`${API_BASE}/animals/${animalId}`, { headers: authHeaders() });
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

export async function uploadAnimalPhoto(animalId: string, file: File): Promise<Animal> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE}/animals/${animalId}/photo`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  return parseResponse<Animal>(response);
}

// -------------------------------------------------------------------- posts

export async function getPosts(limit = 20, offset = 0): Promise<Post[]> {
  const response = await fetch(`${API_BASE}/posts?limit=${limit}&offset=${offset}`);
  return parseResponse<Post[]>(response);
}

export function createPost(title: string, content: string): Promise<PostDetail> {
  return requestJson<PostDetail>("/posts", "POST", { title, content });
}

// ----------------------------------------------------------------- analysis

export async function uploadForAnalysis(file: File): Promise<AnalysisResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/analysis/upload`, {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });
  return parseResponse<AnalysisResponse>(response);
}

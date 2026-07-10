import type { AnalysisResponse, Post, PostDetail } from "../types";

// In development the Vite dev server proxies /v1 and /media to FastAPI
// (see vite.config.ts), so the base URL can stay origin-relative.
const API_BASE = "/v1";

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
    } catch {
      // Non-JSON error body; keep the generic message.
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export async function getPosts(limit = 20, offset = 0): Promise<Post[]> {
  const response = await fetch(`${API_BASE}/posts?limit=${limit}&offset=${offset}`);
  return parseResponse<Post[]>(response);
}

export async function createPost(title: string, content: string): Promise<PostDetail> {
  const response = await fetch(`${API_BASE}/posts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, content }),
  });
  return parseResponse<PostDetail>(response);
}

export async function uploadForAnalysis(file: File): Promise<AnalysisResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/analysis/upload`, {
    method: "POST",
    body: formData,
  });
  return parseResponse<AnalysisResponse>(response);
}

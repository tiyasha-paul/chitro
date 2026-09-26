export interface AuthenticatedUser {
  id: string;
  email: string;
  display_name: string;
}

export interface Workspace {
  id: string;
  name: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  user: AuthenticatedUser;
  workspace: Workspace;
}

export interface PlatformPost {
  id: string;
  campaign_id: string;
  platform: string;
  language: string;
  status: string;
  caption: string | null;
  hook: string | null;
  hashtags: string[] | null;
  cta: string | null;
  media_spec: Record<string, unknown> | null;
  validation_errors: Array<Record<string, unknown>> | null;
  rejection_reason: string | null;
  generation_attempt: number;
  generation_history: GenerationHistoryEntry[] | null;
  created_at: string;
  updated_at: string;
}

export interface GenerationHistoryEntry {
  attempt: number;
  status: string;
  caption: string | null;
  hook: string | null;
  hashtags: string[] | null;
  cta: string | null;
  rejection_reason: string | null;
  timestamp: string | null;
}

export interface Campaign {
  id: string;
  name: string;
  objective: string | null;
  target_audience: string | null;
  brief_context: string | null;
  brief_payload: Record<string, unknown> | null;
  previous_insights: Record<string, unknown> | Array<unknown> | null;
  created_at: string;
  posts: PlatformPost[];
}

export interface CreateCampaignInput {
  name?: string;
  brief: {
    title: string;
    genre: string;
    language: "bn" | "en";
    audience: string;
    objective: string;
    key_themes: string[];
    tone: string;
    cta: string;
    release_date: string;
  };
}

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

const apiBaseUrl = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api").replace(/\/$/, "");

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}${path}`, { ...options, headers });
  } catch {
    throw new ApiError("Chitro is unavailable right now. Please try again shortly.", 0);
  }

  if (!response.ok) {
    let message = "Something went wrong. Please try again.";
    try {
      const payload: unknown = await response.json();
      if (typeof payload === "object" && payload !== null && "detail" in payload) {
        const detail = payload.detail;
        message = typeof detail === "string" ? detail : message;
      }
    } catch {
      // A non-JSON error is intentionally shown as a safe generic message.
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

export const api = {
  register: (input: { email: string; password: string; display_name?: string }) =>
    request<AuthResponse>("/auth/register", { method: "POST", body: JSON.stringify(input) }),
  login: (input: { email: string; password: string }) =>
    request<AuthResponse>("/auth/login", { method: "POST", body: JSON.stringify(input) }),
  me: (token: string) => request<AuthResponse>("/auth/me", {}, token),
  listCampaigns: (token: string) => request<Campaign[]>("/campaigns", {}, token),
  getCampaign: (id: string, token: string) => request<Campaign>(`/campaigns/${id}`, {}, token),
  createCampaign: (input: CreateCampaignInput, token: string) =>
    request<Campaign>("/campaigns", { method: "POST", body: JSON.stringify(input) }, token),
  generateCampaignContent: (id: string, token: string) =>
    request<PlatformPost>(`/campaigns/${id}/posts/generate`, {
      method: "POST",
      body: JSON.stringify({ platform: "instagram", language: "bn" }),
    }, token),
  approvePost: (id: string, token: string) =>
    request<PlatformPost>(`/posts/${id}/approve`, { method: "POST" }, token),
  rejectPost: (id: string, reason: string, token: string) =>
    request<PlatformPost>(`/posts/${id}/reject`, { method: "POST", body: JSON.stringify({ reason }) }, token),
  regeneratePost: (id: string, token: string) =>
    request<PlatformPost>(`/posts/${id}/regenerate`, { method: "POST" }, token),
};

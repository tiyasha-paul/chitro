import type { AuthResponse } from "./api";

const sessionKey = "chitro.session";

export function saveSession(session: AuthResponse): void {
  localStorage.setItem(sessionKey, JSON.stringify(session));
}

export function getSession(): AuthResponse | null {
  try {
    const stored = localStorage.getItem(sessionKey);
    return stored ? (JSON.parse(stored) as AuthResponse) : null;
  } catch {
    localStorage.removeItem(sessionKey);
    return null;
  }
}

export function clearSession(): void {
  localStorage.removeItem(sessionKey);
}

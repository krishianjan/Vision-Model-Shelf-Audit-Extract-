/**
 * Auth — calls POST /auth/token on our FastAPI.
 * Uses storage.ts for token persistence (universal: native + web).
 * No static native-only imports.
 */
import { setItem, getItem, removeItem } from "./storage";

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "kosha_access_token";
const USER_KEY = "kosha_user";

export interface AuthUser {
  user_id: string;
  org_id: string;
  email: string;
  name: string;
}

export async function signIn(email: string, password: string): Promise<AuthUser> {
  const res = await fetch(`${API_URL}/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Invalid email or password");
  }
  const data = await res.json();
  await setItem(TOKEN_KEY, data.access_token);
  const user: AuthUser = {
    user_id: data.user_id,
    org_id: data.org_id,
    email: data.email,
    name: data.name,
  };
  await setItem(USER_KEY, JSON.stringify(user));
  return user;
}

export async function signOut(): Promise<void> {
  await removeItem(TOKEN_KEY);
  await removeItem(USER_KEY);
}

export async function getToken(): Promise<string | null> {
  return getItem(TOKEN_KEY);
}

export async function getUser(): Promise<AuthUser | null> {
  const raw = await getItem(USER_KEY);
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

export async function isLoggedIn(): Promise<boolean> {
  const token = await getItem(TOKEN_KEY);
  return !!token;
}

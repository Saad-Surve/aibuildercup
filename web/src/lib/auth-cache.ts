import type { Me } from "@/lib/types";

const KEY = "resonance-session-v1";
let snapshot: Me | null | undefined;
const listeners = new Set<() => void>();

// A rendering hint only. Firebase and the API remain the authority for every request.
export function readAuthCache(): Me | null {
  if (snapshot !== undefined) return snapshot;
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) ?? "null");
    if (
      value &&
      typeof value === "object" &&
      "uid" in value &&
      typeof value.uid === "string" &&
      "onboardingCompleted" in value &&
      typeof value.onboardingCompleted === "boolean"
    ) {
      snapshot = value as Me;
    } else snapshot = null;
  } catch {
    snapshot = null;
  }
  return snapshot;
}

export function writeAuthCache(profile: Me | null): void {
  snapshot = profile;
  try {
    if (profile) localStorage.setItem(KEY, JSON.stringify(profile));
    else localStorage.removeItem(KEY);
  } catch {
    /* The current session still works when storage is unavailable. */
  }
  for (const listener of listeners) listener();
}

export function subscribeAuthCache(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export const serverAuthCache = (): null => null;

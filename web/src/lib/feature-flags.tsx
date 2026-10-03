"use client";

import { useSyncExternalStore } from "react";

/**
 * Client-side feature flags.
 *
 * Flags are UI experiments a creator turns on in Settings. They live in `localStorage` behind a
 * tiny external store, read through `useSyncExternalStore` so there is no effect-driven state
 * (and no hydration mismatch: the server snapshot is always the defaults). The registry shape
 * means a flag can later be backed by the user's server preferences without changing call sites.
 */

export type FeatureFlagId = "headerTabs" | "copyAuthToken";

export interface FeatureFlagDefinition {
  id: FeatureFlagId;
  label: string;
  description: string;
  defaultValue: boolean;
}

export const FEATURE_FLAGS: FeatureFlagDefinition[] = [
  {
    id: "headerTabs",
    label: "Header tabs",
    description:
      "Show the project module tabs (Transcript, Review, Burn Captions, …) as links in the top header and hide the in-page tab bar.",
    defaultValue: true,
  },
  {
    id: "copyAuthToken",
    label: "Copy auth token",
    description:
      'Show a key button next to your avatar that copies the current Firebase ID token as a "Bearer …" header.',
    defaultValue: true,
  },
];

export type FeatureFlagValues = Record<FeatureFlagId, boolean>;

const STORAGE_KEY = "hc-feature-flags";

//: Frozen so the server snapshot is referentially stable (React compares snapshots by identity).
const DEFAULT_FLAGS: FeatureFlagValues = Object.freeze(
  Object.fromEntries(FEATURE_FLAGS.map((flag) => [flag.id, flag.defaultValue])),
) as FeatureFlagValues;

function defaultFlags(): FeatureFlagValues {
  return DEFAULT_FLAGS;
}

function readStoredFlags(): Partial<FeatureFlagValues> {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return {};
    const stored = parsed as Record<string, unknown>;
    const result: Partial<FeatureFlagValues> = {};
    for (const flag of FEATURE_FLAGS) {
      if (typeof stored[flag.id] === "boolean") {
        result[flag.id] = stored[flag.id] as boolean;
      }
    }
    return result;
  } catch {
    return {};
  }
}

const listeners = new Set<() => void>();
let cache: FeatureFlagValues | null = null;

function snapshot(): FeatureFlagValues {
  if (cache === null) {
    cache = { ...defaultFlags(), ...readStoredFlags() };
  }
  return cache;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function setFeatureFlag(id: FeatureFlagId, value: boolean): void {
  cache = { ...snapshot(), [id]: value };
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(cache));
  } catch {
    // Private mode: the flag still applies for this session.
  }
  for (const listener of listeners) listener();
}

// Keep other tabs in sync.
if (typeof window !== "undefined") {
  window.addEventListener("storage", (event) => {
    if (event.key !== STORAGE_KEY) return;
    cache = { ...defaultFlags(), ...readStoredFlags() };
    for (const listener of listeners) listener();
  });
}

export function useFeatureFlags(): FeatureFlagValues {
  return useSyncExternalStore(subscribe, snapshot, defaultFlags);
}

export function useFeatureFlag(id: FeatureFlagId): boolean {
  return useFeatureFlags()[id];
}

export { setFeatureFlag };

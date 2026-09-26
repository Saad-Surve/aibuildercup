import { useMemo } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { apiFetch } from "@/lib/api-client";
import type { AvatarState, Me } from "@/lib/types";

/*
 * Humation avatar state helpers.
 *
 * The avatar lives on the user document (`PUT /me/avatar`) so it follows the
 * user across browsers. A random seed alone renders a deterministic avatar;
 * explicit part/color selections override it per slot.
 */

export function randomAvatarState(): AvatarState {
  const seed =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.floor(Math.random() * 2 ** 32).toString(36)}`;
  return { seed, selections: {}, colors: {} };
}

/** Normalize a possibly partial/legacy avatar payload into a full state. */
export function normalizeAvatarState(value: unknown): AvatarState {
  if (!value || typeof value !== "object") return randomAvatarState();
  const record = value as Record<string, unknown>;
  const selections: Record<string, string> = {};
  const colors: Record<string, string> = {};
  if (record.selections && typeof record.selections === "object") {
    for (const [slot, part] of Object.entries(
      record.selections as Record<string, unknown>,
    )) {
      if (typeof part === "string") selections[slot] = part;
    }
  }
  if (record.colors && typeof record.colors === "object") {
    for (const [slot, color] of Object.entries(
      record.colors as Record<string, unknown>,
    )) {
      if (typeof color === "string") colors[slot] = color;
    }
  }
  return {
    seed: typeof record.seed === "string" ? record.seed : null,
    selections,
    colors,
  };
}

export function updateAvatar(state: AvatarState): Promise<AvatarState> {
  return apiFetch<AvatarState>("/me/avatar", {
    method: "PUT",
    body: JSON.stringify(state),
  });
}

/** The effective avatar: stored state, or a fresh random one until saved. */
export function useUserAvatar(): AvatarState {
  const { profile } = useAuth();
  return useMemo(() => {
    if (profile?.avatar) return normalizeAvatarState(profile.avatar);
    return randomAvatarState();
  }, [profile]);
}

let ensureTask: Promise<AvatarState | null> | null = null;

/*
 * Persist a random avatar for users who have none yet (first run after this
 * feature ships, or pre-existing accounts). Module-level dedupe so concurrent
 * callers share one PUT; failures resolve null and retry on the next call.
 */
export function ensureAvatarAssigned(
  profile: Me | null,
): Promise<AvatarState | null> {
  if (!profile || profile.avatar)
    return Promise.resolve(profile?.avatar ?? null);
  if (!ensureTask) {
    ensureTask = updateAvatar(randomAvatarState())
      .catch(() => null)
      .finally(() => {
        ensureTask = null;
      });
  }
  return ensureTask;
}

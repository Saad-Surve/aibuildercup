"use client";

import { useAuth } from "@/components/auth/auth-provider";

/**
 * Read-only demo mode.
 *
 * The demo account (`Me.readOnly`) may browse everything it owns but never change it. The API
 * enforces this on every mutating request; `useReadOnly` lets the UI disable the same controls
 * and explain why, so the demo never looks broken when a click is refused.
 */

export const READ_ONLY_REASON =
  "This is the read-only demo account. Changes are disabled.";

export function useReadOnly(): boolean {
  const { profile } = useAuth();
  return profile?.readOnly ?? false;
}

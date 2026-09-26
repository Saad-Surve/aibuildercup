"use client";

import { useEffect } from "react";

import { useAuth } from "@/components/auth/auth-provider";
import { ensureAvatarAssigned } from "@/lib/avatar";

/*
 * Assigns a random avatar on first sight for users who have none stored yet,
 * then refreshes the profile so every avatar instance updates. Mount once
 * inside the authenticated layout.
 */
export function AvatarBootstrap() {
  const { profile, status, refreshProfile } = useAuth();

  useEffect(() => {
    if (status !== "signed_in" || !profile || profile.avatar) return;
    let alive = true;
    void ensureAvatarAssigned(profile).then((state) => {
      if (alive && state) void refreshProfile();
    });
    return () => {
      alive = false;
    };
  }, [status, profile, refreshProfile]);

  return null;
}

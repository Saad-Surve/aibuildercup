"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  GoogleAuthProvider,
  onAuthStateChanged,
  signInWithCustomToken,
  signInWithPopup,
  signInWithRedirect,
  signOut as firebaseSignOut,
  type User,
} from "firebase/auth";

import { ApiError, apiFetch } from "@/lib/api-client";
import { API_BASE_URL } from "@/lib/api-base";
import { DEMO_ENABLED } from "@/lib/demo";
import { auth } from "@/lib/firebase";
import type { Me } from "@/lib/types";

export type AuthStatus = "loading" | "signed_out" | "signed_in" | "error";

interface AuthContextValue {
  user: User | null;
  profile: Me | null;
  status: AuthStatus;
  error: string | null;
  signInWithGoogle: () => Promise<void>;
  signInAsDemo: () => Promise<void>;
  demoAvailable: boolean;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.code}: ${error.message}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong.";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Me | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    const unsubscribe = onAuthStateChanged(auth, async (nextUser) => {
      if (!active) return;
      setUser(nextUser);

      if (!nextUser) {
        setProfile(null);
        setError(null);
        setStatus("signed_out");
        return;
      }

      setStatus("loading");
      setError(null);
      try {
        const me = await apiFetch<Me>("/me");
        if (!active) return;
        setProfile(me);
        setStatus("signed_in");
      } catch (caught) {
        if (!active) return;
        setError(describeError(caught));
        setStatus("error");
      }
    });

    return () => {
      active = false;
      unsubscribe();
    };
  }, []);

  const signInWithGoogle = useCallback(async () => {
    setError(null);
    const provider = new GoogleAuthProvider();
    try {
      await signInWithPopup(auth, provider);
    } catch (caught) {
      // Popup blocked (or disallowed) — fall back to a same-tab redirect.
      const code =
        caught && typeof caught === "object" && "code" in caught
          ? String((caught as { code?: unknown }).code)
          : "";
      if (code === "auth/popup-blocked" || code === "auth/operation-not-supported-in-this-environment") {
        try {
          await signInWithRedirect(auth, provider);
          return;
        } catch (fallback) {
          setError(describeError(fallback));
          setStatus("signed_out");
          return;
        }
      }
      setError(describeError(caught));
      setStatus("signed_out");
    }
  }, []);

  const signOut = useCallback(async () => {
    await firebaseSignOut(auth);
  }, []);

  const signInAsDemo = useCallback(async () => {
    setError(null);
    if (!DEMO_ENABLED) {
      setError("The demo account is not configured.");
      return;
    }
    try {
      // The API mints a custom token for the read-only demo account, so no password ever
      // reaches the browser. The endpoint is unauthenticated on purpose.
      const response = await fetch(`${API_BASE_URL}/demo/session`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error("Could not start the demo session.");
      }
      const { token } = (await response.json()) as { token: string };
      await signInWithCustomToken(auth, token);
    } catch (caught) {
      setError(describeError(caught));
      setStatus("signed_out");
    }
  }, []);

  const refreshProfile = useCallback(async () => {
    if (!auth.currentUser) return;
    try {
      const me = await apiFetch<Me>("/me");
      setProfile(me);
      setError(null);
      setStatus("signed_in");
    } catch (caught) {
      setError(describeError(caught));
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      profile,
      status,
      error,
      signInWithGoogle,
      signInAsDemo,
      demoAvailable: DEMO_ENABLED,
      signOut,
      refreshProfile,
    }),
    [user, profile, status, error, signInWithGoogle, signInAsDemo, signOut, refreshProfile],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

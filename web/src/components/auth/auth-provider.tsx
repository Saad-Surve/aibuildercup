"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
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
import { useQueryClient } from "@tanstack/react-query";

import { ApiError, apiFetch } from "@/lib/api-client";
import { API_BASE_URL } from "@/lib/api-base";
import { DEMO_ENABLED } from "@/lib/demo";
import { auth } from "@/lib/firebase";
import {
  readAuthCache,
  writeAuthCache,
  subscribeAuthCache,
  serverAuthCache,
} from "@/lib/auth-cache";
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
  const queryClient = useQueryClient();
  const cached = useSyncExternalStore(
    subscribeAuthCache,
    readAuthCache,
    serverAuthCache,
  );
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Me | null>(null);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let previousUid: string | null | undefined;
    let profileRequest: AbortController | null = null;

    const unsubscribe = onAuthStateChanged(auth, async (nextUser) => {
      if (!active) return;
      profileRequest?.abort();
      if ((previousUid ?? readAuthCache()?.uid) !== nextUser?.uid)
        queryClient.clear();
      previousUid = nextUser?.uid;
      setUser(nextUser);

      if (!nextUser) {
        writeAuthCache(null);
        setProfile(null);
        setError(null);
        setStatus("signed_out");
        return;
      }

      const restored = readAuthCache();
      if (restored?.uid === nextUser.uid) {
        setProfile(restored);
        setStatus("signed_in");
      } else {
        writeAuthCache(null);
        setProfile(null);
        setStatus("loading");
      }
      setError(null);
      const controller = new AbortController();
      profileRequest = controller;
      try {
        const me = await apiFetch<Me>("/me", { signal: controller.signal });
        if (!active || controller.signal.aborted) return;
        writeAuthCache(me);
        setProfile(me);
        setStatus("signed_in");
      } catch (caught) {
        if (!active || controller.signal.aborted) return;
        setError(describeError(caught));
        const authoritative =
          caught instanceof ApiError &&
          (caught.status === 401 || caught.status === 403);
        if (!authoritative && readAuthCache()?.uid === nextUser.uid) {
          setStatus("signed_in");
        } else {
          writeAuthCache(null);
          setStatus("error");
        }
      }
    });

    return () => {
      active = false;
      profileRequest?.abort();
      unsubscribe();
    };
  }, [queryClient]);

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
      if (
        code === "auth/popup-blocked" ||
        code === "auth/operation-not-supported-in-this-environment"
      ) {
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
    writeAuthCache(null);
    queryClient.clear();
  }, [queryClient]);

  const signInAsDemo = useCallback(async () => {
    setError(null);
    if (!DEMO_ENABLED) {
      setError("The demo is unavailable right now.");
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
    const currentUser = auth.currentUser;
    if (!currentUser) return;
    try {
      const me = await apiFetch<Me>("/me");
      if (auth.currentUser !== currentUser) return;
      writeAuthCache(me);
      setProfile(me);
      setError(null);
      setStatus("signed_in");
    } catch (caught) {
      if (auth.currentUser !== currentUser) return;
      setError(describeError(caught));
    }
  }, []);

  const value = useMemo(
    () => ({
      user,
      profile: profile ?? (status === "loading" ? cached : null),
      status:
        status === "loading" && cached?.onboardingCompleted
          ? ("signed_in" as const)
          : status,
      error,
      signInWithGoogle,
      signInAsDemo,
      demoAvailable: DEMO_ENABLED,
      signOut,
      refreshProfile,
    }),
    [
      user,
      cached,
      profile,
      status,
      error,
      signInWithGoogle,
      signInAsDemo,
      signOut,
      refreshProfile,
    ],
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

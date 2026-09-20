"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AuthLoadingScreen } from "@/components/auth/auth-loading-screen";
import { useAuth } from "@/components/auth/auth-provider";
import { GoogleSignInButton } from "@/components/auth/google-sign-in-button";
import { CenteredScreen } from "@/components/common/centered-screen";
import { Logo } from "@/components/common/logo";
import { Button } from "@/components/ui/button";

function ErrorNotice({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
    >
      {message}
    </div>
  );
}

export function LoginPage() {
  const { profile, status, error, signInWithGoogle, signOut } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "signed_in" && profile) {
      router.replace(
        profile.onboardingCompleted ? "/dashboard" : "/onboarding",
      );
    }
  }, [status, profile, router]);

  const redirecting =
    status === "loading" || (status === "signed_in" && Boolean(profile));

  return (
    <CenteredScreen className="relative overflow-hidden">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-32 left-1/2 h-72 w-[36rem] -translate-x-1/2 rounded-full bg-signal/10 blur-3xl"
      />

      <div className="relative w-full max-w-sm">
        <Logo className="mb-8" />

        <div className="rounded-xl bg-card p-6 ring-1 ring-foreground/10">
          {redirecting ? (
            <div className="py-6">
              <AuthLoadingScreen label="Taking you to your studio…" />
            </div>
          ) : status === "error" ? (
            <div className="flex flex-col gap-4">
              <div className="space-y-1">
                <h1 className="font-heading text-lg font-semibold tracking-tight">
                  We couldn&apos;t verify your session
                </h1>
                <p className="text-sm text-muted-foreground">
                  Your sign-in worked, but the studio API didn&apos;t answer.
                </p>
              </div>
              <ErrorNotice message={error ?? "Unknown error."} />
              <Button variant="outline" onClick={signOut}>
                Sign out and try again
              </Button>
            </div>
          ) : (
            <div className="flex flex-col gap-5">
              <div className="space-y-1">
                <h1 className="font-heading text-lg font-semibold tracking-tight">
                  Sign in
                </h1>
                <p className="text-sm text-muted-foreground">
                  Review, improve, and localize your videos with AI reviewers.
                </p>
              </div>

              {error ? <ErrorNotice message={error} /> : null}

              <GoogleSignInButton onClick={signInWithGoogle} />

              <p className="text-xs leading-relaxed text-muted-foreground">
                We use your Google account only to identify you. Your token is
                verified by the API, and your video data stays in your project.
              </p>
            </div>
          )}
        </div>
      </div>
    </CenteredScreen>
  );
}

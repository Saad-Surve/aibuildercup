"use client";

import { useEffect } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";

import { AuthLoadingScreen } from "@/components/auth/auth-loading-screen";
import { useAuth } from "@/components/auth/auth-provider";
import { GoogleSignInButton } from "@/components/auth/google-sign-in-button";
import { LandingBackground } from "@/components/landing/landing-background";
import { Button } from "@/components/ui/button";

export function LandingPage() {
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
    <main className="relative flex h-[100dvh] flex-col overflow-hidden bg-background text-foreground">
      <LandingBackground />

      <div className="relative flex flex-1 flex-col items-center justify-center px-6 text-center">
        {redirecting ? (
          <AuthLoadingScreen label="Taking you to your studio…" />
        ) : (
          <div className="flex w-full max-w-2xl flex-col items-center gap-6">
            <Image
              src="/logo-mark.png"
              alt="Resonance"
              width={194}
              height={145}
              priority
              className="h-auto w-[170px] sm:w-[200px]"
            />

            <h1 className="max-w-[16ch] font-serif text-5xl leading-[1.05] font-medium tracking-tight text-balance sm:text-6xl lg:text-7xl">
              Create Without Limits
            </h1>

            <p className="max-w-xl text-pretty text-base text-muted-foreground sm:text-lg">
              Your all-in-one creative studio for artists, filmmakers &amp;
              digital creators
            </p>

            <div className="mt-1">
              {status === "error" ? (
                <div className="flex flex-col items-center gap-3">
                  <p role="alert" className="text-sm text-destructive">
                    {error ?? "We couldn't reach the studio API."}
                  </p>
                  <Button
                    variant="outline"
                    onClick={signOut}
                    className="rounded-full"
                  >
                    Sign out and try again
                  </Button>
                </div>
              ) : (
                <GoogleSignInButton onClick={signInWithGoogle} />
              )}
            </div>
          </div>
        )}
      </div>

      <footer className="relative pb-5 text-center text-xs text-muted-foreground">
        Resonance · A digital creator studio
      </footer>
    </main>
  );
}

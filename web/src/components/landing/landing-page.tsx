"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AuthLoadingScreen } from "@/components/auth/auth-loading-screen";
import { useAuth } from "@/components/auth/auth-provider";
import { SignInPanel } from "@/components/auth/sign-in-panel";
import { Logo } from "@/components/common/logo";
import { HeroIllustration } from "@/components/landing/hero-illustration";

export function LandingPage() {
  const { profile, status } = useAuth();
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
    <div className="flex min-h-[100dvh] flex-col lg:flex-row">
      <section className="relative flex flex-1 flex-col justify-center gap-8 overflow-hidden px-8 py-14 lg:px-16">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-24 -left-24 h-72 w-72 rounded-full bg-signal/10 blur-3xl"
        />

        <Logo className="relative" />

        <div className="relative space-y-4">
          <h1 className="max-w-[18ch] font-heading text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            See what your video really says.
          </h1>
          <p className="max-w-[48ch] text-sm text-muted-foreground sm:text-base">
            One upload gives you a timestamped transcript, a multi-reviewer
            heatmap under the timeline, and ready-to-publish clips, captions,
            and posts.
          </p>
        </div>

        <HeroIllustration className="relative w-full max-w-md" />
      </section>

      <div
        aria-hidden="true"
        className="h-px w-full bg-border lg:h-auto lg:w-px"
      />

      <section className="flex flex-1 items-center justify-center px-8 py-14 lg:px-16">
        <div className="w-full max-w-sm">
          {redirecting ? (
            <AuthLoadingScreen label="Taking you to your studio…" />
          ) : (
            <SignInPanel />
          )}
        </div>
      </section>
    </div>
  );
}

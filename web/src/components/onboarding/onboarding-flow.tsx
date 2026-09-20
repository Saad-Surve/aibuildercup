"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AuthLoadingScreen } from "@/components/auth/auth-loading-screen";
import { useAuth } from "@/components/auth/auth-provider";
import { CenteredScreen } from "@/components/common/centered-screen";
import { Logo } from "@/components/common/logo";
import { StepRail } from "@/components/onboarding/step-rail";
import {
  AudienceStep,
  DoneStep,
  IdentityStep,
  PersonaStep,
  PlatformsStep,
  StyleStep,
  TopicsStep,
  WelcomeStep,
} from "@/components/onboarding/steps";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { ApiError, apiFetch } from "@/lib/api-client";
import {
  ONBOARDING_STEPS,
  answersForStep,
  stepIsComplete,
  type OnboardingAnswers,
  type StepId,
} from "@/lib/onboarding";
import type { OnboardingState, Persona } from "@/lib/types";

const DATA_STEPS: StepId[] = [
  "identity",
  "topics",
  "audience",
  "style",
  "platforms",
];

function describe(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

export function OnboardingFlow() {
  const { profile, refreshProfile } = useAuth();
  const router = useRouter();

  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<OnboardingAnswers>({});
  const [persona, setPersona] = useState<Persona | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    apiFetch<OnboardingState>("/onboarding")
      .then((state) => {
        if (!active) return;
        setAnswers((state.answers ?? {}) as OnboardingAnswers);
        if (state.currentStep) {
          const resume = ONBOARDING_STEPS.findIndex(
            (item) => item.id === state.currentStep,
          );
          if (resume >= 0) setIndex(resume);
        }
      })
      .catch((caught) => {
        if (active) setError(describe(caught));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const step = ONBOARDING_STEPS[index];
  const isLast = index === ONBOARDING_STEPS.length - 1;

  const update = useCallback((patch: Partial<OnboardingAnswers>) => {
    setAnswers((previous) => ({ ...previous, ...patch }));
  }, []);

  async function goNext() {
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      if (DATA_STEPS.includes(step.id)) {
        await apiFetch("/onboarding", {
          method: "PUT",
          body: JSON.stringify({
            step: step.id,
            answers: answersForStep(step.id, answers),
          }),
        });
      }

      if (step.id === "platforms") {
        // Regenerate each time the user reaches this point, so edits made by
        // going back are reflected in the persona.
        await apiFetch("/onboarding/complete", { method: "POST" });
        const generated = await apiFetch<Persona>("/persona");
        setPersona(generated);
        await refreshProfile();
      }

      if (!isLast) setIndex((value) => value + 1);
    } catch (caught) {
      setError(describe(caught));
    } finally {
      setBusy(false);
    }
  }

  function goBack() {
    setError(null);
    setIndex((value) => Math.max(0, value - 1));
  }

  if (loading) {
    return (
      <CenteredScreen>
        <AuthLoadingScreen label="Loading your progress…" />
      </CenteredScreen>
    );
  }

  const canContinue = stepIsComplete(step.id, answers);
  const percent = Math.round(((index + 1) / ONBOARDING_STEPS.length) * 100);

  const continueLabel =
    step.id === "welcome"
      ? "Get started"
      : step.id === "platforms"
        ? "Generate persona"
        : "Continue";

  function renderStep() {
    switch (step.id) {
      case "welcome":
        return <WelcomeStep />;
      case "identity":
        return <IdentityStep answers={answers} update={update} />;
      case "topics":
        return <TopicsStep answers={answers} update={update} />;
      case "audience":
        return <AudienceStep answers={answers} update={update} />;
      case "style":
        return <StyleStep answers={answers} update={update} />;
      case "platforms":
        return <PlatformsStep answers={answers} update={update} />;
      case "persona":
        return <PersonaStep persona={persona} />;
      case "done":
        return (
          <DoneStep
            name={profile?.displayName ?? undefined}
            onFinish={() => router.push("/dashboard")}
          />
        );
    }
  }

  return (
    <div className="min-h-[100dvh]">
      <header className="border-b">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-6">
          <Logo />
          <span className="tabular text-xs text-muted-foreground">
            {String(index + 1).padStart(2, "0")} /{" "}
            {String(ONBOARDING_STEPS.length).padStart(2, "0")}
          </span>
        </div>
      </header>

      <div className="mx-auto grid max-w-6xl gap-12 px-6 py-10 lg:grid-cols-[200px_1fr]">
        <aside className="hidden lg:block">
          <StepRail currentIndex={index} />
        </aside>

        <main className="min-w-0 max-w-2xl">
          <div className="mb-8 lg:hidden">
            <Progress value={percent} />
          </div>

          <div className="space-y-2">
            <h1 className="font-heading text-2xl font-semibold tracking-tight">
              {step.title}
            </h1>
            <p className="max-w-[65ch] text-sm text-muted-foreground">
              {step.description}
            </p>
          </div>

          <div className="mt-8">{renderStep()}</div>

          {error ? (
            <p className="mt-6 text-sm text-destructive">{error}</p>
          ) : null}

          {!isLast ? (
            <div className="mt-10 flex items-center gap-3 border-t pt-6">
              {index > 0 ? (
                <Button variant="ghost" onClick={goBack} disabled={busy}>
                  Back
                </Button>
              ) : null}
              <Button
                size="lg"
                onClick={goNext}
                disabled={busy || !canContinue}
              >
                {busy ? <Spinner /> : null}
                {continueLabel}
              </Button>
            </div>
          ) : null}
        </main>
      </div>
    </div>
  );
}

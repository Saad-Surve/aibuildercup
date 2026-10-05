"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AuthLoadingScreen } from "@/components/auth/auth-loading-screen";
import { useAuth } from "@/components/auth/auth-provider";
import { CenteredScreen } from "@/components/common/centered-screen";
import { Icon } from "@/components/common/icon";
import { Logo } from "@/components/common/logo";
import { UserMenu } from "@/components/layout/user-menu";
import { StepRail } from "@/components/onboarding/step-rail";
import {
  AudienceStep,
  DoneStep,
  IdentityStep,
  ImportStep,
  PersonaStep,
  PlatformsStep,
  StyleStep,
  TopicsStep,
  WelcomeStep,
} from "@/components/onboarding/steps";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { ArrowLeft01Icon } from "@hugeicons/core-free-icons";
import { ApiError, apiFetch } from "@/lib/api-client";
import {
  ONBOARDING_STEPS,
  answersForStep,
  mergeResearchAnswers,
  stepIsComplete,
  type OnboardingAnswers,
  type StepId,
} from "@/lib/onboarding";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";
import type { OnboardingResearch, OnboardingState, Persona } from "@/lib/types";

const DATA_STEPS: StepId[] = [
  "import",
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

export function OnboardingFlow({
  mode = "onboarding",
}: {
  mode?: "onboarding" | "edit";
}) {
  const { profile, refreshProfile } = useAuth();
  const router = useRouter();
  const readOnly = useReadOnly();

  // Editing reuses the same steps but starts at the first data step and ends
  // back on the profile, with every answer prefilled from what was saved. The
  // import shortcut is onboarding-only, so editing skips it.
  const steps =
    mode === "edit"
      ? ONBOARDING_STEPS.filter(
          (item) => item.id !== "welcome" && item.id !== "import",
        )
      : ONBOARDING_STEPS;

  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<OnboardingAnswers>({});
  // Last answers known to be persisted, used to skip no-op PUTs.
  const [savedAnswers, setSavedAnswers] = useState<OnboardingAnswers>({});
  const [persona, setPersona] = useState<Persona | null>(null);
  const [research, setResearch] = useState<OnboardingResearch | null>(null);
  const [researchTried, setResearchTried] = useState(false);
  const [researchError, setResearchError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    apiFetch<OnboardingState>("/onboarding")
      .then((state) => {
        if (!active) return;
        const loaded = (state.answers ?? {}) as OnboardingAnswers;
        setAnswers(loaded);
        setSavedAnswers(loaded);
        if (mode === "onboarding" && state.currentStep) {
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
  }, [mode]);

  const step = steps[index];
  const isLast = index === steps.length - 1;

  const update = useCallback((patch: Partial<OnboardingAnswers>) => {
    setAnswers((previous) => ({ ...previous, ...patch }));
  }, []);

  async function persistCurrentStep() {
    if (!DATA_STEPS.includes(step.id)) return;

    // Only write when something actually changed on this step.
    const slice = answersForStep(step.id, answers);
    const saved = answersForStep(step.id, savedAnswers);
    if (JSON.stringify(slice) === JSON.stringify(saved)) return;

    await apiFetch("/onboarding", {
      method: "PUT",
      body: JSON.stringify({ step: step.id, answers: slice }),
    });
    setSavedAnswers((previous) => ({ ...previous, ...slice }));
  }

  async function generatePersona() {
    // Regenerate so edits made by going back are reflected in the persona.
    await apiFetch("/onboarding/complete", { method: "POST" });
    const generated = await apiFetch<Persona>("/persona");
    setPersona(generated);
    await refreshProfile();
  }

  // Research the creator from their public links and prefill the form. Kept self-contained:
  // a failure is shown inline and does not block the creator from continuing manually.
  async function runResearch() {
    const links = answers.creatorLinks ?? [];
    if (links.length === 0) return;
    setError(null);
    setResearchError(null);
    setBusy(true);
    try {
      const result = await apiFetch<OnboardingResearch>("/onboarding/research", {
        method: "POST",
        body: JSON.stringify({ links }),
      });
      const { answers: merged } = mergeResearchAnswers(answers, result.answers);
      setAnswers(merged);
      // The API already persisted the merged answers and the links, so don't re-PUT them.
      setSavedAnswers(merged);
      setResearch(result);
    } catch (caught) {
      setResearchError(describe(caught));
    } finally {
      setResearchTried(true);
      setBusy(false);
    }
  }

  async function goNext() {
    if (busy) return;
    setError(null);
    setBusy(true);
    try {
      if (step.id === "import") {
        const links = answers.creatorLinks ?? [];
        if (links.length > 0 && !research && !researchTried) {
          // Research first, and stay so the creator can review the result and sources.
          await runResearch();
          return;
        }
      }
      await persistCurrentStep();
      if (step.id === "platforms") {
        await generatePersona();
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

  // Jump directly to a step from the rail. The current step is saved first so
  // nothing typed is lost, and the persona is generated if it is needed.
  async function goTo(target: number) {
    if (busy || target === index || target < 0 || target >= steps.length)
      return;
    setError(null);
    setBusy(true);
    try {
      await persistCurrentStep();
      const targetStep = steps[target];
      if (
        (targetStep.id === "persona" || targetStep.id === "done") &&
        !persona
      ) {
        await generatePersona();
      }
      setIndex(target);
    } catch (caught) {
      setError(describe(caught));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <CenteredScreen>
        <AuthLoadingScreen label="Loading your progress…" />
      </CenteredScreen>
    );
  }

  const canContinue = stepIsComplete(step.id, answers);

  if (readOnly) {
    return (
      <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-4 px-6 text-center">
        <h1 className="font-heading text-2xl font-semibold tracking-tight">
          Editing is disabled
        </h1>
        <p className="max-w-prose text-sm text-muted-foreground">
          {READ_ONLY_REASON} You can browse the rest of the studio freely.
        </p>
        <Button
          variant="outline"
          onClick={() =>
            router.push(mode === "edit" ? "/profile" : "/dashboard")
          }
        >
          Back
        </Button>
      </div>
    );
  }
  const percent = Math.round(((index + 1) / steps.length) * 100);

  const linksGiven = (answers.creatorLinks ?? []).length > 0;
  const continueLabel =
    step.id === "welcome"
      ? "Get started"
      : step.id === "import"
        ? research || researchTried || !linksGiven
          ? "Continue"
          : "Research with Gemini"
        : step.id === "platforms"
          ? "Generate persona"
          : "Continue";

  function renderStep() {
    switch (step.id) {
      case "welcome":
        return <WelcomeStep />;
      case "import":
        return (
          <ImportStep
            links={answers.creatorLinks ?? []}
            onLinksChange={(links) => update({ creatorLinks: links })}
            research={research}
            researchError={researchError}
            busy={busy}
            onResearch={runResearch}
          />
        );
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
            mode={mode}
            onFinish={() =>
              router.push(mode === "edit" ? "/profile" : "/dashboard")
            }
          />
        );
    }
  }

  return (
    <div className="min-h-[100dvh]">
      <header className="sticky top-0 z-30 border-b border-transparent bg-background/80 shadow-[inset_0_-1px_0_0_var(--color-border)] backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-3 px-6">
          <Logo href="/dashboard" />
          <div className="flex items-center gap-2">
            {mode === "edit" ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => router.push("/profile")}
              >
                <Icon icon={ArrowLeft01Icon} />
                Back to profile
              </Button>
            ) : null}
            <UserMenu />
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-6xl gap-12 px-6 py-10 lg:grid-cols-[200px_1fr]">
        <aside className="hidden lg:block">
          <StepRail steps={steps} currentIndex={index} onSelect={goTo} />
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
            <div className="mt-10 flex items-center gap-3 border-t border-transparent pt-6 shadow-[inset_0_1px_0_0_var(--color-border)]">
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
              <span className="tabular ml-auto text-xs text-muted-foreground">
                {String(index + 1).padStart(2, "0")} /{" "}
                {String(steps.length).padStart(2, "0")}
              </span>
            </div>
          ) : null}
        </main>
      </div>
    </div>
  );
}

"use client";

import { Tick02Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { cn } from "@/lib/utils";
import type { StepMeta } from "@/lib/onboarding";

export function StepRail({
  steps,
  currentIndex,
  onSelect,
}: {
  steps: StepMeta[];
  currentIndex: number;
  onSelect: (index: number) => void;
}) {
  return (
    <nav aria-label="Steps" className="space-y-0.5">
      {steps.map((step, index) => {
        const state =
          index < currentIndex
            ? "done"
            : index === currentIndex
              ? "current"
              : "upcoming";

        return (
          <button
            key={step.id}
            type="button"
            onClick={() => onSelect(index)}
            aria-current={state === "current" ? "step" : undefined}
            className="flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            <span
              className={cn(
                "tabular flex size-6 shrink-0 items-center justify-center rounded-md border text-[0.7rem]",
                state === "current" &&
                  "border-signal bg-signal text-signal-foreground",
                state === "done" &&
                  "border-transparent bg-muted text-foreground",
                state === "upcoming" && "border-border text-muted-foreground",
              )}
            >
              {state === "done" ? (
                <Icon icon={Tick02Icon} className="size-3.5" />
              ) : (
                String(index + 1).padStart(2, "0")
              )}
            </span>
            <span
              className={cn(
                "text-sm",
                state === "current"
                  ? "font-medium text-foreground"
                  : "text-muted-foreground",
              )}
            >
              {step.label}
            </span>
          </button>
        );
      })}
    </nav>
  );
}

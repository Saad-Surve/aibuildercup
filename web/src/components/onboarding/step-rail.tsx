import { Tick02Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { cn } from "@/lib/utils";
import { ONBOARDING_STEPS } from "@/lib/onboarding";

export function StepRail({ currentIndex }: { currentIndex: number }) {
  return (
    <nav aria-label="Onboarding steps" className="space-y-0.5">
      {ONBOARDING_STEPS.map((step, index) => {
        const state =
          index < currentIndex
            ? "done"
            : index === currentIndex
              ? "current"
              : "upcoming";

        return (
          <div
            key={step.id}
            aria-current={state === "current" ? "step" : undefined}
            className="flex items-center gap-3 py-1.5"
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
          </div>
        );
      })}
    </nav>
  );
}

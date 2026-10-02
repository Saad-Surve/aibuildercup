"use client";

import Link from "next/link";
import {
  ArrowRight01Icon,
  ClosedCaptionIcon,
  SparklesIcon,
} from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { STUDIO_MODULES, type StudioModule } from "@/lib/studio";
import { cn } from "@/lib/utils";

type Availability = "ready" | "needs-video" | "needs-transcript" | "soon";

const AVAILABILITY_STYLE: Record<Availability, string> = {
  ready: "border-sev-good/30 bg-sev-good/10 text-sev-good",
  "needs-video": "border-border bg-muted text-muted-foreground",
  "needs-transcript": "border-sev-low/30 bg-sev-low/10 text-sev-low",
  soon: "border-border bg-muted text-muted-foreground",
};

const AVAILABILITY_LABEL: Record<Availability, string> = {
  ready: "Ready",
  "needs-video": "Needs video",
  "needs-transcript": "Needs transcript",
  soon: "Coming soon",
};

function availability(
  module: StudioModule,
  hasVideo: boolean,
  hasTranscript: boolean,
): Availability {
  if (!module.ready) return "soon";
  if (module.needsTranscript) {
    if (!hasVideo) return "needs-video";
    if (!hasTranscript) return "needs-transcript";
  }
  return "ready";
}

function href(projectId: string, moduleId: string) {
  return `/projects/view?projectId=${projectId}&module=${moduleId}`;
}

/**
 * The studio landing: what this project can do, in the order a creator cares
 * about. Clicking a module opens that focused workspace rather than dropping
 * everything on one page at once.
 */
export function ModuleGrid({
  projectId,
  hasVideo,
  hasTranscript,
}: {
  projectId: string;
  hasVideo: boolean;
  hasTranscript: boolean;
}) {
  const transcriptModule = STUDIO_MODULES.find(
    (module) => module.id === "transcript",
  );
  const rest = STUDIO_MODULES.filter((module) => module.id !== "transcript");

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="font-heading text-base font-medium">Your studio</h2>
        <p className="text-sm text-muted-foreground">
          Pick a module to work on. The transcript powers most of them.
        </p>
      </div>

      {transcriptModule ? (
        <ModuleCard
          module={transcriptModule}
          availability={availability(transcriptModule, hasVideo, hasTranscript)}
          href={href(projectId, transcriptModule.id)}
          featured
        />
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2">
        {rest.map((module) => (
          <ModuleCard
            key={module.id}
            module={module}
            availability={availability(module, hasVideo, hasTranscript)}
            href={href(projectId, module.id)}
          />
        ))}
      </div>
    </div>
  );
}

function ModuleCard({
  module,
  availability: state,
  href: target,
  featured = false,
}: {
  module: StudioModule;
  availability: Availability;
  href: string;
  featured?: boolean;
}) {
  return (
    <Link href={target} className="group block">
      <Card
        className={cn(
          "h-full gap-2 py-(--card-spacing) transition-shadow group-hover:shadow-md group-hover:ring-foreground/20",
          featured && "bg-muted/30",
        )}
      >
        <div className="flex items-start gap-3 px-(--card-spacing)">
          <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-foreground">
            <Icon icon={module.icon} className="size-5" />
          </span>
          <div className="min-w-0 flex-1 space-y-1">
            <div className="flex items-center justify-between gap-2">
              <span className="font-heading font-medium">{module.label}</span>
              <Badge
                variant="outline"
                className={cn("shrink-0", AVAILABILITY_STYLE[state])}
              >
                {AVAILABILITY_LABEL[state]}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground">
              {module.description}
            </p>
            <span className="inline-flex items-center gap-1 pt-1 text-xs text-signal opacity-0 transition-opacity group-hover:opacity-100">
              Open
              <Icon icon={ArrowRight01Icon} className="size-3.5" />
            </span>
          </div>
        </div>
      </Card>
    </Link>
  );
}

export const TRANSCRIPT_ICON = ClosedCaptionIcon;
export const REVIEW_ICON = SparklesIcon;

"use client";

import { ArrowRight01Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { prefetchStudioModule } from "@/components/projects/studio/module-registry";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  STUDIO_MODULES,
  type StudioModule,
  type StudioModuleId,
  studioModuleHref,
} from "@/lib/studio";
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

/**
 * The studio landing as a bento: the transcript is the wide hero (it powers the
 * rest), and the other modules tile beneath it. One grid, one gap, so nothing
 * drifts.
 *
 * Cards are real `<a href>`s but left clicks are intercepted and swapped in
 * place with `history.pushState` (see `ModuleNav`), so opening a module never
 * reloads the workspace.
 */
export function ModuleGrid({
  projectId,
  hasVideo,
  hasTranscript,
  onSelect,
}: {
  projectId: string;
  hasVideo: boolean;
  hasTranscript: boolean;
  onSelect: (moduleId: StudioModuleId) => void;
}) {
  const transcriptModule = STUDIO_MODULES.find(
    (module) => module.id === "transcript",
  );
  const rest = STUDIO_MODULES.filter((module) => module.id !== "transcript");

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {transcriptModule ? (
        <ModuleCard
          module={transcriptModule}
          projectId={projectId}
          availability={availability(transcriptModule, hasVideo, hasTranscript)}
          onSelect={onSelect}
          featured
          className="sm:col-span-2"
        />
      ) : null}
      {rest.map((module) => (
        <ModuleCard
          key={module.id}
          module={module}
          projectId={projectId}
          availability={availability(module, hasVideo, hasTranscript)}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}

function ModuleCard({
  module,
  projectId,
  availability: state,
  onSelect,
  featured = false,
  className,
}: {
  module: StudioModule;
  projectId: string;
  availability: Availability;
  onSelect: (moduleId: StudioModuleId) => void;
  featured?: boolean;
  className?: string;
}) {
  return (
    <a
      href={studioModuleHref(projectId, module.id)}
      aria-label={`Open ${module.label}`}
      className={cn("group block", className)}
      onMouseEnter={() => prefetchStudioModule(module.id)}
      onFocus={() => prefetchStudioModule(module.id)}
      onClick={(event) => {
        if (event.defaultPrevented) return;
        if (
          event.button !== 0 ||
          event.metaKey ||
          event.ctrlKey ||
          event.shiftKey ||
          event.altKey
        ) {
          return;
        }
        event.preventDefault();
        onSelect(module.id);
      }}
    >
      <Card
        className={cn(
          "h-full gap-2 py-(--card-spacing) transition-shadow group-hover:shadow-md group-hover:ring-foreground/20",
          featured && "bg-muted/30",
        )}
      >
        <div className="flex items-start gap-3 px-(--card-spacing)">
          <span
            className={cn(
              "mt-0.5 flex shrink-0 items-center justify-center rounded-lg bg-muted text-foreground",
              featured ? "size-11" : "size-9",
            )}
          >
            <Icon
              icon={module.icon}
              className={featured ? "size-6" : "size-5"}
            />
          </span>
          <div className="min-w-0 flex-1 space-y-1">
            <div className="flex items-center justify-between gap-2">
              <span
                className={cn(
                  "font-heading font-medium",
                  featured && "text-base",
                )}
              >
                {module.label}
              </span>
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
    </a>
  );
}

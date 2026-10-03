"use client";

import {
  Alert02Icon,
  Loading03Icon,
  RefreshIcon,
} from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { DisabledReason } from "@/components/common/disabled-reason";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { Job, Project } from "@/lib/types";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";
import { cn } from "@/lib/utils";

/** The job carries the provider's real failure reason; it is the best message to show. */
function jobErrorMessage(job: Job | null): string | null {
  const message = job?.error?.message;
  return typeof message === "string" && message.trim() ? message : null;
}

const STEP_LABELS: Record<string, string> = {
  queued: "Queued",
  speech_to_text: "Transcribing",
  segmenting: "Segmenting",
  analyzing: "Reviewing",
  ready: "Ready",
  done: "Done",
  failed: "Failed",
};

/** A human state derived from the job/project stage, not the (fabricated) percent. */
function stateLabel(step: string | null | undefined, failed: boolean): string {
  if (failed) return "Failed";
  if (!step) return "Processing";
  return STEP_LABELS[step] ?? "Processing";
}

/** Semantic pill colours: green means done, blue means working, grey means waiting. */
function pillClass(step: string | null | undefined, failed: boolean): string {
  if (failed) {
    return "border-destructive/30 bg-destructive/10 text-destructive [&_.pill-dot]:bg-destructive";
  }
  switch (step) {
    case "ready":
    case "done":
      return "border-sev-good/30 bg-sev-good/10 text-sev-good [&_.pill-dot]:bg-sev-good";
    case "queued":
      return "border-border bg-muted text-muted-foreground [&_.pill-dot]:bg-muted-foreground/60";
    default:
      return "border-sev-low/30 bg-sev-low/10 text-sev-low [&_.pill-dot]:bg-sev-low";
  }
}

export function ProcessingStatusCard({
  project,
  job,
  onRetry,
  retrying = false,
}: {
  project: Project;
  job: Job | null;
  onRetry?: () => void;
  retrying?: boolean;
}) {
  const readOnly = useReadOnly();
  const failed = job?.status === "failed" || project.status === "failed";
  const step = job?.progress.step ?? project.progress?.stage ?? null;
  const label = stateLabel(step, failed);
  // On failure prefer the specific reason (job error, then the project's persisted
  // progress message). Otherwise the job's own message is the live status.
  const message = failed
    ? (jobErrorMessage(job) ??
      project.progress?.message ??
      "Transcription failed.")
    : (job?.progress.message ??
      project.progress?.message ??
      "Queued for transcription");

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <Icon
            icon={failed ? Alert02Icon : Loading03Icon}
            className={cn(
              "size-4",
              failed ? "text-destructive" : "animate-spin text-sev-low",
            )}
          />
          <CardTitle>
            {failed ? "Transcription failed" : "Processing your video"}
          </CardTitle>
          <span
            className={cn(
              "ml-1 inline-flex h-7 items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium",
              pillClass(step, failed),
            )}
          >
            <span
              className={cn(
                "pill-dot size-1.5 rounded-full",
                !failed && "animate-pulse",
              )}
            />
            {label}
          </span>
        </div>
        <CardDescription>
          {failed
            ? "The transcript could not be generated. You can retry without re-uploading."
            : "We are transcribing your video, then the reviewers run over the transcript."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <p
          className={cn(
            "text-sm",
            failed ? "text-destructive" : "text-muted-foreground",
          )}
        >
          {message}
        </p>
        {failed && onRetry ? (
          <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onRetry}
              disabled={retrying || readOnly}
            >
              <Icon
                icon={RefreshIcon}
                className={retrying ? "animate-spin" : undefined}
              />
              {retrying ? "Retrying…" : "Retry transcription"}
            </Button>
          </DisabledReason>
        ) : null}
      </CardContent>
    </Card>
  );
}
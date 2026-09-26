"use client";

import {
  Alert02Icon,
  Loading03Icon,
  RefreshIcon,
} from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { Job, Project } from "@/lib/types";
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
              failed ? "text-destructive" : "animate-spin text-signal",
            )}
          />
          <CardTitle>
            {failed ? "Transcription failed" : "Processing your video"}
          </CardTitle>
          <span
            className={cn(
              "ml-1 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
              failed
                ? "border-destructive/30 bg-destructive/10 text-destructive"
                : "border-signal/30 bg-signal/10 text-signal",
            )}
          >
            <span
              className={cn(
                "size-1.5 rounded-full",
                failed
                  ? "bg-destructive"
                  : "animate-pulse bg-signal",
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
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onRetry}
            disabled={retrying}
          >
            <Icon
              icon={RefreshIcon}
              className={retrying ? "animate-spin" : undefined}
            />
            {retrying ? "Retrying…" : "Retry transcription"}
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}
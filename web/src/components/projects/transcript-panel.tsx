"use client";

import { useState } from "react";
import {
  ClosedCaptionIcon,
  Loading03Icon,
  SparklesIcon,
} from "@hugeicons/core-free-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Icon } from "@/components/common/icon";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useProjectTranscript } from "@/hooks/use-project-transcript";
import { ApiError } from "@/lib/api-client";
import {
  formatTimestamp,
  listTranscriptVersions,
  retranscribeTranscript,
} from "@/lib/projects";
import { WORKSPACE_PANE_SNAP } from "@/lib/workspace";

/*
 * Transcript viewer for the project workspace. Segments are clickable:
 * choosing one seeks the source video through a window event the player
 * listens for, so the panel stays decoupled from the player instance.
 *
 * The card is a fixed-height flex column (like the video and review cards), and
 * only the segment list scrolls — the header stays put.
 */
export function TranscriptPanel({
  projectId,
  processing,
  live = false,
  failureMessage,
}: {
  projectId: string;
  processing: boolean;
  /** Whether the realtime socket is connected; polling is the degraded fallback. */
  live?: boolean;
  failureMessage?: string | null;
}) {
  const [version, setVersion] = useState<number | null>(null);
  // `processing` gates the missing-transcript messaging; polling only happens
  // when push is unavailable (`live` false). See the hook for the full rules.
  const transcriptQuery = useProjectTranscript(projectId, {
    shouldPoll: processing && !live,
    version,
  });
  const queryClient = useQueryClient();

  const versionsQuery = useQuery({
    queryKey: ["transcript-versions", projectId],
    queryFn: () => listTranscriptVersions(projectId),
    retry: false,
  });
  const versions = versionsQuery.data?.items ?? [];
  const latestVersion = versions.length
    ? (versions[versions.length - 1]?.version ?? null)
    : null;

  const rerun = useMutation({
    mutationFn: () => retranscribeTranscript(projectId),
    onSuccess: () => {
      // Follow the new active version once the rerun finishes.
      setVersion(null);
      void queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      void queryClient.invalidateQueries({
        queryKey: ["transcript", projectId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["transcript-versions", projectId],
      });
    },
  });

  function seekTo(startMs: number) {
    window.dispatchEvent(
      new CustomEvent("creator-studio:seek", {
        detail: { projectId, seconds: startMs / 1000 },
      }),
    );
  }

  if (transcriptQuery.isLoading) {
    return (
      <Card className={WORKSPACE_PANE_SNAP}>
        <CardHeader className="shrink-0">
          <div className="flex items-center gap-2">
            <Icon icon={ClosedCaptionIcon} className="text-muted-foreground" />
            <CardTitle>Transcript</CardTitle>
          </div>
          <CardDescription>Loading the transcript…</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-11/12" />
          <Skeleton className="h-4 w-4/5" />
        </CardContent>
      </Card>
    );
  }

  if (transcriptQuery.data) {
    const transcript = transcriptQuery.data;
    const speakerCount = new Set(
      transcript.segments
        .map((segment) => segment.speaker)
        .filter((speaker): speaker is number => speaker != null),
    ).size;
    const showSpeakers = speakerCount > 1;
    const speakerName = (speaker: number) =>
      transcript.speakerLabels?.[String(speaker)] ?? `S${speaker}`;
    return (
      <Card className={WORKSPACE_PANE_SNAP}>
        <CardHeader className="shrink-0">
          <div className="flex flex-wrap items-center gap-2">
            <Icon icon={ClosedCaptionIcon} className="text-muted-foreground" />
            <CardTitle>Transcript</CardTitle>
            <span className="h-4 w-px bg-border" aria-hidden="true" />
            <span className="text-sm text-muted-foreground">
              {transcript.segments.length} segments · {transcript.language}
              {showSpeakers ? ` · ${speakerCount} speakers` : ""}
            </span>
            <div className="ml-auto flex items-center gap-2">
              {versions.length > 0 && (
                <Select
                  value={String(version ?? latestVersion ?? "")}
                  onValueChange={(value) => setVersion(Number(value))}
                >
                  <SelectTrigger size="sm" className="w-20">
                    <SelectValue placeholder="Version">
                      {(value) => (value ? `v${value}` : "Version")}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {versions.map((item) => (
                      <SelectItem
                        key={item.transcriptId}
                        value={String(item.version)}
                      >
                        v{item.version}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => rerun.mutate()}
                disabled={rerun.isPending || processing}
                title={
                  processing ? "Transcription is already running" : undefined
                }
              >
                <Icon icon={SparklesIcon} />
                {rerun.isPending ? "Starting…" : "Run transcript again"}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="scroll-fade-y min-h-0 flex-1 overflow-y-auto py-2 pr-1">
          <ol className="space-y-1">
            {transcript.segments.map((segment) => (
              <li key={segment.segmentId}>
                <button
                  type="button"
                  onClick={() => seekTo(segment.startMs)}
                  className="group flex w-full items-baseline gap-3 rounded-lg px-2 py-1.5 text-left hover:bg-muted"
                >
                  <span className="shrink-0 tabular text-xs text-time underline-offset-2 group-hover:underline">
                    {formatTimestamp(segment.startMs)}
                  </span>
                  {showSpeakers && segment.speaker != null ? (
                    <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                      {speakerName(segment.speaker)}
                    </span>
                  ) : null}
                  <span className="text-sm">{segment.text}</span>
                </button>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
    );
  }

  const notReady =
    transcriptQuery.error instanceof ApiError &&
    transcriptQuery.error.status === 404;

  // A transient/in-flight error while the worker is still running is not a
  // verdict: keep showing the progress state and let the next poll replace it.
  if (transcriptQuery.error && !notReady && !processing) {
    return (
      <Card className={WORKSPACE_PANE_SNAP}>
        <CardHeader className="shrink-0">
          <CardTitle>Transcript unavailable</CardTitle>
          <CardDescription>
            {transcriptQuery.error instanceof Error &&
            transcriptQuery.error.message
              ? transcriptQuery.error.message
              : "The transcript could not be loaded. Refresh to try again."}
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  // The pipeline settled without producing a transcript (failed, or nothing
  // was ever queued). Polling is off, so say so instead of spinning forever.
  if (!processing) {
    return (
      <Card className={WORKSPACE_PANE_SNAP}>
        <CardHeader className="shrink-0">
          <CardTitle>Transcript unavailable</CardTitle>
          <CardDescription>
            {failureMessage ??
              "Transcription did not finish for this video. Retry from the workspace to try again."}
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card className={WORKSPACE_PANE_SNAP}>
      <CardHeader className="shrink-0">
        <div className="flex items-center gap-2">
          <Icon icon={Loading03Icon} className="animate-spin text-signal" />
          <CardTitle>Transcribing…</CardTitle>
        </div>
        <CardDescription>
          Word timestamps land here as soon as speech recognition finishes.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
      </CardContent>
    </Card>
  );
}

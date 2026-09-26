"use client";

import { ClosedCaptionIcon, Loading03Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useProjectTranscript } from "@/hooks/use-project-transcript";
import { ApiError } from "@/lib/api-client";
import { formatTimestamp } from "@/lib/projects";
import { WORKSPACE_PANE_STICKY } from "@/lib/workspace";

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
  failureMessage,
}: {
  projectId: string;
  processing: boolean;
  failureMessage?: string | null;
}) {
  // Polled until the transcript exists; see `hooks/use-project-transcript.ts`
  // for why the rules there are load-bearing. Polling follows `processing` so
  // a failed project stops asking instead of polling forever.
  const transcriptQuery = useProjectTranscript(projectId, { shouldPoll: processing });

  function seekTo(startMs: number) {
    window.dispatchEvent(
      new CustomEvent("creator-studio:seek", {
        detail: { projectId, seconds: startMs / 1000 },
      }),
    );
  }

  if (transcriptQuery.isLoading) {
    return (
      <Card className={WORKSPACE_PANE_STICKY}>
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
    return (
      <Card className={WORKSPACE_PANE_STICKY}>
        <CardHeader className="shrink-0">
          <div className="flex items-center gap-2">
            <Icon icon={ClosedCaptionIcon} className="text-muted-foreground" />
            <CardTitle>Transcript</CardTitle>
          </div>
          <CardDescription>
            {transcript.segments.length} segments ·{" "}
            {formatTimestamp(transcript.durationMs)} · {transcript.language}
          </CardDescription>
        </CardHeader>
        <CardContent className="min-h-0 flex-1 overflow-y-auto pr-1">
          <ol className="space-y-1">
            {transcript.segments.map((segment) => (
              <li key={segment.segmentId}>
                <button
                  type="button"
                  onClick={() => seekTo(segment.startMs)}
                  className="flex w-full items-baseline gap-3 rounded-lg px-2 py-1.5 text-left hover:bg-muted"
                >
                  <span className="shrink-0 tabular text-xs text-signal">
                    {formatTimestamp(segment.startMs)}
                  </span>
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

  if (transcriptQuery.error && !notReady) {
    return (
      <Card className={WORKSPACE_PANE_STICKY}>
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
      <Card className={WORKSPACE_PANE_STICKY}>
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
    <Card className={WORKSPACE_PANE_STICKY}>
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

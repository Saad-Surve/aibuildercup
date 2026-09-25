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

/*
 * Transcript viewer for the project workspace. Segments are clickable:
 * choosing one seeks the source video through a window event the player
 * listens for, so the panel stays decoupled from the player instance.
 */
export function TranscriptPanel({
  projectId,
  processing,
}: {
  projectId: string;
  processing: boolean;
}) {
  // Polled until the transcript exists; see `hooks/use-project-transcript.ts`
  // for why the rules there are load-bearing.
  const transcriptQuery = useProjectTranscript(projectId);

  function seekTo(startMs: number) {
    window.dispatchEvent(
      new CustomEvent("creator-studio:seek", {
        detail: { projectId, seconds: startMs / 1000 },
      }),
    );
  }

  if (transcriptQuery.isLoading) {
    return (
      <Card>
        <CardHeader>
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
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Icon icon={ClosedCaptionIcon} className="text-muted-foreground" />
            <CardTitle>Transcript</CardTitle>
          </div>
          <CardDescription>
            {transcript.segments.length} segments ·{" "}
            {formatTimestamp(transcript.durationMs)} · {transcript.language}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="max-h-96 space-y-1 overflow-y-auto pr-1">
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
      <Card>
        <CardHeader>
          <CardTitle>Transcript unavailable</CardTitle>
          <CardDescription>
            The transcript could not be loaded. Refresh to try again.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Icon icon={Loading03Icon} className="animate-spin text-signal" />
          <CardTitle>{processing ? "Transcribing…" : "Transcript pending"}</CardTitle>
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

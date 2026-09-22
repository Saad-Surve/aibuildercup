"use client";

import { useQuery } from "@tanstack/react-query";
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
import { formatTimestamp, getTranscript } from "@/lib/projects";
import { ApiError } from "@/lib/api-client";

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
  const transcriptQuery = useQuery({
    queryKey: ["transcript", projectId],
    queryFn: () => getTranscript(projectId),
    retry: false,
    refetchInterval: (query) =>
      query.state.data || !processing ? false : 3000,
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
  if (notReady && processing) {
    return (
      <Card>
        <CardHeader>
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

  return null;
}

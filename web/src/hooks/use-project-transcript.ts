"use client";

import { useQuery } from "@tanstack/react-query";

import { getTranscript } from "@/lib/projects";
import type { Transcript } from "@/lib/types";

/**
 * How often to re-ask for a transcript that does not exist yet.
 *
 * Transcription takes minutes, so asking every few seconds is pure load: ten
 * seconds still picks the transcript up promptly while the pipeline runs.
 */
export const TRANSCRIPT_POLL_MS = 10_000;

/**
 * The project's transcript, polled until it exists.
 *
 * The transcript is the one resource that starts out *absent* and appears later:
 * transcription takes tens of seconds, so the first fetch is almost always a
 * 404. Getting this query wrong is easy and has already stuck the UI once, so
 * every rule lives here instead of at the call sites.
 *
 * Rules that must hold:
 *
 *  - **Never stop polling while there is no data *and the pipeline is running*.**
 *    A 404 is the expected answer until the worker finishes; it is not the end
 *    of the story. But once the project settles (ready/failed) with no
 *    transcript coming, polling must stop — otherwise a failed project polls
 *    forever. Callers pass `shouldPoll` from the workspace `processing` flag.
 *  - **Poll while the tab is backgrounded.** Every other query in the workspace
 *    sets `refetchIntervalInBackground`, and TanStack skips an interval tick
 *    entirely when the window is unfocused without it
 *    (`queryObserver.js`: `refetchIntervalInBackground || focusManager.isFocused()`).
 *    Transcription outlasts a tab switch, and the transcript must appear without
 *    the user coming back to force it.
 *  - **`staleTime: 0`.** The app-wide default is 30s, which would let focus and
 *    remount refetches decide a missing transcript is still "fresh". It is not:
 *    until there is data there is nothing to be stale.
 *
 * Both the transcript panel and the review panel consume this hook. They used to
 * declare the query separately with different options, and the two observers
 * disagreed about whether to poll — the one that polled was not the one that
 * won.
 */
export function useProjectTranscript(
  projectId: string,
  options?: { shouldPoll?: boolean; version?: number | null },
) {
  const shouldPoll = options?.shouldPoll ?? true;
  const version = options?.version ?? null;
  return useQuery<Transcript>({
    queryKey: ["transcript", projectId, version ?? "active"],
    queryFn: () => getTranscript(projectId, version),
    retry: false,
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
    refetchIntervalInBackground: true,
    // Only the active transcript is polled; a pinned older version is static.
    refetchInterval: (query) =>
      query.state.data || !shouldPoll || version != null
        ? false
        : TRANSCRIPT_POLL_MS,
  });
}

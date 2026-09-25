"use client";

import { useQuery } from "@tanstack/react-query";

import { getTranscript } from "@/lib/projects";
import type { Transcript } from "@/lib/types";

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
 *  - **Never stop polling while there is no data.** A 404 is the expected answer
 *    until the worker finishes; it is not the end of the story.
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
export function useProjectTranscript(projectId: string) {
  return useQuery<Transcript>({
    queryKey: ["transcript", projectId],
    queryFn: () => getTranscript(projectId),
    retry: false,
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
    refetchIntervalInBackground: true,
    refetchInterval: (query) => (query.state.data ? false : 3000),
  });
}

"use client";

import { useQuery } from "@tanstack/react-query";

import { getTranscript } from "@/lib/projects";
import type { Transcript } from "@/lib/types";

/**
 * Interval for the degraded fallback only.
 *
 * The transcript is normally delivered by the WebSocket: `transcript.ready` (or
 * the project turning `ready`) invalidates this query, so it refetches exactly
 * once when the content appears. This interval is used only when the caller says
 * push is unavailable (socket down) — see `useProjectEvents`.
 */
export const TRANSCRIPT_POLL_MS = 10_000;

/**
 * The project's transcript.
 *
 * The transcript is the one resource that starts out *absent* and appears later:
 * transcription takes tens of seconds, so the first fetch is almost always a
 * 404. Getting this query wrong is easy and has already stuck the UI once, so
 * every rule lives here instead of at the call sites.
 *
 * Rules that must hold:
 *
 *  - **`shouldPoll` means "the socket is down and the pipeline is running".**
 *    With realtime push this is false and the query refetches only when an event
 *    invalidates it (transcript.ready / project ready / transcribe job success).
 *    When true it falls back to a slow interval so a dropped socket cannot leave
 *    the panel empty forever.
 *  - **Poll while the tab is backgrounded.** TanStack skips an interval tick
 *    entirely when the window is unfocused unless `refetchIntervalInBackground`
 *    is set. Transcription outlasts a tab switch, so the fallback must survive
 *    one.
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
  const shouldPoll = options?.shouldPoll ?? false;
  const version = options?.version ?? null;
  return useQuery<Transcript>({
    queryKey: ["transcript", projectId, version ?? "active"],
    queryFn: () => getTranscript(projectId, version),
    retry: false,
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
    refetchIntervalInBackground: true,
    // Only the active transcript polls; a pinned older version is static.
    refetchInterval: (query) =>
      query.state.data || !shouldPoll || version != null
        ? false
        : TRANSCRIPT_POLL_MS,
  });
}

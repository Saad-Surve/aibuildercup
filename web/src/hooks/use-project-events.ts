"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  onRealtimeStatus,
  subscribeProject,
  type RealtimeMessage,
  type RealtimeStatus,
} from "@/lib/realtime";
import type { AnalysisRun, Job, Project } from "@/lib/types";

/*
 * Bridges the project WebSocket onto the React Query cache.
 *
 * This is the only place realtime frames touch query state. Progress frames
 * patch the cached `project`/`job`/`analysis-run` objects in place; completion
 * frames invalidate the resource queries that own the richer payloads
 * (transcript, reviewers, heatmap, findings) so they refetch exactly once, when
 * something actually changed. No component polls.
 *
 * On a reconnect the hook re-invalidates the load-bearing queries: events sent
 * while the socket was down were never delivered, so the caches may be behind.
 */

export function useProjectEvents(
  projectId: string,
  options?: { onJobId?: (jobId: string) => void },
) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<RealtimeStatus>("closed");

  // Keep the latest callback without resubscribing the socket on every render.
  const onJobIdRef = useRef(options?.onJobId);
  useEffect(() => {
    onJobIdRef.current = options?.onJobId;
  }, [options?.onJobId]);

  useEffect(() => onRealtimeStatus(setStatus), []);

  useEffect(() => {
    // A completion often arrives as project.ready, job.succeeded, and
    // transcript.ready together. Coalesce their invalidations into one refetch.
    const pending = new Map<string, readonly unknown[]>();
    let timer: ReturnType<typeof setTimeout> | null = null;
    function invalidate(queryKey: readonly unknown[]) {
      pending.set(JSON.stringify(queryKey), queryKey);
      if (timer) return;
      timer = setTimeout(() => {
        timer = null;
        for (const key of pending.values()) {
          void queryClient.invalidateQueries({ queryKey: key });
        }
        pending.clear();
      }, 200);
    }

    const unsubscribe = subscribeProject(
      projectId,
      (message: RealtimeMessage) => {
        switch (message.type) {
          case "snapshot.project": {
            queryClient.setQueryData<Project>(["project", projectId], (old) =>
              old
                ? {
                    ...old,
                    status: message.status,
                    progress: message.progress ?? old.progress,
                  }
                : old,
            );
            const job = message.job;
            if (job) {
              onJobIdRef.current?.(job.jobId);
              queryClient.setQueryData<Job>(["job", job.jobId], (old) =>
                old
                  ? {
                      ...old,
                      status: job.status,
                      progress: job.progress ?? old.progress,
                      error: job.error,
                    }
                  : old,
              );
            }
            break;
          }
          case "project.progress": {
            queryClient.setQueryData<Project>(["project", projectId], (old) =>
              old
                ? {
                    ...old,
                    status: message.status,
                    progress: message.progress ?? old.progress,
                  }
                : old,
            );
            if (message.status === "ready") {
              invalidate(["transcript", projectId]);
            }
            break;
          }
          case "job.progress": {
            onJobIdRef.current?.(message.jobId);
            queryClient.setQueryData<Job>(["job", message.jobId], (old) =>
              old
                ? {
                    ...old,
                    status: message.status,
                    progress: message.progress ?? old.progress,
                    error: message.error,
                  }
                : old,
            );
            // The transcribe job succeeding means the transcript is stored. The
            // `transcript.ready` frame usually does this too; this covers a frame
            // that was missed while the socket was reconnecting.
            if (
              message.status === "succeeded" &&
              (message.jobType === "transcribe" || message.jobType == null)
            ) {
              invalidate(["transcript", projectId]);
            }
            break;
          }
          case "transcript.ready": {
            invalidate(["transcript", projectId]);
            invalidate(["project", projectId]);
            break;
          }
          case "analysis.progress": {
            queryClient.setQueryData<AnalysisRun>(
              ["analysis-run", projectId, message.analysisRunId],
              (old) =>
                old
                  ? {
                      ...old,
                      status: message.status as AnalysisRun["status"],
                      completedDimensions:
                        message.completedDimensions as AnalysisRun["completedDimensions"],
                    }
                  : old,
            );
            // Reviewer outcomes land one at a time; refetch the projections that
            // show them. These are event-driven only — no interval.
            invalidate([
              "analysis-reviewers",
              projectId,
              message.analysisRunId,
            ]);
            invalidate(["analysis-findings", projectId, message.analysisRunId]);
            invalidate(["analysis-heatmap", projectId, message.analysisRunId]);
            break;
          }
          case "analysis.ready": {
            invalidate(["analysis-runs", projectId]);
            invalidate(["analysis-run", projectId, message.analysisRunId]);
            invalidate([
              "analysis-reviewers",
              projectId,
              message.analysisRunId,
            ]);
            invalidate(["analysis-heatmap", projectId, message.analysisRunId]);
            invalidate(["analysis-findings", projectId, message.analysisRunId]);
            invalidate(["analysis-interest", projectId, message.analysisRunId]);
            break;
          }
          case "error":
          case "ping":
          case "pong":
            break;
        }
      },
    );
    return () => {
      unsubscribe();
      if (timer) clearTimeout(timer);
      // Keep inactive caches stale even if navigation beats the debounce.
      for (const queryKey of pending.values()) {
        void queryClient.invalidateQueries({ queryKey, refetchType: "none" });
      }
    };
  }, [projectId, queryClient]);

  // Skip the very first open (the mount queries are already in flight); from the
  // first *re*connect onward, resync anything that could have changed unnoticed.
  const hasOpenedRef = useRef(false);
  useEffect(() => {
    if (status !== "open") return;
    if (!hasOpenedRef.current) {
      hasOpenedRef.current = true;
      return;
    }
    void queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    void queryClient.invalidateQueries({ queryKey: ["transcript", projectId] });
    void queryClient.invalidateQueries({
      queryKey: ["analysis-runs", projectId],
    });
    void queryClient.invalidateQueries({ queryKey: ["assets", projectId] });
    void queryClient.invalidateQueries({ queryKey: ["revisions", projectId] });
  }, [status, projectId, queryClient]);

  return { status, connected: status === "open" };
}

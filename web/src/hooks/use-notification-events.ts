"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { subscribeOwner } from "@/lib/realtime";
import type {
  AnalysisRun,
  CaptionRender,
  Localization,
  Project,
  ProjectList,
  Publish,
} from "@/lib/types";

/** Patch observed data from owner events; reconcile rich data once on actual completion. */
export function useNotificationEvents(uid: string | null): void {
  const client = useQueryClient();
  useEffect(() => {
    if (!uid) return;
    const unsubscribe = subscribeOwner((event) => {
      if (!("projectId" in event)) return;
      const id = event.projectId;
      const now = new Date().toISOString();
      if (event.type === "project.progress") {
        const patch = (project: Project) => ({
          ...project,
          status: event.status,
          progress: event.progress,
          updatedAt: now,
        });
        client.setQueryData<Project>(["project", id], (old) =>
          old ? patch(old) : old,
        );
        client.setQueryData<ProjectList>(["projects"], (old) =>
          old
            ? {
                ...old,
                items: old.items.map((project) =>
                  project.projectId === id ? patch(project) : project,
                ),
              }
            : old,
        );
      }
      if (event.type === "analysis.ready") {
        client.setQueryData<{ items: AnalysisRun[] }>(
          ["analysis-runs", id],
          (old) =>
            old
              ? {
                  ...old,
                  items: old.items.map((run) =>
                    run.analysisRunId === event.analysisRunId
                      ? {
                          ...run,
                          status: event.status as AnalysisRun["status"],
                          overallScore: event.overallScore,
                          updatedAt: now,
                        }
                      : run,
                  ),
                }
              : old,
        );
      }
      if (
        event.type === "job.progress" &&
        (event.status === "succeeded" || event.status === "failed")
      ) {
        const status =
          event.status === "succeeded"
            ? ("ready" as const)
            : ("failed" as const);
        for (const key of ["caption-renders", "localizations"] as const) {
          client.setQueryData<{ items: (CaptionRender | Localization)[] }>(
            [key, id],
            (old) =>
              old
                ? {
                    ...old,
                    items: old.items.map((item) =>
                      item.jobId === event.jobId
                        ? { ...item, status, updatedAt: now }
                        : item,
                    ),
                  }
                : old,
          );
        }
        client.setQueryData<{ items: Publish[] }>(["publishes", id], (old) =>
          old
            ? {
                ...old,
                items: old.items.map((item) =>
                  item.jobId === event.jobId
                    ? {
                        ...item,
                        status:
                          event.status === "failed"
                            ? ("failed" as const)
                            : item.publishAt &&
                                new Date(item.publishAt).getTime() > Date.now()
                              ? ("processing" as const)
                              : ("published" as const),
                        updatedAt: now,
                      }
                    : item,
                ),
              }
            : old,
        );
        // A metadata-only patch is enough for a notice. Rich URLs/output fields
        // still reconcile on the next view (or immediately for active observers).
        for (const key of ["caption-renders", "localizations", "publishes"]) {
          const cached = client.getQueryData<{
            items: { jobId: string | null }[];
          }>([key, id]);
          if (cached?.items.some((item) => item.jobId === event.jobId)) {
            void client.invalidateQueries({ queryKey: [key, id] });
          }
        }
      }
    });
    return unsubscribe;
  }, [client, uid]);
}

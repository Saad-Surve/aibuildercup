"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft01Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { DeleteProjectDialog } from "@/components/projects/delete-project-dialog";
import { DraftWorkspace } from "@/components/projects/draft/draft-workspace";
import { EditProjectDialog } from "@/components/projects/edit-project-dialog";
import { ProjectStatusBadge } from "@/components/projects/project-status-badge";
import { VideoStudio } from "@/components/projects/video-studio";
import { Skeleton } from "@/components/ui/skeleton";
import { useProjectEvents } from "@/hooks/use-project-events";
import { getJob, getProject } from "@/lib/projects";
import type { Job } from "@/lib/types";

/**
 * Project router. Fetches the project, drives the realtime socket, and hands off
 * to the video studio or the draft studio — the two have entirely different
 * shapes, so they live in their own components.
 */
export function ProjectWorkspace({
  projectId,
  moduleId,
}: {
  projectId: string;
  moduleId: string;
}) {
  const [jobId, setJobId] = useState<string | null>(null);

  // One realtime socket drives the whole workspace. `connected` gates the slow
  // polling fallback used only if the socket cannot be established.
  const { connected } = useProjectEvents(projectId, { onJobId: setJobId });

  const projectQuery = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      const running = status === "processing" || status === "uploading";
      return running && !connected ? 8000 : false;
    },
    refetchIntervalInBackground: true,
  });

  const jobQuery = useQuery<Job>({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      const running = status === "queued" || status === "running";
      return running && !connected ? 8000 : false;
    },
    refetchIntervalInBackground: true,
  });

  if (projectQuery.isLoading) {
    return (
      <div className="w-full space-y-6">
        <Skeleton className="h-5 w-24" />
        <div className="space-y-3">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-4 w-80" />
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:items-start">
          <Skeleton className="h-[min(60vh,40rem)] w-full" />
          <Skeleton className="h-[min(60vh,40rem)] w-full" />
        </div>
      </div>
    );
  }

  // Only a *missing* project is "not found". A transient refetch error keeps the
  // last good project data (React Query preserves it), so it must NOT flash the
  // not-found screen while the pipeline is still polling.
  if (!projectQuery.data) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <h1 className="font-heading text-xl font-semibold tracking-tight">
          Project not found
        </h1>
        <p className="text-sm text-muted-foreground">
          This project does not exist or you do not have access to it.
        </p>
        <Link
          href="/projects"
          className="inline-flex items-center gap-1.5 text-sm text-signal hover:underline"
        >
          <Icon icon={ArrowLeft01Icon} />
          Back to projects
        </Link>
      </div>
    );
  }

  const project = projectQuery.data;

  return (
    <div className="w-full space-y-6">
      <div className="space-y-6 lg:snap-start lg:snap-always lg:scroll-mt-20">
        <Link
          href="/projects"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <Icon icon={ArrowLeft01Icon} />
          Projects
        </Link>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0 space-y-1">
            <div className="flex items-center gap-1">
              <h1 className="font-heading text-xl font-semibold tracking-tight break-words">
                {project.name}
              </h1>
              <EditProjectDialog
                projectId={projectId}
                initialName={project.name}
                initialDescription={project.description}
                initialThumbnailConcept={project.thumbnailConcept}
                iconOnly
              />
            </div>
            {project.description ? (
              <p className="max-w-[65ch] text-sm text-muted-foreground break-words">
                {project.description}
              </p>
            ) : null}
          </div>

          {project.kind === "draft" ? (
            <div className="flex flex-wrap items-center gap-2">
              <ProjectStatusBadge status={project.status} />
              <DeleteProjectDialog
                projectId={projectId}
                projectName={project.name}
                assetIds={project.sourceAssetId ? [project.sourceAssetId] : []}
              />
            </div>
          ) : null}
        </div>
      </div>

      {project.kind === "draft" ? (
        <DraftWorkspace project={project} />
      ) : (
        <VideoStudio
          project={project}
          moduleId={moduleId}
          connected={connected}
          job={jobQuery.data ?? null}
          onJobId={setJobId}
        />
      )}
    </div>
  );
}

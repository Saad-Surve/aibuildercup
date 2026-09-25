"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft01Icon, FileVideoIcon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { PageHeader } from "@/components/common/page-header";
import { DeleteProjectDialog } from "@/components/projects/delete-project-dialog";
import { ProcessingStatusCard } from "@/components/projects/processing-status-card";
import { ProjectStatusBadge } from "@/components/projects/project-status-badge";
import { ReviewPanel } from "@/components/projects/review-panel";
import { SourceVideoPlayer } from "@/components/projects/source-video-player";
import { TranscriptPanel } from "@/components/projects/transcript-panel";
import { VideoDropzone } from "@/components/projects/video-dropzone";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getVideoBlobForProject } from "@/lib/local-media";
import {
  formatBytes,
  getJob,
  getProject,
  listAssets,
  subscribeToProjectEvents,
} from "@/lib/projects";
import type { Asset, Job, Project } from "@/lib/types";

export function ProjectWorkspace({ projectId }: { projectId: string }) {
  const [jobId, setJobId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const projectQuery = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId),
    // Keep the status fresh while the pipeline runs so the workspace flips to
    // ready even after a reload (when no job id is in memory to poll).
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "processing" || status === "uploading" ? 3000 : false;
    },
    refetchIntervalInBackground: true,
  });

  const assetsQuery = useQuery({
    queryKey: ["assets", projectId],
    queryFn: () => listAssets(projectId),
  });

  const jobQuery = useQuery<Job>({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 3000 : false;
    },
    refetchIntervalInBackground: true,
  });

  // When transcription finishes, refresh the project (status flips to ready)
  // and let the transcript panel pick up the new segments.
  const jobStatus = jobQuery.data?.status;
  useEffect(() => {
    if (jobStatus !== "succeeded") return;
    void queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    void queryClient.invalidateQueries({ queryKey: ["transcript", projectId] });
  }, [jobStatus, projectId, queryClient]);

  // The transcript panel's own polling pauses while the tab is unfocused, so when the
  // project turns "ready" (noticed by the background project poll) fetch the transcript
  // here. This is what makes the content appear without a reload or refocus.
  const projectStatus = projectQuery.data?.status;
  useEffect(() => {
    if (projectStatus !== "ready") return;
    void queryClient.invalidateQueries({ queryKey: ["transcript", projectId] });
  }, [projectStatus, projectId, queryClient]);

  // Live progress via the SSE stream. Event-driven cache updates make the
  // workspace flip the moment the backend state changes; the polling queries
  // above stay as a fallback if the stream drops or the user is signed out.
  useEffect(() => {
    if (projectStatus !== "processing" && projectStatus !== "uploading") return;
    return subscribeToProjectEvents(projectId, (event) => {
      queryClient.setQueryData<Project>(["project", projectId], (old) =>
        old ? { ...old, status: event.status, progress: event.progress } : old,
      );
      if (event.job) {
        const jobSnapshot = event.job;
        setJobId((previous) => previous ?? jobSnapshot.jobId);
        queryClient.setQueryData<Job>(["job", jobSnapshot.jobId], (old) =>
          old
            ? {
                ...old,
                status: jobSnapshot.status,
                progress: jobSnapshot.progress,
              }
            : old,
        );
      }
    });
  }, [projectStatus, projectId, queryClient]);

  // When the API lists no assets but this browser still holds the upload,
  // play the local copy instead of asking for another upload. Hooks stay
  // above the early returns.
  const [localAsset, setLocalAsset] = useState<Asset | null>(null);
  const assetsLoading = assetsQuery.isLoading;
  const assetsData = assetsQuery.data;
  useEffect(() => {
    const source = assetsData?.items.find(
      (asset) => asset.type === "source_video",
    );
    if (assetsLoading || source) return;
    let alive = true;
    void getVideoBlobForProject(projectId).then((blob) => {
      if (!alive || !blob) return;
      const timestamp = new Date().toISOString();
      setLocalAsset((previous) => {
        if (previous) return previous;
        return {
          assetId: `local:${projectId}`,
          projectId,
          type: "source_video",
          status: "uploaded",
          storagePath: "Cached in this browser",
          mimeType: blob.type || "video/mp4",
          sizeBytes: blob.size,
          durationMs: null,
          createdAt: timestamp,
          updatedAt: timestamp,
        };
      });
    });
    return () => {
      alive = false;
    };
  }, [assetsLoading, assetsData, projectId]);

  if (projectQuery.isLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-6">
        <Skeleton className="h-8 w-56" />
        <Skeleton className="h-40 w-full" />
      </div>
    );
  }

  if (projectQuery.isError || !projectQuery.data) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <PageHeader title="Project not found" />
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
  const sourceAsset = assetsData?.items.find(
    (asset) => asset.type === "source_video",
  );

  const effectiveSource = sourceAsset ?? localAsset;
  const processing =
    project.status === "processing" ||
    jobQuery.data?.status === "queued" ||
    jobQuery.data?.status === "running";

  // Same seek channel the transcript panel uses: the player listens for it.
  function seekTo(startMs: number) {
    window.dispatchEvent(
      new CustomEvent("creator-studio:seek", {
        detail: { projectId, seconds: startMs / 1000 },
      }),
    );
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Link
        href="/projects"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <Icon icon={ArrowLeft01Icon} />
        Projects
      </Link>

      <PageHeader
        title={project.name}
        description={project.description || undefined}
        actions={
          <>
            <ProjectStatusBadge status={project.status} />
            <DeleteProjectDialog
              projectId={projectId}
              projectName={project.name}
              assetIds={effectiveSource ? [effectiveSource.assetId] : []}
            />
          </>
        }
      />

      {effectiveSource ? (
        <div className="space-y-6">
          {(processing || project.status === "failed") && (
            <ProcessingStatusCard project={project} job={jobQuery.data ?? null} />
          )}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Icon icon={FileVideoIcon} className="text-muted-foreground" />
                <CardTitle>Source video</CardTitle>
              </div>
              <CardDescription>
                {formatBytes(effectiveSource.sizeBytes)} ·{" "}
                {effectiveSource.mimeType}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <SourceVideoPlayer
                projectId={projectId}
                asset={effectiveSource}
              />
              <p className="tabular truncate text-xs text-muted-foreground">
                {formatBytes(effectiveSource.sizeBytes)} ·{" "}
                {effectiveSource.mimeType} · {effectiveSource.storagePath}
              </p>
            </CardContent>
          </Card>
          <ReviewPanel
            projectId={projectId}
            platform={project.targetPlatforms[0] ?? "youtube"}
            onSeek={seekTo}
          />
          <TranscriptPanel projectId={projectId} processing={processing} />
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Upload your video</CardTitle>
            <CardDescription>
              The transcript and reviewer heatmap are built from this file.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <VideoDropzone projectId={projectId} onQueued={setJobId} />
          </CardContent>
        </Card>
      )}
    </div>
  );
}

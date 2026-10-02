"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft01Icon, FileVideoIcon } from "@hugeicons/core-free-icons";
import { format } from "date-fns";

import { Icon } from "@/components/common/icon";
import { PageHeader } from "@/components/common/page-header";
import { DeleteProjectDialog } from "@/components/projects/delete-project-dialog";
import { EditProjectDialog } from "@/components/projects/edit-project-dialog";
import { ProcessingStatusCard } from "@/components/projects/processing-status-card";
import { ProjectStatusBadge } from "@/components/projects/project-status-badge";
import { ReviewPanel } from "@/components/projects/review-panel";
import { SourceVideoPlayer } from "@/components/projects/source-video-player";
import { TranscriptPanel } from "@/components/projects/transcript-panel";
import { VideoDropzone } from "@/components/projects/video-dropzone";
import { VideoRevisions } from "@/components/projects/video-revisions";
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
  completeUpload,
  formatBytes,
  formatTimestamp,
  getJob,
  getProject,
  listAssets,
  pickSourceAsset,
} from "@/lib/projects";
import { useProjectEvents } from "@/hooks/use-project-events";
import type { Asset, Job } from "@/lib/types";
import {
  WORKSPACE_PANE_CARD,
  WORKSPACE_PANE_STACK_SPACER,
} from "@/lib/workspace";

export function ProjectWorkspace({ projectId }: { projectId: string }) {
  const [jobId, setJobId] = useState<string | null>(null);
  const [durationMs, setDurationMs] = useState<number | null>(null);
  const queryClient = useQueryClient();

  // One realtime socket drives the whole workspace: project status, job
  // progress, transcript arrival, and analysis reviewers. `connected` gates the
  // slow polling fallback used only if the socket cannot be established.
  const { connected } = useProjectEvents(projectId, { onJobId: setJobId });

  const projectQuery = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId),
    // Realtime patches the cache; this interval is the degraded fallback, only
    // while the pipeline runs and the socket is down.
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      const running = status === "processing" || status === "uploading";
      return running && !connected ? 8000 : false;
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
      const running = status === "queued" || status === "running";
      return running && !connected ? 8000 : false;
    },
    refetchIntervalInBackground: true,
  });

  // The job/transcript/project invalidations that used to live here are now
  // emitted by the realtime hook: `transcript.ready`, a transcribe job
  // succeeding, and the project turning `ready` all invalidate the transcript
  // query, so it refetches exactly once when the content appears.

  // When the API lists no assets but this browser still holds the upload,
  // play the local copy instead of asking for another upload. Hooks stay
  // above the early returns.
  const [localAsset, setLocalAsset] = useState<Asset | null>(null);
  const assetsLoading = assetsQuery.isLoading;
  const assetsData = assetsQuery.data;
  const sourceAsset = pickSourceAsset(
    assetsData?.items,
    projectQuery.data?.sourceAssetId,
  );

  // Retry a failed transcription. `POST /assets/{id}/complete` reuses the existing job
  // and the backend requeues it, so no re-upload is needed; the same job id is then
  // polled and the project flips back to `processing`.
  const retryTranscription = useMutation({
    mutationFn: () => {
      if (!sourceAsset) throw new Error("No source video to retry.");
      return completeUpload(projectId, sourceAsset.assetId);
    },
    onSuccess: (accepted) => {
      setJobId(accepted.jobId);
      void queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["job", accepted.jobId] });
      void queryClient.invalidateQueries({
        queryKey: ["transcript", projectId],
      });
    },
  });

  useEffect(() => {
    const source = pickSourceAsset(
      assetsData?.items,
      projectQuery.data?.sourceAssetId,
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
          revision: null,
          createdAt: timestamp,
          updatedAt: timestamp,
        };
      });
    });
    return () => {
      alive = false;
    };
  }, [assetsLoading, assetsData, projectId, projectQuery.data?.sourceAssetId]);

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
          <div className="space-y-10">
            <Skeleton className="h-[min(60vh,40rem)] w-full" />
            <Skeleton className="h-[min(60vh,40rem)] w-full" />
          </div>
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

  const effectiveSource = sourceAsset ?? localAsset;
  const displayRevision =
    project.sourceRevision ?? sourceAsset?.revision ?? null;
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
    <div className="w-full space-y-6">
      {/*
       * The top snap stop includes the back link and the header, so mandatory
       * snapping can rest here instead of skipping past "< Projects".
       */}
      <div className="space-y-6 lg:snap-start lg:snap-always lg:scroll-mt-20">
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
              <EditProjectDialog
                projectId={projectId}
                initialName={project.name}
                initialDescription={project.description}
                initialThumbnailConcept={project.thumbnailConcept}
              />
              <DeleteProjectDialog
                projectId={projectId}
                projectName={project.name}
                assetIds={effectiveSource ? [effectiveSource.assetId] : []}
              />
            </>
          }
        />
      </div>

      {effectiveSource ? (
        <div className="space-y-6">
          {(processing || project.status === "failed") && (
            <ProcessingStatusCard
              project={project}
              job={jobQuery.data ?? null}
              onRetry={
                sourceAsset ? () => retryTranscription.mutate() : undefined
              }
              retrying={retryTranscription.isPending}
            />
          )}

          {/*
           * Two panes: the source video stays pinned on the left while the right
           * column stacks the transcript, the reviewer heatmap, and the findings.
           * At `lg` every card shares one fixed height and scrolls its own body,
           * so the page never grows or reflows as transcript and findings
           * arrive; on phones the cards grow with their content up to the same
           * cap, which avoids four nested scrollers.
           */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 lg:items-start">
            <div className="lg:sticky lg:top-20">
              <Card className={WORKSPACE_PANE_CARD}>
                <CardHeader className="shrink-0">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Icon
                        icon={FileVideoIcon}
                        className="text-muted-foreground"
                      />
                      <CardTitle>Source video</CardTitle>
                    </div>
                    {sourceAsset && (
                      <VideoRevisions
                        projectId={projectId}
                        activeRevision={project.sourceRevision}
                        revisionCount={project.revisionCount}
                        onQueued={setJobId}
                      />
                    )}
                  </div>
                  <CardDescription>
                    {displayRevision != null
                      ? `Revision ${displayRevision} · ${effectiveSource.mimeType}`
                      : effectiveSource.mimeType}
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex min-h-0 flex-1 flex-col">
                  <div className="flex min-h-0 flex-1 items-center [&>*]:w-full">
                    <SourceVideoPlayer
                      projectId={projectId}
                      asset={effectiveSource}
                      onDuration={setDurationMs}
                    />
                  </div>
                  <dl className="mt-3 grid shrink-0 grid-cols-3 gap-2 text-xs">
                    <div>
                      <dt className="text-muted-foreground/70">Duration</dt>
                      <dd className="tabular text-foreground">
                        {(durationMs ?? effectiveSource.durationMs) != null
                          ? formatTimestamp(
                              durationMs ?? effectiveSource.durationMs ?? 0,
                            )
                          : "—"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground/70">Size</dt>
                      <dd className="tabular text-foreground">
                        {formatBytes(effectiveSource.sizeBytes)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground/70">Uploaded</dt>
                      <dd className="text-foreground">
                        {format(
                          new Date(effectiveSource.createdAt),
                          "d MMM yyyy",
                        )}
                      </dd>
                    </div>
                  </dl>
                </CardContent>
              </Card>
            </div>

            <div className="space-y-10">
              <TranscriptPanel
                projectId={projectId}
                projectName={project.name}
                processing={processing}
                live={connected}
                failureMessage={
                  project.status === "failed"
                    ? (project.progress?.message ?? null)
                    : null
                }
              />
              <ReviewPanel
                projectId={projectId}
                platform={project.targetPlatforms[0] ?? "youtube"}
                onSeek={seekTo}
                live={connected}
                transcriptShouldPoll={processing && !connected}
              />
              {/*
               * Room below the last pane so it can snap level with the video card;
               * the panes are the same height as the video column, so without it
               * the last one can never reach the top.
               */}
              <div aria-hidden className={WORKSPACE_PANE_STACK_SPACER} />
            </div>
          </div>
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

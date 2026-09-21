"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft01Icon, FileVideoIcon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { PageHeader } from "@/components/common/page-header";
import { DeleteProjectDialog } from "@/components/projects/delete-project-dialog";
import { ProcessingStatusCard } from "@/components/projects/processing-status-card";
import { ProjectStatusBadge } from "@/components/projects/project-status-badge";
import { SourceVideoPlayer } from "@/components/projects/source-video-player";
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
import { formatBytes, getJob, getProject, listAssets } from "@/lib/projects";
import type { Asset, Job } from "@/lib/types";

export function ProjectWorkspace({ projectId }: { projectId: string }) {
  const [jobId, setJobId] = useState<string | null>(null);

  const projectQuery = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId),
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
  });

  // When the API lists no assets (e.g. a mock-mode reload dropped them) but
  // this browser still holds the upload, play the local copy instead of
  // asking for another upload. Hooks stay above the early returns.
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
          <ProcessingStatusCard project={project} job={jobQuery.data ?? null} />
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

"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileVideoIcon } from "@hugeicons/core-free-icons";
import { format } from "date-fns";

import { Icon } from "@/components/common/icon";
import { ProcessingStatusCard } from "@/components/projects/processing-status-card";
import { ReviewPanel } from "@/components/projects/review-panel";
import { SourceVideoPlayer } from "@/components/projects/source-video-player";
import { TranscriptPanel } from "@/components/projects/transcript-panel";
import { VideoDropzone } from "@/components/projects/video-dropzone";
import { VideoRevisions } from "@/components/projects/video-revisions";
import { CaptionsModule } from "@/components/projects/studio/captions-module";
import { LocalizationModule } from "@/components/projects/studio/localization-module";
import { ModuleGrid } from "@/components/projects/studio/module-grid";
import { ModuleNav } from "@/components/projects/studio/module-nav";
import { PackagingModule } from "@/components/projects/studio/packaging-module";
import { TranscriptGate } from "@/components/projects/studio/transcript-gate";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useProjectTranscript } from "@/hooks/use-project-transcript";
import { getVideoBlobForProject } from "@/lib/local-media";
import {
  completeUpload,
  formatBytes,
  formatTimestamp,
  listAssets,
  pickSourceAsset,
  retranscribeTranscript,
} from "@/lib/projects";
import { type StudioModuleId, moduleById } from "@/lib/studio";
import type { Asset, Job, Project } from "@/lib/types";
import {
  WORKSPACE_PANE_CARD,
  WORKSPACE_PANE_STACK_SPACER,
} from "@/lib/workspace";

const MODULE_IDS = new Set<StudioModuleId>([
  "overview",
  "transcript",
  "review",
  "captions",
  "packaging",
  "localization",
]);

/**
 * The video studio: the source video stays pinned on the left while the right
 * pane swaps between the overview grid and a focused module. Reachable modules
 * that need a transcript gate themselves behind {@link TranscriptGate}.
 */
export function VideoStudio({
  project,
  connected,
  job,
  onJobId,
}: {
  project: Project;
  connected: boolean;
  job: Job | null;
  onJobId: (jobId: string) => void;
}) {
  const projectId = project.projectId;
  const searchParams = useSearchParams();
  const rawModule = searchParams.get("module");
  const activeModule: StudioModuleId =
    rawModule && MODULE_IDS.has(rawModule as StudioModuleId)
      ? (rawModule as StudioModuleId)
      : "overview";

  const queryClient = useQueryClient();
  const [durationMs, setDurationMs] = useState<number | null>(null);

  const assetsQuery = useQuery({
    queryKey: ["assets", projectId],
    queryFn: () => listAssets(projectId),
  });

  const transcriptQuery = useProjectTranscript(projectId, {
    shouldPoll:
      (project.status === "processing" || project.status === "uploading") &&
      !connected,
  });

  const assetsLoading = assetsQuery.isLoading;
  const assetsData = assetsQuery.data;
  const sourceAsset = pickSourceAsset(assetsData?.items, project.sourceAssetId);

  const retryTranscription = useMutation({
    mutationFn: () => {
      if (!sourceAsset) throw new Error("No source video to retry.");
      return completeUpload(projectId, sourceAsset.assetId);
    },
    onSuccess: (accepted) => {
      onJobId(accepted.jobId);
      void queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["job", accepted.jobId] });
      void queryClient.invalidateQueries({
        queryKey: ["transcript", projectId],
      });
    },
  });

  const generateTranscript = useMutation({
    mutationFn: () => retranscribeTranscript(projectId),
    onSuccess: (accepted) => {
      onJobId(accepted.jobId);
      void queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      void queryClient.invalidateQueries({
        queryKey: ["transcript", projectId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["transcript-versions", projectId],
      });
    },
  });

  // When the API lists no assets but this browser still holds the upload,
  // play the local copy instead of asking for another upload.
  const [localAsset, setLocalAsset] = useState<Asset | null>(null);
  useEffect(() => {
    const source = pickSourceAsset(assetsData?.items, project.sourceAssetId);
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
  }, [assetsLoading, assetsData, projectId, project.sourceAssetId]);

  const effectiveSource = sourceAsset ?? localAsset;
  const displayRevision =
    project.sourceRevision ?? sourceAsset?.revision ?? null;
  const processing =
    project.status === "processing" ||
    project.status === "uploading" ||
    generateTranscript.isPending;
  const hasTranscript = Boolean(transcriptQuery.data);

  function seekTo(startMs: number) {
    window.dispatchEvent(
      new CustomEvent("creator-studio:seek", {
        detail: { projectId, seconds: startMs / 1000 },
      }),
    );
  }

  if (!effectiveSource) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Upload your video</CardTitle>
          <CardDescription>
            The transcript and reviewer heatmap are built from this file.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <VideoDropzone projectId={projectId} onQueued={onJobId} />
        </CardContent>
      </Card>
    );
  }

  const activeModuleInfo = moduleById(activeModule);

  function renderModule() {
    if (activeModule === "overview") {
      return (
        <ModuleGrid
          projectId={projectId}
          hasVideo={Boolean(effectiveSource)}
          hasTranscript={hasTranscript}
        />
      );
    }
    if (!activeModuleInfo) return null;
    if (activeModuleInfo.needsTranscript && !hasTranscript) {
      return (
        <TranscriptGate
          module={activeModuleInfo}
          hasVideo={Boolean(effectiveSource)}
          processing={processing}
          generating={generateTranscript.isPending}
          failureMessage={
            project.status === "failed"
              ? (project.progress?.message ?? null)
              : null
          }
          onGenerate={() => generateTranscript.mutate()}
        />
      );
    }
    switch (activeModule) {
      case "transcript":
        return (
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
        );
      case "review":
        return (
          <ReviewPanel
            projectId={projectId}
            platform={project.targetPlatforms[0] ?? "youtube"}
            onSeek={seekTo}
            live={connected}
            transcriptShouldPoll={processing && !connected}
          />
        );
      case "captions":
        return (
          <CaptionsModule projectId={projectId} projectName={project.name} />
        );
      case "packaging":
        return <PackagingModule />;
      case "localization":
        return (
          <LocalizationModule
            primaryLanguage={project.primaryLanguage}
            targetLanguages={project.targetLanguages}
          />
        );
      default:
        return null;
    }
  }

  return (
    <div className="space-y-6">
      {(processing || project.status === "failed") && (
        <ProcessingStatusCard
          project={project}
          job={job}
          onRetry={sourceAsset ? () => retryTranscription.mutate() : undefined}
          retrying={retryTranscription.isPending}
        />
      )}

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
                    onQueued={onJobId}
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
                    {format(new Date(effectiveSource.createdAt), "d MMM yyyy")}
                  </dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <ModuleNav projectId={projectId} active={activeModule} />
          {renderModule()}
          <div aria-hidden className={WORKSPACE_PANE_STACK_SPACER} />
        </div>
      </div>
    </div>
  );
}

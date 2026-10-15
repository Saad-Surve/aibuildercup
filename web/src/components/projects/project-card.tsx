"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useQueryClient } from "@tanstack/react-query";
import { FileVideoIcon, PencilEdit02Icon } from "@hugeicons/core-free-icons";
import { format } from "date-fns";

import { Icon } from "@/components/common/icon";
import { ProjectStatusBadge } from "@/components/projects/project-status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getCachedPosterForProject } from "@/lib/local-media";
import { formatBytes, formatTimestamp } from "@/lib/projects";
import { workspaceHref } from "@/lib/studio";
import type { Project } from "@/lib/types";
import { prefetchProject } from "@/lib/project-prefetch";

/*
 * Card thumbnail: the poster frame captured from the project's uploaded
 * source video (cached in localStorage at upload/play time). Falls back to
 * the project-level cache when the API does not list the asset, then to the
 * film placeholder.
 */
function ProjectThumb({
  projectId,
  activeAssetId,
  posterUrl,
}: {
  projectId: string;
  activeAssetId: string | null;
  /** Applied thumbnail cover; takes precedence over the captured frame poster. */
  posterUrl: string | null;
}) {
  const [poster, setPoster] = useState<string | null>(null);
  useEffect(() => {
    // Read only the local frame cache; cards must never download/decode a video.
    if (!activeAssetId) return;
    const timer = window.setTimeout(
      () => setPoster(getCachedPosterForProject(projectId)),
      0,
    );
    return () => window.clearTimeout(timer);
  }, [projectId, activeAssetId]);

  const cover = posterUrl ?? poster;
  if (cover) {
    // Static export disables image transformation; retain data/signed URLs while
    // getting explicit dimensions, async decoding, and native lazy loading.
    return (
      <Image
        src={cover}
        width={480}
        height={270}
        alt=""
        aria-hidden="true"
        className="aspect-video w-full object-cover"
      />
    );
  }
  return (
    <div className="flex aspect-video w-full items-center justify-center bg-muted">
      <Icon icon={FileVideoIcon} className="size-6 text-muted-foreground" />
    </div>
  );
}

/** A paper-like preview of a draft's first lines, instead of a video poster. */
function DraftPreview({ project }: { project: Project }) {
  const summary = project.draftSummary;
  const preview = summary?.preview?.trim();
  return (
    <div className="relative flex aspect-video w-full flex-col gap-2 overflow-hidden bg-muted/40 p-4">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-[0.4] [background-image:repeating-linear-gradient(to_bottom,transparent,transparent_1.55rem,color-mix(in_oklch,var(--border),transparent_40%)_1.6rem)]"
      />
      <span className="relative inline-flex w-fit items-center gap-1 rounded-md bg-background/80 px-2 py-0.5 text-xs text-muted-foreground ring-1 ring-foreground/10">
        <Icon icon={PencilEdit02Icon} className="size-3.5" />
        {project.draftFormat === "script" ? "Video script" : "Written content"}
      </span>
      <p className="relative line-clamp-4 text-sm text-foreground/80">
        {preview || summary?.title || project.description || "Empty draft"}
      </p>
    </div>
  );
}

/*
 * Loading placeholder that mirrors the real card layout (16:9 thumb, title
 * row with status, description lines, and metadata grid) so the grid doesn't jump.
 */
export function ProjectCardSkeleton() {
  return (
    <Card aria-hidden="true" className="h-full">
      <div className="-mt-(--card-spacing)">
        <Skeleton className="aspect-video w-full rounded-none" />
      </div>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <Skeleton className="mt-1 h-5 w-2/3" />
          <Skeleton className="h-5 w-16 rounded-full" />
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <div className="mt-3 grid grid-cols-3 gap-2">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-8 w-full" />
        </div>
      </CardContent>
    </Card>
  );
}

export function ProjectCard({ project }: { project: Project }) {
  const isDraft = project.kind === "draft";
  const client = useQueryClient();
  const source = project.sourceSummary;
  const prefetch = () => prefetchProject(client, project);

  return (
    <Link
      href={workspaceHref(project.projectId)}
      onMouseEnter={prefetch}
      onFocus={prefetch}
      className="group block rounded-lg focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <Card className="h-full transition-shadow group-hover:shadow-md group-hover:ring-foreground/20">
        <div className="-mt-(--card-spacing) overflow-hidden rounded-t-lg">
          {isDraft ? (
            <DraftPreview project={project} />
          ) : (
            <ProjectThumb
              projectId={project.projectId}
              activeAssetId={project.sourceAssetId}
              posterUrl={project.posterUrl}
            />
          )}
        </div>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <CardTitle className="mt-1 line-clamp-1">{project.name}</CardTitle>
            <ProjectStatusBadge status={project.status} />
          </div>
        </CardHeader>
        <CardContent>
          <p className="line-clamp-2 min-h-10 text-sm text-muted-foreground">
            {project.description || "No description."}
          </p>
          {isDraft ? (
            <dl className="mt-3 grid grid-cols-3 gap-2 text-xs">
              <div>
                <dt className="text-muted-foreground/70">Words</dt>
                <dd className="tabular text-foreground">
                  {project.draftSummary?.wordCount ?? 0}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground/70">Blocks</dt>
                <dd className="tabular text-foreground">
                  {project.draftSummary?.blockCount ?? 0}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground/70">Updated</dt>
                <dd className="text-foreground">
                  {format(new Date(project.updatedAt), "d MMM yyyy")}
                </dd>
              </div>
            </dl>
          ) : (
            <dl className="mt-3 grid grid-cols-3 gap-2 text-xs">
              <div>
                <dt className="text-muted-foreground/70">Duration</dt>
                <dd className="tabular text-foreground">
                  {source?.durationMs != null
                    ? formatTimestamp(source.durationMs)
                    : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground/70">Size</dt>
                <dd className="tabular text-foreground">
                  {source ? formatBytes(source.sizeBytes) : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-muted-foreground/70">Uploaded</dt>
                <dd className="text-foreground">
                  {format(
                    new Date(source?.createdAt ?? project.createdAt),
                    "d MMM yyyy",
                  )}
                </dd>
              </div>
            </dl>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}

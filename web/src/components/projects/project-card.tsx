"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Film01Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { ProjectStatusBadge } from "@/components/projects/project-status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ensurePoster, ensureProjectPoster } from "@/lib/local-media";
import { listAssets } from "@/lib/projects";
import type { Project } from "@/lib/types";

/*
 * Card thumbnail: the poster frame captured from the project's uploaded
 * source video (cached in localStorage at upload/play time). Falls back to
 * the project-level cache when the API no longer lists the asset (e.g. a
 * mock-mode reload), then to the film placeholder.
 */
function ProjectThumb({ projectId }: { projectId: string }) {
  const assetsQuery = useQuery({
    queryKey: ["assets", projectId],
    queryFn: () => listAssets(projectId),
    staleTime: 60_000,
  });
  const [poster, setPoster] = useState<string | null>(null);

  useEffect(() => {
    if (assetsQuery.isLoading || assetsQuery.isError || poster) return;
    const source = assetsQuery.data?.items.find(
      (asset) => asset.type === "source_video",
    );
    let alive = true;
    void (async () => {
      const url = source
        ? await ensurePoster({
            projectId,
            assetId: source.assetId,
            sizeBytes: source.sizeBytes,
          })
        : await ensureProjectPoster(projectId);
      if (alive && url) setPoster(url);
    })();
    return () => {
      alive = false;
    };
  }, [
    assetsQuery.isLoading,
    assetsQuery.isError,
    assetsQuery.data,
    poster,
    projectId,
  ]);

  if (poster) {
    // Plain <img> on purpose: posters are generated data URLs, nothing to optimize.
    return (
      <img
        src={poster}
        alt=""
        aria-hidden="true"
        className="aspect-video w-full object-cover"
      />
    );
  }
  return (
    <div className="flex aspect-video w-full items-center justify-center bg-muted">
      <Icon icon={Film01Icon} className="size-6 text-muted-foreground" />
    </div>
  );
}

/*
 * Loading placeholder that mirrors the real card layout (16:9 thumb, title
 * row with status, two description lines) so the grid doesn't jump.
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
      </CardContent>
    </Card>
  );
}

export function ProjectCard({ project }: { project: Project }) {
  return (
    <Link
      href={`/projects/view?projectId=${project.projectId}`}
      className="group block rounded-xl focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <Card className="h-full transition-shadow group-hover:shadow-md group-hover:ring-foreground/20">
        <div className="-mt-(--card-spacing) overflow-hidden rounded-t-xl">
          <ProjectThumb projectId={project.projectId} />
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
        </CardContent>
      </Card>
    </Link>
  );
}

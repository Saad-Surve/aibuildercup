"use client";

import { useEffect } from "react";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";

import { useAuth } from "@/components/auth/auth-provider";
import { getCreatorLibrary, type CreatorLibrary } from "@/lib/creator-library";
import { listProjects, listThumbnails } from "@/lib/projects";
import type { ProjectList, ThumbnailConcept } from "@/lib/types";

const MAX_PROJECTS = 9;
const MAX_PROJECT_POSTERS = 20;
const MAX_IMAGES = 80;
const QUERY_CONCURRENCY = 2;
const IMAGE_CONCURRENCY = 4;
const SIGNED_URL_SAFETY_MS = 30_000;

type IdleApi = {
  requestIdleCallback?: (
    callback: () => void,
    options?: { timeout: number },
  ) => number;
  cancelIdleCallback?: (handle: number) => void;
};

type NavigatorWithConnection = Navigator & {
  connection?: { saveData?: boolean };
};

function signedUrlExpiry(url: string): number | null {
  try {
    const parsed = new URL(url);
    const date =
      parsed.searchParams.get("X-Goog-Date") ??
      parsed.searchParams.get("X-Amz-Date");
    const expires =
      parsed.searchParams.get("X-Goog-Expires") ??
      parsed.searchParams.get("X-Amz-Expires");
    if (!date || !expires) return null;
    const seconds = Number(expires);
    if (!Number.isFinite(seconds)) return null;
    const match = date.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/);
    if (!match) return null;
    const [, year, month, day, hour, minute, second] = match;
    return (
      Date.UTC(
        Number(year),
        Number(month) - 1,
        Number(day),
        Number(hour),
        Number(minute),
        Number(second),
      ) +
      seconds * 1000
    );
  } catch {
    return null;
  }
}

function isWarmable(url: string): boolean {
  const expiresAt = signedUrlExpiry(url);
  return expiresAt === null || expiresAt > Date.now() + SIGNED_URL_SAFETY_MS;
}

async function inParallel<T>(
  values: T[],
  concurrency: number,
  task: (value: T) => Promise<void>,
): Promise<void> {
  let next = 0;
  const workers = Array.from(
    { length: Math.min(concurrency, values.length) },
    async () => {
      while (next < values.length) {
        const value = values[next++];
        await task(value);
      }
    },
  );
  await Promise.all(workers);
}

function warmImage(url: string): Promise<void> {
  return new Promise((resolve) => {
    const image = new Image();
    const timeout = window.setTimeout(resolve, 15_000);
    const settle = () => {
      window.clearTimeout(timeout);
      resolve();
    };
    image.addEventListener("load", settle, { once: true });
    image.addEventListener("error", settle, { once: true });
    image.src = url;
  });
}

async function prefetchImages(client: QueryClient): Promise<void> {
  await Promise.all([
    client.prefetchQuery({
      queryKey: ["projects"],
      queryFn: listProjects,
    }),
    client.prefetchQuery({
      queryKey: ["creator-library"],
      queryFn: getCreatorLibrary,
      staleTime: 30_000,
    }),
  ]);

  const projects = client.getQueryData<ProjectList>(["projects"]);
  const library = client.getQueryData<CreatorLibrary>(["creator-library"]);
  const recentVideoProjects = (projects?.items ?? [])
    .filter((project) => project.kind === "video")
    .toSorted(
      (left, right) =>
        new Date(right.updatedAt).getTime() -
        new Date(left.updatedAt).getTime(),
    )
    .slice(0, MAX_PROJECTS);
  const recentProjects = (projects?.items ?? [])
    .toSorted(
      (left, right) =>
        new Date(right.updatedAt).getTime() -
        new Date(left.updatedAt).getTime(),
    )
    .slice(0, MAX_PROJECT_POSTERS);

  await inParallel(recentVideoProjects, QUERY_CONCURRENCY, async (project) => {
    const projectId = project.projectId;
    await client.prefetchQuery({
      queryKey: ["thumbnails", projectId],
      queryFn: () => listThumbnails(projectId),
    });
  });

  const urls = [
    ...recentProjects.map((project) => project.posterUrl),
    ...(library?.nodes ?? []).map((node) => node.thumbnailUrl),
    ...recentVideoProjects.flatMap((project) => {
      const projectId = project.projectId;
      const thumbnails = client.getQueryData<{ items: ThumbnailConcept[] }>([
        "thumbnails",
        projectId,
      ]);
      return (thumbnails?.items ?? []).map((item) => item.previewUrl);
    }),
  ];
  const unique = Array.from(
    new Set(urls.filter((url): url is string => Boolean(url))),
  )
    .filter(isWarmable)
    .slice(0, MAX_IMAGES);

  await inParallel(unique, IMAGE_CONCURRENCY, warmImage);
}

/** Warms read-only image data and the browser cache after the app becomes idle. */
export function ImagePrefetcher() {
  const client = useQueryClient();
  const { user } = useAuth();

  useEffect(() => {
    if (!user || (navigator as NavigatorWithConnection).connection?.saveData) {
      return;
    }

    let cancelled = false;
    const idleApi = window as unknown as IdleApi;
    const run = () => {
      if (!cancelled) void prefetchImages(client).catch(() => undefined);
    };
    const handle = idleApi.requestIdleCallback
      ? idleApi.requestIdleCallback(run, { timeout: 5_000 })
      : window.setTimeout(run, 1_500);

    return () => {
      cancelled = true;
      if (idleApi.cancelIdleCallback && idleApi.requestIdleCallback) {
        idleApi.cancelIdleCallback(handle);
      } else {
        window.clearTimeout(handle);
      }
    };
  }, [client, user]);

  return null;
}

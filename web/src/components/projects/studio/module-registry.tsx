"use client";

import dynamic from "next/dynamic";

import { Skeleton } from "@/components/ui/skeleton";
import type { StudioModuleId } from "@/lib/studio";

/**
 * Lazily loaded studio modules.
 *
 * Each module is its own chunk so opening a project does not parse the thumbnail
 * canvas, glossary editor and dubbing UI up front. The loader functions are kept
 * separately from the `dynamic()` wrappers so `prefetchStudioModule` can warm a
 * chunk on tab hover/focus without rendering the module.
 */

function ModuleLoading() {
  return <Skeleton className="h-[min(60vh,40rem)] w-full" />;
}

const loaders = {
  transcript: () => import("@/components/projects/transcript-panel"),
  review: () => import("@/components/projects/review-panel"),
  captions: () => import("@/components/projects/studio/captions-module"),
  packaging: () => import("@/components/projects/studio/packaging-module"),
  localization: () =>
    import("@/components/projects/studio/localization-module"),
  publishing: () => import("@/components/projects/studio/publishing-module"),
} as const;

type LazyModuleId = keyof typeof loaders;

const TranscriptPanel = dynamic(
  () => loaders.transcript().then((module) => module.TranscriptPanel),
  { loading: ModuleLoading },
);
const ReviewPanel = dynamic(
  () => loaders.review().then((module) => module.ReviewPanel),
  { loading: ModuleLoading },
);
const CaptionsModule = dynamic(
  () => loaders.captions().then((module) => module.CaptionsModule),
  { loading: ModuleLoading },
);
const PackagingModule = dynamic(
  () => loaders.packaging().then((module) => module.PackagingModule),
  { loading: ModuleLoading },
);
const LocalizationModule = dynamic(
  () => loaders.localization().then((module) => module.LocalizationModule),
  { loading: ModuleLoading },
);
const PublishingModule = dynamic(
  () => loaders.publishing().then((module) => module.PublishingModule),
  { loading: ModuleLoading },
);

export const STUDIO_MODULE_COMPONENTS = {
  transcript: TranscriptPanel,
  review: ReviewPanel,
  captions: CaptionsModule,
  packaging: PackagingModule,
  localization: LocalizationModule,
  publishing: PublishingModule,
} satisfies Record<LazyModuleId, unknown>;

/** Start downloading a module's chunk before the user opens it. Idempotent. */
export function prefetchStudioModule(id: StudioModuleId): void {
  if (id === "overview") return;
  void loaders[id]();
}

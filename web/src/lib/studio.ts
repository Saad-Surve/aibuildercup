import {
  ClosedCaptionIcon,
  DashboardSquare01Icon,
  FileVideoIcon,
  ImageAdd01Icon,
  Megaphone01Icon,
  SparklesIcon,
} from "@hugeicons/core-free-icons";

export type StudioModuleId =
  | "overview"
  | "transcript"
  | "review"
  | "captions"
  | "packaging"
  | "localization";

export interface StudioModule {
  id: StudioModuleId;
  label: string;
  /** One-line description for the module card. */
  description: string;
  // A hugeicons icon object, rendered through the shared `Icon` wrapper.
  icon: typeof ClosedCaptionIcon;
  /** Whether the module is useless until a transcript exists. */
  needsTranscript: boolean;
  /** Wired-up modules open; placeholders are shown as coming soon. */
  ready: boolean;
}

export const STUDIO_MODULES: StudioModule[] = [
  {
    id: "transcript",
    label: "Transcript",
    description:
      "The timestamped words. Edit them, label speakers, and re-run recognition.",
    icon: ClosedCaptionIcon,
    needsTranscript: true,
    ready: true,
  },
  {
    id: "review",
    label: "Review + Findings",
    description:
      "Nine reviewers score the cut and pin findings to the timeline heatmap.",
    icon: SparklesIcon,
    needsTranscript: true,
    ready: true,
  },
  {
    id: "captions",
    label: "Burn Captions",
    description:
      "Render a styled, captioned MP4 from the transcript. The original is untouched.",
    icon: FileVideoIcon,
    needsTranscript: true,
    ready: true,
  },
  {
    id: "packaging",
    label: "Thumbnail, Clips & SEO",
    description:
      "Generate grounded thumbnail concepts from the video, then iterate and apply the winner.",
    icon: ImageAdd01Icon,
    needsTranscript: false,
    ready: true,
  },
  {
    id: "localization",
    label: "Localization",
    description:
      "Translate and dub the video into your target languages with a glossary.",
    icon: Megaphone01Icon,
    needsTranscript: true,
    ready: true,
  },
];

export function moduleById(id: string | null | undefined): StudioModule | null {
  return STUDIO_MODULES.find((module) => module.id === id) ?? null;
}

export function isStudioModuleId(value: unknown): value is StudioModuleId {
  return (
    typeof value === "string" &&
    STUDIO_MODULES.some((module) => module.id === value)
  );
}

/**
 * Canonical URL for a module. `overview` drops the trailing segment so the
 * project root stays clean; every other module keeps its path segment. These
 * paths are served by a rewrite (a static export cannot prerender a project id),
 * so they must never be navigated to with a normal `<Link>` — see
 * `useStudioModule` for the shallow-routing client navigation.
 */
export function studioModuleHref(
  projectId: string,
  moduleId: StudioModuleId,
): string {
  const base = `/projects/view/project/${projectId}`;
  return moduleId === "overview" ? base : `${base}/${moduleId}`;
}

/**
 * Entry URL for the workspace (from the project list, create dialog, or a back
 * link).
 *
 * The pretty `/projects/view/project/{id}` path is served by a rewrite, which a
 * static export cannot give an RSC payload — a client navigation to it falls
 * back to a full document reload. Entering the workspace therefore goes through
 * the real `/projects/view` route with a query id; inside, module switches use
 * {@link studioModuleHref} shallowly.
 */
export function workspaceHref(projectId: string): string {
  return `/projects/view?projectId=${encodeURIComponent(projectId)}`;
}

/**
 * Read the active module out of a pathname. Returns `null` when the path is not
 * a project path at all (e.g. the query-string shell), `overview` when the path
 * is a project root or an unknown segment, and the module id otherwise.
 */
export function studioModuleFromPath(
  pathname: string | null | undefined,
): StudioModuleId | null {
  if (!pathname) return null;
  const match = pathname.match(
    /^\/projects\/view\/project\/[^/]+(?:\/([^/?#]+))?/,
  );
  if (!match) return null;
  const candidate = match[1] ?? "overview";
  return isStudioModuleId(candidate) ? candidate : "overview";
}

export const OVERVIEW_ICON = DashboardSquare01Icon;

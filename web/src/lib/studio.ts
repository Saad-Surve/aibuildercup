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

export const OVERVIEW_ICON = DashboardSquare01Icon;

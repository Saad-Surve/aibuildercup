import { apiFetch } from "@/lib/api-client";
import type {
  CreatorContext,
  Draft,
  DraftBlock,
  DraftBrief,
  DraftFormat,
} from "@/lib/types";

export function getDraft(projectId: string): Promise<Draft> {
  return apiFetch<Draft>(`/projects/${projectId}/draft`);
}

/** What the last generation retrieved from the creator's channel (style evidence). */
export function getDraftContext(projectId: string): Promise<CreatorContext> {
  return apiFetch<CreatorContext>(`/projects/${projectId}/draft/context`);
}

export function saveDraft(
  projectId: string,
  input: { title?: string; blocks: DraftBlock[] },
): Promise<Draft> {
  return apiFetch<Draft>(`/projects/${projectId}/draft`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function generateDraft(
  projectId: string,
  brief?: Partial<DraftBrief>,
): Promise<Draft> {
  return apiFetch<Draft>(`/projects/${projectId}/draft/generate`, {
    method: "POST",
    body: JSON.stringify(brief ?? {}),
  });
}

export function assistDraft(
  projectId: string,
  input: { message: string; blockId?: string | null; mode?: string },
): Promise<Draft> {
  return apiFetch<Draft>(`/projects/${projectId}/draft/assist`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/** Drop-in replacements for a selected span (inline variant alternatives). */
export function suggestDraft(
  projectId: string,
  input: { text: string; context?: string; mode?: string; count?: number },
): Promise<{ suggestions: string[] }> {
  return apiFetch<{ suggestions: string[] }>(
    `/projects/${projectId}/draft/suggest`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function formatLabel(format: DraftFormat): string {
  return format === "script" ? "Video script" : "Written content";
}

export const DRAFT_FORMAT_OPTIONS: {
  value: DraftFormat;
  label: string;
  hint: string;
}[] = [
  {
    value: "written",
    label: "Written content",
    hint: "An article, newsletter, or post.",
  },
  {
    value: "script",
    label: "Video script",
    hint: "Scene-by-scene beats for a video.",
  },
];

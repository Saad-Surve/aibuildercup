import { apiFetch } from "@/lib/api-client";
import type {
  AnalysisDimension,
  AnalysisRun,
  Finding,
  HeatmapBin,
  HeatmapColor,
  ReviewerRun,
  Severity,
  StartAnalysisInput,
  StartAnalysisResponse,
} from "@/lib/types";

export interface AnalysisRunList {
  items: AnalysisRun[];
}

export interface ReviewerRunList {
  items: ReviewerRun[];
}

export interface FindingList {
  items: Finding[];
}

export interface HeatmapResponse {
  bins: HeatmapBin[];
}

export function listAnalysisRuns(projectId: string): Promise<AnalysisRunList> {
  return apiFetch<AnalysisRunList>(`/projects/${projectId}/analysis`);
}

export function startAnalysis(
  projectId: string,
  input: StartAnalysisInput = {},
): Promise<StartAnalysisResponse> {
  return apiFetch<StartAnalysisResponse>(`/projects/${projectId}/analysis`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getAnalysisRun(
  projectId: string,
  analysisRunId: string,
): Promise<AnalysisRun> {
  return apiFetch<AnalysisRun>(
    `/projects/${projectId}/analysis/${analysisRunId}`,
  );
}

export function listReviewers(
  projectId: string,
  analysisRunId: string,
): Promise<ReviewerRunList> {
  return apiFetch<ReviewerRunList>(
    `/projects/${projectId}/analysis/${analysisRunId}/reviewers`,
  );
}

export interface FindingQuery {
  dimension?: AnalysisDimension;
  severity?: Severity;
  startMs?: number;
  endMs?: number;
}

export function listFindings(
  projectId: string,
  analysisRunId: string,
  query: FindingQuery = {},
): Promise<FindingList> {
  const params = new URLSearchParams();
  if (query.dimension) params.set("dimension", query.dimension);
  if (query.severity) params.set("severity", query.severity);
  if (query.startMs !== undefined) params.set("startMs", String(query.startMs));
  if (query.endMs !== undefined) params.set("endMs", String(query.endMs));
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return apiFetch<FindingList>(
    `/projects/${projectId}/analysis/${analysisRunId}/findings${suffix}`,
  );
}

export function getHeatmap(
  projectId: string,
  analysisRunId: string,
): Promise<HeatmapResponse> {
  return apiFetch<HeatmapResponse>(
    `/projects/${projectId}/analysis/${analysisRunId}/heatmap`,
  );
}

export interface ContextArtifactUrl {
  url: string;
  contentType: string;
  expiresIn: number;
}

/** Lazy signed URL for one frame/clip a reviewer fetched. */
export function getReviewerContextUrl(
  projectId: string,
  analysisRunId: string,
  reviewerRunId: string,
  index: number,
): Promise<ContextArtifactUrl> {
  return apiFetch<ContextArtifactUrl>(
    `/projects/${projectId}/analysis/${analysisRunId}/reviewers/${reviewerRunId}/context/${index}`,
  );
}

// --- presentation -----------------------------------------------------------

export const DIMENSION_LABELS: Record<AnalysisDimension, string> = {
  truth_evidence: "Truth & Evidence",
  clarity: "Spoken Clarity",
  pacing_retention: "Pacing & Retention",
  legal_safety: "Legal & Safety",
  cultural_localization: "Culture & Localization",
  platform_fit: "Platform Dynamics",
  audience_brand: "Audience & Brand",
  emotional_impact: "Emotional Impact",
  conversion_cta: "Conversion & CTA",
};

export function dimensionLabel(dimension: string): string {
  return (
    DIMENSION_LABELS[dimension as AnalysisDimension] ??
    dimension.replace(/_/g, " ")
  );
}

export const SEVERITY_ORDER: Severity[] = [
  "critical",
  "high",
  "medium",
  "low",
  "none",
];

export const SEVERITY_LABELS: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  none: "Fine",
};

/** Tailwind token for a severity chip. Colour is the review signal, by design. */
export const SEVERITY_TEXT_CLASS: Record<Severity, string> = {
  critical: "text-sev-critical",
  high: "text-sev-high",
  medium: "text-sev-medium",
  low: "text-sev-low",
  none: "text-sev-none",
};

export const SEVERITY_DOT_CLASS: Record<Severity, string> = {
  critical: "bg-sev-critical",
  high: "bg-sev-high",
  medium: "bg-sev-medium",
  low: "bg-sev-low",
  none: "bg-sev-none",
};

export const HEAT_FILL_CLASS: Record<HeatmapColor, string> = {
  green: "bg-heat-green",
  yellow: "bg-heat-yellow",
  orange: "bg-heat-orange",
  red: "bg-heat-red",
};

export function heatFill(bin: HeatmapBin): string {
  return HEAT_FILL_CLASS[bin.color] ?? "bg-heat-red";
}

/** Score as a short mono string on the 1-5 scale: `4.2`, or `—` when absent. */
export function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined) return "—";
  return score.toFixed(1);
}

export function formatDurationMs(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function formatCostUsd(usd: number): string {
  if (usd <= 0) return "$0.00";
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

/** Friendly label for the model output type, e.g. `needs_verification`. */
export function formatFindingType(value: string): string {
  return value.replace(/_/g, " ");
}

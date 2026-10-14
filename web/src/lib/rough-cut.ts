import { apiFetch, apiFetchBlob } from "@/lib/api-client";
import type {
  RoughCutAccepted,
  RoughCutPlan,
  RoughCutRequest,
} from "@/lib/types";

function base(projectId: string, runId: string) {
  return `/projects/${projectId}/analysis/${runId}/rough-cut`;
}

export function getRoughCutPlan(
  projectId: string,
  runId: string,
): Promise<RoughCutPlan> {
  return apiFetch(`${base(projectId, runId)}/plan`);
}

export function previewRoughCutPlan(
  projectId: string,
  runId: string,
  input: RoughCutRequest,
): Promise<RoughCutPlan> {
  return apiFetch(`${base(projectId, runId)}/plan`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function renderRoughCut(
  projectId: string,
  runId: string,
  input: RoughCutRequest,
): Promise<RoughCutAccepted> {
  return apiFetch(base(projectId, runId), {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function discardRoughCut(
  projectId: string,
  assetId: string,
): Promise<void> {
  return apiFetch(`/projects/${projectId}/assets/${assetId}`, {
    method: "DELETE",
  });
}

export async function getSourceCaptions(
  projectId: string,
  assetId: string,
): Promise<string> {
  const blob = await apiFetchBlob(
    `/projects/${projectId}/assets/${assetId}/captions`,
  );
  return `data:text/vtt;charset=utf-8,${encodeURIComponent(await blob.text())}`;
}

export async function downloadRoughCutPlan(
  projectId: string,
  runId: string,
  assetId: string,
  format: "cmx3600" | "markdown",
  fps = 30,
) {
  const params = new URLSearchParams({ assetId, format, fps: String(fps) });
  const blob = await apiFetchBlob(`${base(projectId, runId)}/edl?${params}`);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `resonance-rough-cut.${format === "markdown" ? "md" : "edl"}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

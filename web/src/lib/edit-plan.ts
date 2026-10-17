import { apiFetch, apiFetchBlob } from "@/lib/api-client";
import type { EditPlan } from "@/lib/types";

export type EditLabels = Record<string, "cut" | "note">;

function base(projectId: string, runId: string) {
  return `/projects/${projectId}/analysis/${runId}/edit-plan`;
}

export function getEditPlan(
  projectId: string,
  runId: string,
  labels: EditLabels,
): Promise<EditPlan> {
  const params = new URLSearchParams({ labels: JSON.stringify(labels) });
  return apiFetch(`${base(projectId, runId)}/plan?${params}`);
}

export async function downloadEditPlan(
  projectId: string,
  runId: string,
  labels: EditLabels,
  format: "cmx3600" | "markdown",
  fps: number,
) {
  const params = new URLSearchParams({
    labels: JSON.stringify(labels),
    format,
    fps: String(fps),
  });
  const blob = await apiFetchBlob(`${base(projectId, runId)}/edl?${params}`);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `resonance-edit-plan.${format === "markdown" ? "md" : "edl"}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

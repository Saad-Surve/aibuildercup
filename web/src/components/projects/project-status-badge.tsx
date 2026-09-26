import { Badge } from "@/components/ui/badge";
import type { ProjectStatus } from "@/lib/types";

const STATUS_LABEL: Record<ProjectStatus, string> = {
  draft: "Draft",
  uploading: "Uploading",
  processing: "Processing",
  ready: "Ready",
  partial_failure: "Partial",
  failed: "Failed",
  archived: "Archived",
};

function statusVariant(
  status: ProjectStatus,
): "default" | "secondary" | "outline" | "destructive" {
  if (status === "ready") return "default";
  if (status === "processing" || status === "uploading") return "secondary";
  if (status === "failed" || status === "partial_failure") return "destructive";
  return "outline";
}

export function ProjectStatusBadge({ status }: { status: ProjectStatus }) {
  return (
    <Badge className="h-7 px-2.5" variant={statusVariant(status)}>
      {STATUS_LABEL[status]}
    </Badge>
  );
}

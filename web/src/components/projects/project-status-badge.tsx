import { Badge } from "@/components/ui/badge";
import type { ProjectStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUS_LABEL: Record<ProjectStatus, string> = {
  draft: "Draft",
  uploading: "Uploading",
  processing: "Processing",
  ready: "Ready",
  partial_failure: "Partial",
  failed: "Failed",
  archived: "Archived",
};

/*
 * Semantic status colours: green is done, amber is working, orange is partial,
 * red is failed, grey is inert. The accent (signal) is reserved for actions —
 * a "Ready" pill should read as success, not as a button.
 */
const STATUS_CLASS: Record<ProjectStatus, string> = {
  draft: "border-border bg-muted text-muted-foreground",
  uploading: "border-sev-low/30 bg-sev-low/10 text-sev-low",
  processing: "border-sev-low/30 bg-sev-low/10 text-sev-low",
  ready: "border-sev-good/30 bg-sev-good/10 text-sev-good",
  partial_failure: "border-sev-medium/30 bg-sev-medium/10 text-sev-medium",
  failed: "border-destructive/30 bg-destructive/10 text-destructive",
  archived: "border-border bg-muted text-muted-foreground",
};

export function ProjectStatusBadge({ status }: { status: ProjectStatus }) {
  return (
    <Badge
      variant="outline"
      className={cn("h-7 border px-2.5", STATUS_CLASS[status])}
    >
      {STATUS_LABEL[status]}
    </Badge>
  );
}

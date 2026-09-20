import Link from "next/link";
import { Film01Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { ProjectStatusBadge } from "@/components/projects/project-status-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Project } from "@/lib/types";

export function ProjectCard({ project }: { project: Project }) {
  return (
    <Link
      href={`/projects/view?projectId=${project.projectId}`}
      className="group block rounded-xl focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <Card className="h-full transition-colors group-hover:ring-foreground/20">
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <span className="flex size-8 items-center justify-center rounded-lg bg-muted text-muted-foreground">
              <Icon icon={Film01Icon} />
            </span>
            <ProjectStatusBadge status={project.status} />
          </div>
          <CardTitle className="mt-1 line-clamp-1">{project.name}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="line-clamp-2 min-h-10 text-sm text-muted-foreground">
            {project.description || "No description."}
          </p>
        </CardContent>
      </Card>
    </Link>
  );
}

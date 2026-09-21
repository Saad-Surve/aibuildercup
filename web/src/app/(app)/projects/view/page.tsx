"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft01Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { PageHeader } from "@/components/common/page-header";
import { ProjectWorkspace } from "@/components/projects/project-workspace";
import { Skeleton } from "@/components/ui/skeleton";

function WorkspaceRoute() {
  const searchParams = useSearchParams();
  const projectId = searchParams.get("projectId");

  if (!projectId) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <PageHeader title="Project not found" />
        <p className="text-sm text-muted-foreground">
          No project was specified.
        </p>
        <Link
          href="/projects"
          className="inline-flex items-center gap-1.5 text-sm text-signal hover:underline"
        >
          <Icon icon={ArrowLeft01Icon} />
          Back to projects
        </Link>
      </div>
    );
  }

  return <ProjectWorkspace projectId={projectId} />;
}

export default function ProjectViewPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-4xl space-y-6">
          <Skeleton className="h-8 w-56" />
          <Skeleton className="h-40 w-full" />
        </div>
      }
    >
      <WorkspaceRoute />
    </Suspense>
  );
}

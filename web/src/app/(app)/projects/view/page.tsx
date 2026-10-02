"use client";

import { Suspense } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { ArrowLeft01Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { PageHeader } from "@/components/common/page-header";
import { ProjectWorkspace } from "@/components/projects/project-workspace";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Path-based project routing.
 *
 * The web app is a static export, so arbitrary project ids cannot be prerendered
 * as files and a dynamic route is impossible. Instead a rewrite (Next dev
 * `rewrites()` and the Firebase Hosting rewrite) serves this shell for
 * `/projects/view/project/**`, and the client reads the id and module from the
 * path. Query-string links (`?projectId=…&module=…`) still work.
 *
 *   /projects/view/project/{projectId}
 *   /projects/view/project/{projectId}/{module}
 */
function WorkspaceRoute() {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const match = pathname?.match(
    /^\/projects\/view\/project\/([^/]+)(?:\/([^/]+))?/,
  );
  const projectId = match?.[1] ?? searchParams.get("projectId");
  const moduleId = match?.[2] ?? searchParams.get("module") ?? "overview";

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

  return <ProjectWorkspace projectId={projectId} moduleId={moduleId} />;
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

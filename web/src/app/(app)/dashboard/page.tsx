"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight01Icon, FolderOpenIcon } from "@hugeicons/core-free-icons";

import { useAuth } from "@/components/auth/auth-provider";
import { Icon } from "@/components/common/icon";
import { PageHeader } from "@/components/common/page-header";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";
import { ProjectCard } from "@/components/projects/project-card";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { listProjects } from "@/lib/projects";

export default function DashboardPage() {
  const { profile } = useAuth();
  const firstName = profile?.displayName?.split(" ")[0];

  const query = useQuery({ queryKey: ["projects"], queryFn: listProjects });
  const projects = query.data?.items ?? [];
  const recent = projects.slice(0, 3);

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <PageHeader
        title={firstName ? `Welcome, ${firstName}` : "Welcome"}
        description="Create a project to upload a video and run the reviewers."
        actions={<CreateProjectDialog />}
      />

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-heading text-sm font-medium">Recent projects</h2>
          {projects.length > 0 ? (
            <Link
              href="/projects"
              className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
            >
              View all
              <Icon icon={ArrowRight01Icon} />
            </Link>
          ) : null}
        </div>

        {query.isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((key) => (
              <Skeleton key={key} className="h-40 w-full rounded-xl" />
            ))}
          </div>
        ) : recent.length === 0 ? (
          <Empty className="border py-16">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Icon icon={FolderOpenIcon} />
              </EmptyMedia>
              <EmptyTitle>No projects yet</EmptyTitle>
              <EmptyDescription>
                Upload a video to get a timestamped transcript and a
                multi-reviewer heatmap under the timeline.
              </EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <CreateProjectDialog />
            </EmptyContent>
          </Empty>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {recent.map((project) => (
              <ProjectCard key={project.projectId} project={project} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

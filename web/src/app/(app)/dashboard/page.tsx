"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight01Icon, FolderOpenIcon } from "@hugeicons/core-free-icons";

import { useAuth } from "@/components/auth/auth-provider";
import { Icon } from "@/components/common/icon";
import { PageHeader } from "@/components/common/page-header";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";
import {
  ProjectCard,
  ProjectCardSkeleton,
} from "@/components/projects/project-card";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
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
        description="Upload a video for a transcript and reviewer heatmap, or start a draft."
        actions={
          query.isLoading || projects.length > 0 ? (
            <CreateProjectDialog />
          ) : undefined
        }
      />

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-heading text-base font-medium tracking-tight">
            Recent projects
          </h2>
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
              <ProjectCardSkeleton key={key} />
            ))}
          </div>
        ) : recent.length === 0 ? (
          <Empty className="border border-transparent py-16 shadow-sm ring-1 ring-foreground/10">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Icon icon={FolderOpenIcon} />
              </EmptyMedia>
              <EmptyTitle>No projects yet</EmptyTitle>
              <EmptyDescription>
                Upload a video to get a timestamped transcript and a
                multi-reviewer heatmap under the timeline — or start a draft and
                write with a writing partner.
              </EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <CreateProjectDialog />
            </EmptyContent>
          </Empty>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {recent.map((project) => (
              <div key={project.projectId}>
                <ProjectCard project={project} />
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

"use client";

import { useQuery } from "@tanstack/react-query";
import { FolderOpenIcon } from "@hugeicons/core-free-icons";

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

export default function ProjectsPage() {
  const query = useQuery({ queryKey: ["projects"], queryFn: listProjects });
  const projects = (query.data?.items ?? []).toSorted(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
  );

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <PageHeader
        title="Projects"
        description="Video projects get a transcript, reviewer heatmap, and captions. Draft projects get a writing workspace."
        actions={
          query.isLoading || projects.length > 0 ? (
            <CreateProjectDialog />
          ) : undefined
        }
      />

      {query.isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((key) => (
            <ProjectCardSkeleton key={key} />
          ))}
        </div>
      ) : query.isError ? (
        <p className="text-sm text-destructive">
          Could not load your projects. Refresh to try again.
        </p>
      ) : projects.length === 0 ? (
        <Empty className="border border-transparent py-16 shadow-sm ring-1 ring-foreground/10">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Icon icon={FolderOpenIcon} />
            </EmptyMedia>
            <EmptyTitle>No projects yet</EmptyTitle>
            <EmptyDescription>
              Create a video project to upload a video and run the reviewers, or
              a draft project to write with a writing partner.
            </EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <CreateProjectDialog />
          </EmptyContent>
        </Empty>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <div key={project.projectId}>
              <ProjectCard project={project} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

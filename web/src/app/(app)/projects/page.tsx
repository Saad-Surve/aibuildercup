"use client";

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
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
  const projects = query.data?.items ?? [];

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <PageHeader
        title="Projects"
        description="One video per project. Upload a video to get a transcript and a reviewer heatmap."
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
              Create a project to upload a video and run the reviewers.
            </EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <CreateProjectDialog />
          </EmptyContent>
        </Empty>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((project, index) => (
            <motion.div
              key={project.projectId}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3, delay: Math.min(index, 8) * 0.05 }}
            >
              <ProjectCard project={project} />
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}

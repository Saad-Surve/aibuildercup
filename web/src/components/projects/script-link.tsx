"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight01Icon,
  CloudUploadIcon,
  FileTextIcon,
  FileVideoIcon,
} from "@hugeicons/core-free-icons";
import { toast } from "sonner";

import { Icon } from "@/components/common/icon";
import { ApiError } from "@/lib/api-client";
import { getProject, updateProject } from "@/lib/projects";
import { listPublishes } from "@/lib/publishes";
import { workspaceHref } from "@/lib/studio";
import type { Project } from "@/lib/types";
import { useReadOnly } from "@/lib/read-only";
import { cn } from "@/lib/utils";

function describe(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}

const FLOW_TEXT = "text-[13px] text-muted-foreground";

function FlowLink({
  href,
  children,
  current,
}: {
  href: string | null;
  children: React.ReactNode;
  current?: boolean;
}) {
  if (href === null || current) {
    return (
      <span
        className={cn(
          "min-w-0 truncate",
          current && "font-medium text-foreground",
        )}
      >
        {children}
      </span>
    );
  }
  return (
    <Link
      href={href}
      className="min-w-0 truncate transition-colors hover:text-foreground hover:underline"
    >
      {children}
    </Link>
  );
}

function Separator() {
  return (
    <span aria-hidden className="shrink-0 text-muted-foreground/50">
      <Icon icon={ArrowRight01Icon} className="size-3" />
    </span>
  );
}

function uploadLabel(status: string | null | undefined): string {
  if (status === "published") return "Live on YouTube";
  if (status === "failed") return "Upload failed";
  if (status === "queued" || status === "uploading" || status === "processing")
    return "Uploading…";
  return "Not uploaded yet";
}

function VideoFlow({ project }: { project: Project }) {
  const queryClient = useQueryClient();
  const readOnly = useReadOnly();
  const [confirmingUnlink, setConfirmingUnlink] = useState(false);
  // Normalise: a backend older than the link fields omits them (undefined),
  // which must behave exactly like an explicit null — never a phantom row.
  const draftId = project.sourceDraftId ?? null;

  // Title comes from the snapshot; this only detects a deleted draft so the
  // row degrades to plain text instead of a dead link.
  const draftQuery = useQuery({
    queryKey: ["project", draftId ?? "none"],
    queryFn: () => getProject(draftId ?? "none"),
    enabled: draftId !== null,
    retry: false,
    staleTime: 60_000,
  });
  const publishesQuery = useQuery({
    queryKey: ["publishes", project.projectId],
    queryFn: () => listPublishes(project.projectId),
    enabled: draftId !== null,
    staleTime: 30_000,
  });
  const unlinkMutation = useMutation({
    mutationFn: () => updateProject(project.projectId, { sourceDraftId: null }),
    onSuccess: () => {
      setConfirmingUnlink(false);
      toast.success("Script source unlinked");
      void queryClient.invalidateQueries({
        queryKey: ["project", project.projectId],
      });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (error) => toast.error(describe(error, "Could not unlink.")),
  });

  if (draftId === null) return null;

  const draftGone = draftQuery.isError;
  const draftTitle = project.sourceDraftName ?? "Draft";
  const latest = publishesQuery.data?.items[0];

  return (
    <p className={cn("flex flex-wrap items-center gap-x-1.5 gap-y-0.5", FLOW_TEXT)}>
      <Icon icon={FileTextIcon} className="size-3.5 shrink-0" />
      <FlowLink href={draftGone ? null : workspaceHref(draftId)}>
        {draftTitle}
        {draftGone ? " (deleted)" : ""}
      </FlowLink>
      <Separator />
      <Icon icon={FileVideoIcon} className="size-3.5 shrink-0" />
      <FlowLink href={null} current>
        {project.name}
      </FlowLink>
      <Separator />
      <Icon icon={CloudUploadIcon} className="size-3.5 shrink-0" />
      <FlowLink href={workspaceHref(project.projectId)}>
        {publishesQuery.isLoading ? "Checking…" : uploadLabel(latest?.status)}
      </FlowLink>
      {readOnly ? null : (
        <button
          type="button"
          onClick={() => {
            if (confirmingUnlink) unlinkMutation.mutate();
            else setConfirmingUnlink(true);
          }}
          onBlur={() => setConfirmingUnlink(false)}
          disabled={unlinkMutation.isPending}
          className="ml-2 shrink-0 underline-offset-4 transition-colors hover:text-foreground hover:underline disabled:opacity-50"
        >
          {confirmingUnlink ? "Confirm unlink?" : "Unlink"}
        </button>
      )}
    </p>
  );
}

/**
 * The draft → video → upload lineage as one quiet flow line, not cards.
 * Rendered on video projects only: the script title jumps straight to its
 * draft, the upload state jumps to this workspace. Renders nothing when the
 * video has no linked draft. Drafts navigate via Go to video instead.
 */
export function PipelineStrip({ project }: { project: Project }) {
  if (project.kind !== "video") return null;
  return <VideoFlow project={project} />;
}

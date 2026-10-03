"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Delete02Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { DisabledReason } from "@/components/common/disabled-reason";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogMedia,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api-client";
import { purgeProjectMedia } from "@/lib/local-media";
import { deleteProject } from "@/lib/projects";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";

function describe(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Could not delete this project. Try again.";
}

export function DeleteProjectDialog({
  projectId,
  projectName,
  assetIds = [],
  destructive = false,
}: {
  projectId: string;
  projectName: string;
  assetIds?: string[];
  //: Render the trigger with destructive colours instead of a neutral outline.
  destructive?: boolean;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const readOnly = useReadOnly();
  const [open, setOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setPending(true);
    setError(null);
    try {
      await deleteProject(projectId);
      // Drop the local upload copy + posters so the deleted project can't
      // resurface in cards or the player from this browser's cache.
      await purgeProjectMedia(projectId, assetIds);
      await queryClient.invalidateQueries({ queryKey: ["projects"] });
      setOpen(false);
      router.push("/projects");
    } catch (caught) {
      setError(describe(caught));
    } finally {
      setPending(false);
    }
  }

  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) setError(null);
      }}
    >
      <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
        <AlertDialogTrigger
          render={
            <Button
              variant={destructive ? "destructive" : "outline"}
              size="sm"
              disabled={readOnly}
            >
              <Icon icon={Delete02Icon} />
              Delete
            </Button>
          }
        />
      </DisabledReason>
      <AlertDialogContent size="sm">
        <AlertDialogHeader>
          <AlertDialogMedia>
            <Icon icon={Delete02Icon} className="text-destructive" />
          </AlertDialogMedia>
          <AlertDialogTitle>Delete this project?</AlertDialogTitle>
          <AlertDialogDescription>
            &ldquo;{projectName}&rdquo; and its uploaded video will be
            permanently deleted. Transcripts, clips, and everything derived from
            it go with it. This can&rsquo;t be undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <AlertDialogFooter>
          <AlertDialogCancel disabled={pending}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            disabled={pending}
            onClick={(event) => {
              event.preventDefault();
              void confirm();
            }}
          >
            {pending ? "Deleting…" : "Delete project"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

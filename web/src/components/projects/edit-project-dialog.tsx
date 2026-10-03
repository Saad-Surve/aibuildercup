"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Edit02Icon } from "@hugeicons/core-free-icons";
import { toast } from "sonner";

import { Icon } from "@/components/common/icon";
import { DisabledReason } from "@/components/common/disabled-reason";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api-client";
import { updateProject } from "@/lib/projects";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";

function describe(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Could not save the project.";
}

export function EditProjectDialog({
  projectId,
  initialName,
  initialDescription,
  initialThumbnailConcept,
  iconOnly = false,
}: {
  projectId: string;
  initialName: string;
  initialDescription: string;
  initialThumbnailConcept: string;
  /** Render a compact icon button instead of the labelled "Edit" button. */
  iconOnly?: boolean;
}) {
  const queryClient = useQueryClient();
  const readOnly = useReadOnly();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(initialName);
  const [description, setDescription] = useState(initialDescription);
  const [thumbnailConcept, setThumbnailConcept] = useState(
    initialThumbnailConcept,
  );
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      updateProject(projectId, {
        name: name.trim(),
        description: description.trim(),
        thumbnailConcept: thumbnailConcept.trim(),
      }),
    onSuccess: (project) => {
      queryClient.setQueryData(["project", projectId], project);
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success("Project updated");
      setOpen(false);
    },
    onError: (caught) => setError(describe(caught)),
  });

  function onOpenChange(next: boolean) {
    if (next) {
      setName(initialName);
      setDescription(initialDescription);
      setThumbnailConcept(initialThumbnailConcept);
      setError(null);
    }
    if (!next && mutation.isPending) return;
    setOpen(next);
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setError("Give the project a name.");
      return;
    }
    setError(null);
    mutation.mutate();
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
        <DialogTrigger
          render={
            iconOnly ? (
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label="Edit project"
                disabled={readOnly}
              />
            ) : (
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={readOnly}
              />
            )
          }
        >
          <Icon icon={Edit02Icon} />
          {iconOnly ? null : "Edit"}
        </DialogTrigger>
      </DisabledReason>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit project</DialogTitle>
          <DialogDescription>
            Rename the project or update its description.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit}>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="edit-project-name" required>
                Name
              </FieldLabel>
              <Input
                id="edit-project-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                maxLength={200}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="edit-project-description">
                Description
              </FieldLabel>
              <Textarea
                id="edit-project-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={3}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="edit-project-thumbnail">
                Thumbnail concept
              </FieldLabel>
              <Input
                id="edit-project-thumbnail"
                value={thumbnailConcept}
                onChange={(event) =>
                  setThumbnailConcept(event.target.value)
                }
                placeholder="Optional — what the thumbnail promises"
                maxLength={500}
              />
            </Field>
            {error ? <FieldError>{error}</FieldError> : null}
          </FieldGroup>
          <DialogFooter className="mt-5">
            <DialogClose
              render={
                <Button
                  type="button"
                  variant="outline"
                  disabled={mutation.isPending}
                />
              }
            >
              Cancel
            </DialogClose>
            <Button type="submit" disabled={mutation.isPending || readOnly}>
              {mutation.isPending ? "Saving…" : "Save changes"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

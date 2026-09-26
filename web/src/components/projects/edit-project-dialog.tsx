"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Edit02Icon } from "@hugeicons/core-free-icons";
import { toast } from "sonner";

import { Icon } from "@/components/common/icon";
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
}: {
  projectId: string;
  initialName: string;
  initialDescription: string;
  initialThumbnailConcept: string;
}) {
  const queryClient = useQueryClient();
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
      <DialogTrigger
        render={<Button type="button" variant="outline" size="sm" />}
      >
        <Icon icon={Edit02Icon} />
        Edit
      </DialogTrigger>
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
              <FieldLabel htmlFor="edit-project-name">Name</FieldLabel>
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
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving…" : "Save changes"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

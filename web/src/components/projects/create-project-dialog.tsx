"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { PlusSignIcon } from "@hugeicons/core-free-icons";
import { toast } from "sonner";

import { Icon } from "@/components/common/icon";
import { ChipSelect } from "@/components/common/chip-select";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api-client";
import { createProject } from "@/lib/projects";
import { LANGUAGE_OPTIONS, PLATFORM_OPTIONS } from "@/lib/onboarding";

function describe(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Could not create the project.";
}

export function CreateProjectDialog() {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [primaryLanguage, setPrimaryLanguage] = useState("en");
  const [platforms, setPlatforms] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success("Project created");
      setOpen(false);
      router.push(`/projects/view?projectId=${project.projectId}`);
    },
    onError: (caught) => setError(describe(caught)),
  });

  function reset() {
    setName("");
    setDescription("");
    setPrimaryLanguage("en");
    setPlatforms([]);
    setError(null);
  }

  function onOpenChange(next: boolean) {
    if (!next && !mutation.isPending) {
      reset();
    }
    setOpen(next);
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setError("Give the project a name.");
      return;
    }
    setError(null);
    mutation.mutate({
      name: name.trim(),
      description: description.trim(),
      primaryLanguage,
      targetPlatforms: platforms,
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger render={<Button />}>
        <Icon icon={PlusSignIcon} />
        New project
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New project</DialogTitle>
          <DialogDescription>
            One video per project. You can change these details later.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit}>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor="project-name">Name</FieldLabel>
              <Input
                id="project-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Career advice video"
                maxLength={200}
              />
            </Field>

            <Field>
              <FieldLabel htmlFor="project-description">Description</FieldLabel>
              <Textarea
                id="project-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="What is this video about?"
                rows={2}
              />
            </Field>

            <Field>
              <FieldLabel htmlFor="project-language">Language</FieldLabel>
              <Select
                value={primaryLanguage}
                onValueChange={(value) => setPrimaryLanguage(String(value))}
              >
                <SelectTrigger id="project-language" className="w-full">
                  <SelectValue placeholder="Select language" />
                </SelectTrigger>
                <SelectContent>
                  {LANGUAGE_OPTIONS.map((language) => (
                    <SelectItem key={language.value} value={language.value}>
                      {language.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>

            <Field>
              <FieldLabel>Target platforms</FieldLabel>
              <ChipSelect
                options={PLATFORM_OPTIONS}
                value={platforms}
                onChange={setPlatforms}
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
              {mutation.isPending ? "Creating…" : "Create project"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

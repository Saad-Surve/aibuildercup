"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  FileVideoIcon,
  PencilEdit02Icon,
  PlusSignIcon,
} from "@hugeicons/core-free-icons";
import { toast } from "sonner";

import { Icon } from "@/components/common/icon";
import { DisabledReason } from "@/components/common/disabled-reason";
import { ChipSelect } from "@/components/common/chip-select";
import { platformLogoSrc } from "@/components/calendar/platform";
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
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";
import { workspaceHref } from "@/lib/studio";
import {
  LANGUAGE_OPTIONS,
  PLATFORM_OPTIONS,
  languageLabel,
} from "@/lib/onboarding";
import type { DraftFormat, ProjectKind } from "@/lib/types";

function describe(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Could not create the project.";
}

type ProjectType = "video" | DraftFormat;

const PROJECT_TYPE_OPTIONS: {
  value: ProjectType;
  label: string;
  description: string;
  icon: typeof FileVideoIcon;
}[] = [
  {
    value: "video",
    label: "Upload a video",
    description: "Transcript, reviewer heatmap, captions, and more.",
    icon: FileVideoIcon,
  },
  {
    value: "written",
    label: "Written content",
    description: "Write an article, newsletter, or post.",
    icon: PencilEdit02Icon,
  },
  {
    value: "script",
    label: "Video script",
    description: "Write scene-by-scene beats for a video.",
    icon: PencilEdit02Icon,
  },
];

export function CreateProjectDialog() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const readOnly = useReadOnly();

  const [open, setOpen] = useState(false);
  const [projectType, setProjectType] = useState<ProjectType>("video");
  const [name, setName] = useState("");
  const [about, setAbout] = useState("");
  const [thumbnailConcept, setThumbnailConcept] = useState("");
  const [primaryLanguage, setPrimaryLanguage] = useState("en");
  const [platforms, setPlatforms] = useState<string[]>([]);
  const [audience, setAudience] = useState("");
  const [tone, setTone] = useState("");
  const [instructions, setInstructions] = useState("");
  const [error, setError] = useState<string | null>(null);
  const kind: ProjectKind = projectType === "video" ? "video" : "draft";
  const draftFormat: DraftFormat =
    projectType === "script" ? "script" : "written";

  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success(
        project.kind === "draft" ? "Draft project created" : "Project created",
      );
      setOpen(false);
      router.push(workspaceHref(project.projectId));
    },
    onError: (caught) => setError(describe(caught)),
  });

  function reset() {
    setProjectType("video");
    setName("");
    setAbout("");
    setThumbnailConcept("");
    setPrimaryLanguage("en");
    setPlatforms([]);
    setAudience("");
    setTone("");
    setInstructions("");
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
    if (kind === "draft" && !about.trim()) {
      setError("What should the draft be about?");
      return;
    }
    setError(null);
    mutation.mutate({
      name: name.trim(),
      description: about.trim(),
      primaryLanguage,
      targetPlatforms: platforms,
      kind,
      draftFormat,
      ...(kind === "video"
        ? { thumbnailConcept: thumbnailConcept.trim() }
        : {
            draftBrief: {
              topic: about.trim(),
              format: draftFormat,
              audience: audience.trim(),
              tone: tone.trim(),
              platform: platforms.join(", "),
              language: primaryLanguage,
              instructions: instructions.trim(),
              targetWords: 0,
              sourceProjectId: "",
            },
          }),
    });
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
        <DialogTrigger render={<Button disabled={readOnly} />}>
          <Icon icon={PlusSignIcon} />
          New project
        </DialogTrigger>
      </DisabledReason>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>New project</DialogTitle>
          <DialogDescription>
            Start with a video or a draft. You can change the details later.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={submit}>
          <FieldGroup>
            <Field>
              <FieldLabel>Project type</FieldLabel>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {PROJECT_TYPE_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    aria-pressed={projectType === option.value}
                    onClick={() => setProjectType(option.value)}
                    className={`flex flex-col gap-1.5 rounded-lg border p-3 text-left transition-colors ${
                      projectType === option.value
                        ? "border-signal/50 bg-signal/5 ring-1 ring-signal/30"
                        : "border-border hover:bg-muted"
                    }`}
                  >
                    <Icon
                      icon={option.icon}
                      className={
                        projectType === option.value
                          ? "text-signal"
                          : "text-muted-foreground"
                      }
                    />
                    <span className="text-sm font-medium">{option.label}</span>
                    <span className="text-xs text-muted-foreground">
                      {option.description}
                    </span>
                  </button>
                ))}
              </div>
            </Field>

            <Field>
              <FieldLabel htmlFor="project-name" required>
                Name
              </FieldLabel>
              <Input
                id="project-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder={
                  kind === "draft"
                    ? "Week three side projects"
                    : "Career advice video"
                }
                maxLength={200}
              />
            </Field>

            <Field>
              <FieldLabel htmlFor="project-about" required={kind === "draft"}>
                What is it about?
              </FieldLabel>
              <Textarea
                id="project-about"
                value={about}
                onChange={(event) => setAbout(event.target.value)}
                placeholder={
                  kind === "draft"
                    ? "Why most side projects stall in week three"
                    : "What is this video about?"
                }
                rows={3}
                maxLength={300}
              />
            </Field>

            {kind === "video" ? (
              <Field>
                <FieldLabel htmlFor="project-thumbnail">
                  Thumbnail concept
                </FieldLabel>
                <Input
                  id="project-thumbnail"
                  value={thumbnailConcept}
                  onChange={(event) => setThumbnailConcept(event.target.value)}
                  placeholder="Optional — what the thumbnail promises"
                  maxLength={500}
                />
              </Field>
            ) : (
              <>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <Field>
                    <FieldLabel htmlFor="project-audience">
                      Who is it for?
                    </FieldLabel>
                    <Input
                      id="project-audience"
                      value={audience}
                      onChange={(event) => setAudience(event.target.value)}
                      placeholder="e.g. first-time founders"
                      maxLength={300}
                    />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="project-tone">Tone</FieldLabel>
                    <Input
                      id="project-tone"
                      value={tone}
                      onChange={(event) => setTone(event.target.value)}
                      placeholder="e.g. direct, warm"
                      maxLength={200}
                    />
                  </Field>
                </div>

                <Field>
                  <FieldLabel htmlFor="project-instructions">
                    Extra notes
                  </FieldLabel>
                  <Textarea
                    id="project-instructions"
                    value={instructions}
                    onChange={(event) => setInstructions(event.target.value)}
                    placeholder="Anything the draft must include or avoid."
                    rows={2}
                  />
                </Field>
              </>
            )}

            <Field>
              <FieldLabel htmlFor="project-language">Language</FieldLabel>
              <Select
                value={primaryLanguage}
                onValueChange={(value) => setPrimaryLanguage(String(value))}
              >
                <SelectTrigger id="project-language" className="w-full">
                  <SelectValue placeholder="Select language">
                    {(value: unknown) =>
                      typeof value === "string"
                        ? languageLabel(value)
                        : "Select language"
                    }
                  </SelectValue>
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
              <FieldLabel>
                {kind === "draft"
                  ? "Where will it publish?"
                  : "Target platforms"}
              </FieldLabel>
              <ChipSelect
                options={PLATFORM_OPTIONS.map((option) => ({
                  ...option,
                  logoSrc: platformLogoSrc(option.value),
                }))}
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
            <Button type="submit" disabled={mutation.isPending || readOnly}>
              {mutation.isPending
                ? "Creating…"
                : kind === "draft"
                  ? "Create & write"
                  : "Create project"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

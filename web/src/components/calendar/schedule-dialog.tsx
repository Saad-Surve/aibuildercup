"use client";

import { useState, type ReactElement } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarAdd01Icon, Delete02Icon } from "@hugeicons/core-free-icons";
import { format } from "date-fns";
import { toast } from "sonner";

import { Icon } from "@/components/common/icon";
import { DisabledReason } from "@/components/common/disabled-reason";
import {
  PlatformLogo,
  PLATFORM_OPTIONS,
  platformLabel,
} from "@/components/calendar/platform";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
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
import { listProjects } from "@/lib/projects";
import {
  createSchedule,
  deleteSchedule,
  updateSchedule,
} from "@/lib/schedules";
import { workspaceHref } from "@/lib/studio";
import type { Schedule, ScheduleStatus } from "@/lib/types";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";
import { cn } from "@/lib/utils";

//: Read-only status shown on the slot card; the system sets it, never the user.
const STATUS_LABEL: Record<ScheduleStatus, string> = {
  planned: "Planned",
  scheduled: "Scheduled",
  published: "Published",
  failed: "Failed",
  cancelled: "Cancelled",
};

const STATUS_BADGE: Record<ScheduleStatus, string> = {
  planned: "border-border bg-muted text-muted-foreground",
  scheduled: "border-signal/40 bg-signal/10 text-foreground",
  published: "border-sev-good/40 bg-sev-good/10 text-sev-good",
  failed: "border-destructive/40 bg-destructive/10 text-destructive",
  cancelled: "border-border bg-muted text-muted-foreground/70",
};

function describe(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}

function toDateInput(value: Date): string {
  return format(value, "yyyy-MM-dd");
}

function toTimeInput(value: Date): string {
  return format(value, "HH:mm");
}

function combineLocal(date: string, time: string): Date {
  return new Date(`${date}T${time || "00:00"}:00`);
}

interface ScheduleDialogProps {
  /** Fixed project; hides the project picker (project-side usage). */
  projectId?: string;
  /** Display name of the fixed project, used as the slot title. */
  projectName?: string;
  /** Edit target; omit to create. */
  schedule?: Schedule;
  /** Prefill for a new slot. */
  initialDate?: Date;
  /** Auto-link this upload on create (wired silently; never offered as a choice). */
  initialPublishId?: string;
  /** Title for a new slot (an upload title); falls back to the project name. */
  initialTitle?: string;
  trigger?: ReactElement;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}

export function ScheduleDialog({
  projectId: fixedProjectId,
  projectName: fixedProjectName,
  schedule,
  initialDate,
  initialPublishId,
  initialTitle,
  trigger,
  open: controlledOpen,
  onOpenChange: controlledOnOpenChange,
}: ScheduleDialogProps) {
  const queryClient = useQueryClient();
  const readOnly = useReadOnly();
  const editing = schedule !== undefined;

  /*
   * The form seeds from props at mount. Callers render the dialog only while it
   * is open (and key it by slot), so every open starts from a fresh mount —
   * no reseed effect needed.
   */
  const [uncontrolledOpen, setUncontrolledOpen] = useState(false);
  const open = controlledOpen ?? uncontrolledOpen;
  function setOpen(next: boolean) {
    setUncontrolledOpen(next);
    controlledOnOpenChange?.(next);
  }

  const seededAt =
    schedule !== undefined
      ? new Date(schedule.scheduledAt)
      : (initialDate ?? new Date());
  const [projectId, setProjectId] = useState(
    schedule?.projectId ?? fixedProjectId ?? "",
  );
  const [date, setDate] = useState(() => toDateInput(seededAt));
  const [time, setTime] = useState(() => toTimeInput(seededAt));
  const [platform, setPlatform] = useState(schedule?.platform ?? "youtube");
  const [notes, setNotes] = useState(schedule?.notes ?? "");
  const [error, setError] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
    enabled: open && !fixedProjectId,
  });
  const projects = projectsQuery.data?.items ?? [];

  function invalidate(project: string) {
    void queryClient.invalidateQueries({ queryKey: ["schedules"] });
    void queryClient.invalidateQueries({
      queryKey: ["project-schedules", project],
    });
    void queryClient.invalidateQueries({ queryKey: ["publishes", project] });
  }

  const saveMutation = useMutation({
    mutationFn: async () => {
      const targetProject = fixedProjectId ?? projectId;
      if (!targetProject) throw new Error("Pick a project for this slot.");
      // No title field: a new slot takes the upload title, else the project
      // name. An edited slot keeps the title it already has.
      const finalTitle =
        initialTitle?.trim() ||
        fixedProjectName ||
        projects.find((project) => project.projectId === targetProject)?.name ||
        "Untitled slot";
      if (!date) throw new Error("Pick a date for this slot.");
      const scheduledAt = combineLocal(date, time).toISOString();
      if (editing && schedule) {
        return updateSchedule(schedule.projectId, schedule.scheduleId, {
          notes,
          platform: platform.trim() || "youtube",
          scheduledAt,
        });
      }
      // The backend arms every YouTube slot: it creates the linked upload and
      // queues it, or keeps the slot planned/failed with `statusDetail` naming
      // exactly what is missing. There is no silent plan-only fallback.
      return createSchedule(targetProject, {
        title: finalTitle,
        notes,
        platform: platform.trim() || "youtube",
        scheduledAt,
        publishId: initialPublishId ?? null,
      });
    },
    onSuccess: (saved) => {
      invalidate(saved.projectId);
      const blocked =
        saved.statusDetail &&
        (saved.status === "planned" || saved.status === "failed");
      if (editing) {
        if (blocked) {
          toast.warning("Slot updated", {
            description: saved.statusDetail ?? undefined,
          });
        } else {
          toast.success("Slot updated");
        }
      } else if (saved.status === "scheduled") {
        // A slot time in the past uploads public right away (the go-live was
        // intended); don't promise a future "goes live" for it.
        const liveNow =
          Number(new Date(saved.scheduledAt).getTime()) <= Date.now();
        toast.success(liveNow ? "Uploading now" : "Upload scheduled", {
          description: liveNow
            ? `The video is uploading${saved.connectionDisplayName ? ` to ${saved.connectionDisplayName}` : ""} and will go public as soon as it finishes processing.`
            : `Goes live ${format(new Date(saved.scheduledAt), "PPp")}${saved.connectionDisplayName ? ` on ${saved.connectionDisplayName}` : ""}.`,
        });
      } else if (blocked) {
        toast.warning("Slot saved", {
          description: saved.statusDetail ?? undefined,
        });
      } else {
        toast.success("Slot scheduled");
      }
      setOpen(false);
    },
    onError: (caught) => setError(describe(caught, "Could not save the slot.")),
  });

  const deleteMutation = useMutation({
    mutationFn: () => {
      if (!schedule) throw new Error("Nothing to delete.");
      return deleteSchedule(schedule.projectId, schedule.scheduleId);
    },
    onSuccess: () => {
      if (schedule) invalidate(schedule.projectId);
      toast.success("Slot deleted");
      setOpen(false);
    },
    onError: (caught) =>
      setError(describe(caught, "Could not delete the slot. Try again.")),
  });

  const busy = saveMutation.isPending || deleteMutation.isPending;

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {trigger ? <DialogTrigger render={trigger} /> : null}
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{editing ? "Edit slot" : "Schedule a slot"}</DialogTitle>
        </DialogHeader>
        {editing && schedule ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {schedule.title}
            </span>
            <Badge className={STATUS_BADGE[schedule.status]}>
              {STATUS_LABEL[schedule.status]}
            </Badge>
          </div>
        ) : null}
        {editing &&
        schedule?.statusDetail &&
        (schedule.status === "planned" || schedule.status === "failed") ? (
          <p className="text-xs text-destructive">{schedule.statusDetail}</p>
        ) : null}
        {!editing && initialTitle ? (
          <p className="text-sm text-muted-foreground">
            For upload: {initialTitle}
          </p>
        ) : null}

        <FieldGroup>
          {fixedProjectId ? null : (
            <Field>
              <FieldLabel htmlFor="schedule-project" required>
                Project
              </FieldLabel>
              <Select
                value={projectId}
                onValueChange={(value) => setProjectId(value ?? "")}
              >
                <SelectTrigger id="schedule-project" className="w-full">
                  <SelectValue placeholder="Pick a project">
                    {(value: unknown) =>
                      typeof value === "string" && value.length > 0
                        ? (projects.find(
                            (project) => project.projectId === value,
                          )?.name ?? value)
                        : "Pick a project"
                    }
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {projects.map((project) => (
                    <SelectItem
                      key={project.projectId}
                      value={project.projectId}
                    >
                      {project.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          )}

          <div className="grid grid-cols-2 gap-4">
            <Field>
              <FieldLabel htmlFor="schedule-date" required>
                Date
              </FieldLabel>
              <Input
                id="schedule-date"
                type="date"
                value={date}
                onChange={(event) => setDate(event.target.value)}
              />
            </Field>
            <Field>
              <FieldLabel htmlFor="schedule-time">Time</FieldLabel>
              <Input
                id="schedule-time"
                type="time"
                value={time}
                onChange={(event) => setTime(event.target.value)}
              />
            </Field>
          </div>

          <div>
            <Field>
              <FieldLabel>Platform</FieldLabel>
              <Select
                value={platform}
                onValueChange={(value) => setPlatform(value ?? "youtube")}
              >
                <SelectTrigger className="w-full flex-1">
                  <SelectValue>
                    {(value: unknown) =>
                      typeof value === "string" && value.length > 0 ? (
                        <span className="flex items-center gap-2">
                          <PlatformLogo platform={value} size={14} />
                          {platformLabel(value)}
                        </span>
                      ) : (
                        ""
                      )
                    }
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {PLATFORM_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      <span className="flex items-center gap-2">
                        <PlatformLogo platform={option.value} size={14} />
                        {option.label}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </div>

          {editing && schedule?.publishId ? (
            <p className="text-xs text-muted-foreground">
              Linked upload
              {schedule.connectionDisplayName
                ? ` · ${schedule.connectionDisplayName}`
                : ""}
              . Moving this slot changes when the video goes public.
            </p>
          ) : null}
          {!editing && initialPublishId ? (
            <p className="text-xs text-muted-foreground">
              Linked to the upload below. Saving changes when the video goes
              public.
            </p>
          ) : null}
          {!editing && !initialPublishId ? (
            <p className="text-xs text-muted-foreground">
              {platform.trim() === "youtube"
                ? "Saving uploads the video and schedules it to go public at the chosen time."
                : "Plan only. This will not publish automatically."}
            </p>
          ) : null}

          <Field>
            <FieldLabel htmlFor="schedule-notes">Notes</FieldLabel>
            <Textarea
              id="schedule-notes"
              value={notes}
              rows={2}
              maxLength={2000}
              onChange={(event) => setNotes(event.target.value)}
            />
          </Field>

          {error ? <FieldError>{error}</FieldError> : null}
        </FieldGroup>

        <DialogFooter className="mt-5 flex-wrap gap-2">
          {editing && schedule ? (
            <div className="mr-auto flex items-center gap-2">
              <Link
                href={workspaceHref(schedule.projectId)}
                className="text-xs text-signal hover:underline"
              >
                Open project
              </Link>
              <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
                <Button
                  type="button"
                  variant={confirmingDelete ? "destructive" : "outline"}
                  size="sm"
                  disabled={busy || readOnly}
                  onClick={() => {
                    if (confirmingDelete) deleteMutation.mutate();
                    else setConfirmingDelete(true);
                  }}
                >
                  <Icon icon={Delete02Icon} />
                  {confirmingDelete ? "Confirm delete" : "Delete"}
                </Button>
              </DisabledReason>
            </div>
          ) : null}
          <DialogClose
            render={<Button type="button" variant="outline" disabled={busy} />}
          >
            Cancel
          </DialogClose>
          <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
            <Button
              type="button"
              disabled={busy || readOnly}
              onClick={() => saveMutation.mutate()}
              className={cn(busy && "opacity-70")}
            >
              <Icon icon={CalendarAdd01Icon} />
              {saveMutation.isPending
                ? "Saving…"
                : editing
                  ? "Save changes"
                  : "Schedule"}
            </Button>
          </DisabledReason>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

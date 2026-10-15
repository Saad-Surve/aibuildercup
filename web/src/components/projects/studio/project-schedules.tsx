"use client";

import { useState } from "react";
import { useViewReconciliation } from "@/hooks/use-view-reconciliation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight01Icon,
  Calendar01Icon,
  CalendarAdd01Icon,
  CloudUploadIcon,
} from "@hugeicons/core-free-icons";
import { format } from "date-fns";

import { Icon } from "@/components/common/icon";
import { PlatformLogo } from "@/components/calendar/platform";
import { ScheduleDialog } from "@/components/calendar/schedule-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { listProjectSchedules } from "@/lib/schedules";
import type { Publish, Schedule } from "@/lib/types";
import { WORKSPACE_SNAP_TARGET } from "@/lib/workspace";
import { cn } from "@/lib/utils";

function statusTone(status: Schedule["status"]): string {
  if (status === "published")
    return "border-sev-good/40 bg-sev-good/10 text-sev-good";
  if (status === "scheduled")
    return "border-signal/40 bg-signal/10 text-foreground";
  if (status === "failed")
    return "border-destructive/40 bg-destructive/10 text-destructive";
  if (status === "cancelled")
    return "border-border bg-muted text-muted-foreground/70";
  return "border-border bg-muted text-muted-foreground";
}

type DialogState =
  | { mode: "create"; publishId?: string; publishTitle?: string }
  | { mode: "edit"; schedule: Schedule };

export function ProjectSchedules({
  projectId,
  projectName,
  publishes,
}: {
  projectId: string;
  projectName: string;
  publishes: Publish[];
}) {
  const [dialog, setDialog] = useState<DialogState | null>(null);

  const reconcileOnView = useViewReconciliation(projectId);
  const schedulesQuery = useQuery({
    queryKey: ["project-schedules", projectId],
    queryFn: () => listProjectSchedules(projectId, reconcileOnView()),
    // Scheduled uploads still need lazy go-live promotion. Planned and published
    // slots are idle; their status is refreshed on view/focus or explicit refresh.
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      const waiting = items.some((item) => item.status === "scheduled");
      return waiting ? 60_000 : false;
    },
  });
  const schedules = schedulesQuery.data?.items ?? [];
  const linkedPublishIds = new Set(
    schedules.map((item) => item.publishId).filter((id) => id !== null),
  );
  const unscheduled = publishes.filter(
    (publish) =>
      !linkedPublishIds.has(publish.publishId) &&
      publish.status !== "published",
  );

  return (
    <Card className={WORKSPACE_SNAP_TARGET}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon icon={Calendar01Icon} className="text-muted-foreground" />
          Posting schedule
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {schedulesQuery.isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-14 rounded-lg" />
            <Skeleton className="h-14 rounded-lg" />
          </div>
        ) : schedules.length === 0 && unscheduled.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Nothing planned yet. Schedule the first slot.
          </p>
        ) : (
          <ul className="space-y-2">
            {schedules.map((item) => (
              <li
                key={item.scheduleId}
                className="flex items-center gap-1 rounded-lg border border-border/60 transition-colors hover:border-border hover:bg-muted/40"
              >
                <button
                  type="button"
                  onClick={() => setDialog({ mode: "edit", schedule: item })}
                  className="flex min-w-0 flex-1 items-center gap-3 p-3 text-left"
                >
                  <PlatformLogo platform={item.platform} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">
                      {item.title}
                    </span>
                    <span className="block text-xs text-muted-foreground tabular-nums">
                      {format(new Date(item.scheduledAt), "d MMM yyyy, HH:mm")}
                      {item.publishId ? " · linked upload" : ""}
                      {item.connectionDisplayName
                        ? ` · ${item.connectionDisplayName}`
                        : ""}
                    </span>
                    {item.statusDetail &&
                    (item.status === "planned" || item.status === "failed") ? (
                      <span className="block truncate text-xs text-destructive">
                        {item.statusDetail}
                      </span>
                    ) : null}
                  </span>
                  <Badge
                    className={cn(
                      "shrink-0 capitalize",
                      statusTone(item.status),
                    )}
                  >
                    {item.status}
                  </Badge>
                </button>
                <Link
                  href={`/calendar?schedule=${item.scheduleId}&date=${format(new Date(item.scheduledAt), "yyyy-MM-dd")}`}
                  aria-label={`View ${item.title} on the calendar`}
                  title="View on calendar"
                  className="mr-2 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  <Icon icon={Calendar01Icon} />
                </Link>
              </li>
            ))}
          </ul>
        )}

        {unscheduled.length > 0 ? (
          <div className="space-y-2 rounded-lg border border-dashed border-border p-3">
            <p className="text-xs font-medium text-muted-foreground">
              Uploads with no slot yet
            </p>
            {unscheduled.map((publish) => (
              <div
                key={publish.publishId}
                className="flex items-center justify-between gap-2"
              >
                <span className="flex min-w-0 items-center gap-2 truncate text-sm">
                  <Icon
                    icon={CloudUploadIcon}
                    className="shrink-0 text-muted-foreground"
                  />
                  <span className="truncate">{publish.title}</span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    · {publish.status}
                  </span>
                </span>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    setDialog({
                      mode: "create",
                      publishId: publish.publishId,
                      publishTitle: publish.title,
                    })
                  }
                >
                  <Icon icon={CalendarAdd01Icon} />
                  Schedule
                </Button>
              </div>
            ))}
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => setDialog({ mode: "create" })}
          >
            <Icon icon={CalendarAdd01Icon} />
            Plan a slot
          </Button>
          <Link
            href="/calendar"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            Open calendar
            <Icon icon={ArrowRight01Icon} />
          </Link>
        </div>
      </CardContent>

      {dialog?.mode === "create" ? (
        <ScheduleDialog
          key={`create-${dialog.publishId ?? "new"}`}
          projectId={projectId}
          projectName={projectName}
          initialPublishId={dialog.publishId}
          initialTitle={dialog.publishTitle}
          open
          onOpenChange={(next) => {
            if (!next) setDialog(null);
          }}
        />
      ) : null}
      {dialog?.mode === "edit" ? (
        <ScheduleDialog
          key={dialog.schedule.scheduleId}
          projectId={projectId}
          schedule={dialog.schedule}
          open
          onOpenChange={(next) => {
            if (!next) setDialog(null);
          }}
        />
      ) : null}
    </Card>
  );
}

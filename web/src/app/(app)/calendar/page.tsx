"use client";

import {
  Suspense,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
} from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft01Icon,
  ArrowRight01Icon,
  Calendar01Icon,
  PlusSignIcon,
} from "@hugeicons/core-free-icons";
import {
  addDays,
  addMonths,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  isSameMonth,
  isToday,
  startOfDay,
  startOfMonth,
  startOfWeek,
} from "date-fns";

import { Icon } from "@/components/common/icon";
import { PageHeader } from "@/components/common/page-header";
import { PlatformLogo } from "@/components/calendar/platform";
import { ScheduleDialog } from "@/components/calendar/schedule-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { listProjects } from "@/lib/projects";
import { listSchedules } from "@/lib/schedules";
import { workspaceHref } from "@/lib/studio";
import type { Schedule, ScheduleStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

type CalendarView = "month" | "week" | "day" | "upcoming";

type DialogState =
  | { mode: "create"; date: Date }
  | { mode: "edit"; schedule: Schedule };

const STATUS_META: Record<
  ScheduleStatus,
  { label: string; dot: string; chip: string; badge: string }
> = {
  planned: {
    label: "Planned",
    dot: "bg-muted-foreground",
    chip: "bg-muted text-muted-foreground hover:bg-muted/70",
    badge: "border-border bg-muted text-muted-foreground",
  },
  scheduled: {
    label: "Scheduled",
    dot: "bg-signal",
    chip: "bg-signal/10 text-foreground hover:bg-signal/20",
    badge: "border-signal/40 bg-signal/10 text-foreground",
  },
  published: {
    label: "Published",
    dot: "bg-sev-good",
    chip: "bg-sev-good/10 text-sev-good hover:bg-sev-good/20",
    badge: "border-sev-good/40 bg-sev-good/10 text-sev-good",
  },
  cancelled: {
    label: "Cancelled",
    dot: "bg-muted-foreground/50",
    chip: "bg-muted text-muted-foreground/70 line-through hover:bg-muted/70",
    badge: "border-border bg-muted text-muted-foreground/70",
  },
};

const FILTERS: { value: ScheduleStatus | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "planned", label: "Planned" },
  { value: "scheduled", label: "Scheduled" },
  { value: "published", label: "Published" },
  { value: "cancelled", label: "Cancelled" },
];

/*
 * Default time for a new slot. A future day keeps the calm 10:00 posting
 * default, but a slot on *today* must never open in the past — round up to the
 * next full hour (22:31 -> 23:00) so the create dialog always starts on a
 * valid, publishable time. Past days stay at 10:00 and are rejected on save.
 */
function at(day: Date): Date {
  const next = new Date(day);
  const now = new Date();
  const onToday =
    next.getFullYear() === now.getFullYear() &&
    next.getMonth() === now.getMonth() &&
    next.getDate() === now.getDate();
  if (onToday) {
    next.setMinutes(0, 0, 0);
    next.setHours(next.getHours() + 1);
  } else {
    next.setHours(10, 0, 0, 0);
  }
  return next;
}

function windowFor(
  view: CalendarView,
  cursor: Date,
): { start: Date; end: Date } {
  if (view === "month") {
    const first = startOfWeek(startOfMonth(cursor), { weekStartsOn: 0 });
    const last = endOfWeek(endOfMonth(cursor), { weekStartsOn: 0 });
    return { start: first, end: last };
  }
  if (view === "week") {
    return {
      start: startOfWeek(cursor, { weekStartsOn: 0 }),
      end: endOfWeek(cursor, { weekStartsOn: 0 }),
    };
  }
  if (view === "upcoming") {
    return { start: startOfDay(cursor), end: addDays(cursor, 90) };
  }
  return { start: startOfDay(cursor), end: startOfDay(cursor) };
}

function titleFor(view: CalendarView, cursor: Date): string {
  if (view === "month") return format(cursor, "MMMM yyyy");
  if (view === "week") {
    const start = startOfWeek(cursor, { weekStartsOn: 0 });
    const end = endOfWeek(cursor, { weekStartsOn: 0 });
    return isSameMonth(start, end)
      ? format(start, "MMMM yyyy")
      : `${format(start, "MMM")} – ${format(end, "MMM yyyy")}`;
  }
  if (view === "upcoming") return "Upcoming";
  return format(cursor, "EEEE, d MMMM yyyy");
}

function stepCursor(view: CalendarView, cursor: Date, delta: number): Date {
  if (view === "month") return addMonths(cursor, delta);
  if (view === "week") return addDays(cursor, delta * 7);
  if (view === "upcoming") return addDays(cursor, delta * 30);
  return addDays(cursor, delta);
}

function EventChip({
  schedule,
  projectName,
  highlighted,
  onOpen,
}: {
  schedule: Schedule;
  projectName: string;
  highlighted: boolean;
  onOpen: () => void;
}) {
  const meta = STATUS_META[schedule.status];
  return (
    <button
      type="button"
      onClick={onOpen}
      title={`${schedule.title} · ${projectName} · ${meta.label}`}
      className={cn(
        "flex w-full items-center gap-1.5 rounded-md px-1.5 py-1 text-left text-xs transition-colors",
        meta.chip,
        highlighted &&
          "ring-2 ring-signal ring-offset-1 ring-offset-background",
      )}
    >
      <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", meta.dot)} />
      <PlatformLogo platform={schedule.platform} size={14} />
      <span className="hidden shrink-0 font-medium tabular-nums xl:inline">
        {format(new Date(schedule.scheduledAt), "HH:mm")}
      </span>
      <span className="min-w-0 flex-1 truncate">{schedule.title}</span>
      <span className="shrink-0 text-[0.6rem] font-medium opacity-70">
        {meta.label}
      </span>
    </button>
  );
}

/* ------------------------------------------------------------------ week grid */

const HOUR_PX = 48;
/** A post is one instant; it occupies this long for overlap layout. */
const SLOT_MINUTES = 30;

function hourLabel(hour: number): string {
  if (hour === 0) return "12am";
  if (hour < 12) return `${hour}am`;
  if (hour === 12) return "12pm";
  return `${hour - 12}pm`;
}

interface PlacedSlot {
  schedule: Schedule;
  top: number;
  height: number;
  leftPct: number;
  widthPct: number;
}

/** Pin each slot to its time, packing overlapping ones into side-by-side lanes. */
function layoutDaySlots(items: Schedule[]): PlacedSlot[] {
  const sorted = [...items].toSorted(
    (a, b) =>
      new Date(a.scheduledAt).getTime() - new Date(b.scheduledAt).getTime(),
  );
  const starts = sorted.map((item) => {
    const instant = new Date(item.scheduledAt);
    return instant.getHours() * 60 + instant.getMinutes();
  });
  const clusters: number[][] = [];
  for (let i = 0; i < sorted.length; i += 1) {
    const current = clusters[clusters.length - 1];
    const clusterEnd =
      current === undefined
        ? -1
        : Math.max(...current.map((j) => starts[j] + SLOT_MINUTES));
    if (current !== undefined && starts[i] < clusterEnd) current.push(i);
    else clusters.push([i]);
  }
  const lanes = Array.from({ length: sorted.length }, () => 0);
  const counts = Array.from({ length: sorted.length }, () => 1);
  for (const members of clusters) {
    const laneEnds: number[] = [];
    for (const i of members) {
      const end = starts[i] + SLOT_MINUTES;
      let lane = laneEnds.findIndex((laneEnd) => laneEnd <= starts[i]);
      if (lane === -1) {
        lane = laneEnds.length;
        laneEnds.push(end);
      } else {
        laneEnds[lane] = end;
      }
      lanes[i] = lane;
    }
    const count = Math.max(laneEnds.length, 1);
    for (const i of members) counts[i] = count;
  }
  const height = (SLOT_MINUTES / 60) * HOUR_PX;
  return sorted.map((schedule, i) => ({
    schedule,
    top: Math.max(0, Math.min((starts[i] / 60) * HOUR_PX, 24 * HOUR_PX - height)),
    height,
    leftPct: (lanes[i] / counts[i]) * 100,
    widthPct: 100 / counts[i],
  }));
}

function WeekTimeGrid({
  weekDays,
  byDay,
  now,
  highlightId,
  nameOf,
  onOpen,
  onCreateAt,
  onDayHeader,
}: {
  weekDays: Date[];
  byDay: Map<string, Schedule[]>;
  now: number;
  highlightId: string | null;
  nameOf: (schedule: Schedule) => string;
  onOpen: (schedule: Schedule) => void;
  onCreateAt: (date: Date) => void;
  onDayHeader: (day: Date) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const hours = useMemo(() => Array.from({ length: 24 }, (_, hour) => hour), []);
  const columns = "3.5rem repeat(7, minmax(0, 1fr))";

  const initialTop = useMemo(() => {
    let earliest = 7 * 60;
    for (const list of byDay.values()) {
      for (const item of list) {
        const instant = new Date(item.scheduledAt);
        earliest = Math.min(
          earliest,
          instant.getHours() * 60 + instant.getMinutes(),
        );
      }
    }
    return Math.max(0, ((earliest - 60) / 60) * HOUR_PX);
  }, [byDay]);

  // Scroll position only — no state involved, so no cascading-render risk.
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: initialTop });
  }, [initialTop]);

  const nowDate = new Date(now);
  const nowTop = ((nowDate.getHours() * 60 + nowDate.getMinutes()) / 60) * HOUR_PX;

  function createAtHour(
    day: Date,
    hour: number,
    event: ReactMouseEvent<HTMLButtonElement>,
  ) {
    // Keyboard activation (detail 0) takes the hour start; a pointer click
    // snaps to the nearest quarter hour within the cell.
    let minutes = hour * 60;
    if (event.detail !== 0) {
      const rect = event.currentTarget.getBoundingClientRect();
      const offset = Math.max(0, Math.min(HOUR_PX, event.clientY - rect.top));
      minutes = hour * 60 + Math.floor((offset / HOUR_PX) * 60 / 15) * 15;
    }
    const next = new Date(day);
    next.setHours(Math.floor(minutes / 60), minutes % 60, 0, 0);
    onCreateAt(next);
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border/60">
      <div
        className="grid border-b border-border/60 bg-muted/30"
        style={{ gridTemplateColumns: columns }}
      >
        <div />
        {weekDays.map((day) => (
          <button
            key={format(day, "yyyy-MM-dd")}
            type="button"
            onClick={() => onDayHeader(day)}
            className="flex flex-col items-center gap-0.5 py-2 transition-colors hover:bg-muted/50"
          >
            <span className="text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
              {format(day, "EEE")}
            </span>
            <span
              className={cn(
                "flex h-7 w-7 items-center justify-center rounded-full text-sm tabular-nums",
                isToday(day)
                  ? "bg-signal font-semibold text-white"
                  : "text-foreground",
              )}
            >
              {format(day, "d")}
            </span>
          </button>
        ))}
      </div>

      <div ref={scrollRef} className="max-h-[560px] overflow-y-auto">
        <div className="grid" style={{ gridTemplateColumns: columns }}>
          <div>
            {hours.map((hour) => (
              <div key={hour} className="relative" style={{ height: HOUR_PX }}>
                {hour === 0 ? null : (
                  <span className="absolute -top-2 right-2 text-[10px] tabular-nums text-muted-foreground">
                    {hourLabel(hour)}
                  </span>
                )}
              </div>
            ))}
          </div>

          {weekDays.map((day) => {
            const key = format(day, "yyyy-MM-dd");
            const slots = layoutDaySlots(byDay.get(key) ?? []);
            const showNow = isToday(day);
            return (
              <div
                key={key}
                className={cn(
                  "relative border-l border-border/60 first:border-l-0",
                  showNow && "bg-signal/[0.04]",
                )}
              >
                {hours.map((hour) => (
                  <button
                    key={hour}
                    type="button"
                    aria-label={`Schedule on ${format(day, "d MMM")} at ${hourLabel(hour)}`}
                    onClick={(event) => createAtHour(day, hour, event)}
                    className="block w-full border-t border-border/40 first:border-t-0 hover:bg-signal/5 focus-visible:bg-signal/5 focus-visible:outline-none"
                    style={{ height: HOUR_PX }}
                  />
                ))}
                {showNow ? (
                  <div
                    aria-hidden
                    className="pointer-events-none absolute inset-x-0 z-10"
                    style={{ top: nowTop }}
                  >
                    <div className="h-0.5 rounded bg-red-500" />
                  </div>
                ) : null}
                {slots.map((slot) => {
                  const meta = STATUS_META[slot.schedule.status];
                  return (
                    <button
                      key={slot.schedule.scheduleId}
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        onOpen(slot.schedule);
                      }}
                      title={`${slot.schedule.title} · ${nameOf(slot.schedule)} · ${format(new Date(slot.schedule.scheduledAt), "HH:mm")} · ${meta.label}`}
                      className={cn(
                        "absolute z-20 flex items-center gap-1 overflow-hidden rounded-md px-1 text-left text-[11px] leading-none transition-colors",
                        meta.chip,
                        slot.schedule.scheduleId === highlightId &&
                          "ring-2 ring-signal ring-offset-1 ring-offset-background",
                      )}
                      style={{
                        top: slot.top,
                        height: slot.height,
                        left: `calc(${slot.leftPct}% + 1px)`,
                        width: `calc(${slot.widthPct}% - 2px)`,
                      }}
                    >
                      <span className="shrink-0 font-medium tabular-nums">
                        {format(new Date(slot.schedule.scheduledAt), "HH:mm")}
                      </span>
                      <PlatformLogo platform={slot.schedule.platform} size={12} />
                      <span className="min-w-0 flex-1 truncate">
                        {slot.schedule.title}
                      </span>
                      <span className="shrink-0 font-medium opacity-70">
                        {meta.label}
                      </span>
                    </button>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function CalendarInner() {
  const searchParams = useSearchParams();
  // Deep links (/calendar?schedule=<id>&date=YYYY-MM-DD) are read during render,
  // the same way the project workspace reads its route — no sync effect.
  const scheduleParam = searchParams.get("schedule");
  const dateParam = searchParams.get("date");
  const [view, setView] = useState<CalendarView>("month");
  const [cursor, setCursor] = useState(() => {
    if (dateParam) {
      const parsed = new Date(`${dateParam}T00:00:00`);
      if (!Number.isNaN(parsed.getTime())) return parsed;
    }
    return new Date();
  });
  const [filter, setFilter] = useState<ScheduleStatus | "all">("all");
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const [linkDismissed, setLinkDismissed] = useState(false);
  const [now] = useState(() => Date.now());

  const window = useMemo(() => windowFor(view, cursor), [view, cursor]);
  const startISO = useMemo(
    () => startOfDay(window.start).toISOString(),
    [window],
  );
  const endISO = useMemo(
    () => addDays(startOfDay(window.end), 1).toISOString(),
    [window],
  );

  const schedulesQuery = useQuery({
    queryKey: ["schedules", startISO, endISO],
    queryFn: () => listSchedules({ start: startISO, end: endISO }),
    // While any slot is still waiting to go live, poll so a scheduled upload's
    // status flips in place once its go-public time passes (the backend promotes
    // it lazily when publishes are read).
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      // Keep polling unless every slot is terminal, so a scheduled upload's
      // status flips here at go-live and a YouTube deletion flips it to
      // cancelled.
      const waiting = items.some((item) => item.status !== "cancelled");
      return waiting ? 60_000 : false;
    },
  });
  const projectsQuery = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
  });

  const all = useMemo(
    () => schedulesQuery.data?.items ?? [],
    [schedulesQuery.data],
  );
  const schedules = useMemo(
    () =>
      filter === "all" ? all : all.filter((item) => item.status === filter),
    [all, filter],
  );
  const projectNames = useMemo(() => {
    const map = new Map<string, string>();
    for (const project of projectsQuery.data?.items ?? []) {
      map.set(project.projectId, project.name);
    }
    return map;
  }, [projectsQuery.data]);
  function nameOf(schedule: Schedule): string {
    return (
      projectNames.get(schedule.projectId) ?? schedule.projectName ?? "Project"
    );
  }

  const byDay = useMemo(() => {
    const map = new Map<string, Schedule[]>();
    for (const item of schedules) {
      const key = format(new Date(item.scheduledAt), "yyyy-MM-dd");
      const list = map.get(key) ?? [];
      list.push(item);
      map.set(key, list);
    }
    for (const list of map.values()) {
      list.sort(
        (a, b) =>
          new Date(a.scheduledAt).getTime() - new Date(b.scheduledAt).getTime(),
      );
    }
    return map;
  }, [schedules]);

  const counts = useMemo(() => {
    const result: Record<ScheduleStatus, number> = {
      planned: 0,
      scheduled: 0,
      published: 0,
      cancelled: 0,
    };
    for (const item of all) result[item.status] += 1;
    return result;
  }, [all]);

  const upcoming = useMemo(() => {
    return all
      .filter(
        (item) =>
          item.status !== "cancelled" &&
          new Date(item.scheduledAt).getTime() >= now - 24 * 3600 * 1000,
      )
      .toSorted(
        (a, b) =>
          new Date(a.scheduledAt).getTime() - new Date(b.scheduledAt).getTime(),
      );
  }, [all, now]);

  // A linked slot opens itself once its data arrives; closing it dismisses the
  // link for this visit. Derived during render — no effect needed.
  const linkedSchedule =
    scheduleParam !== null && dialog === null && !linkDismissed
      ? all.find((item) => item.scheduleId === scheduleParam)
      : undefined;

  const days = useMemo(() => {
    if (view === "month") {
      const first = startOfWeek(startOfMonth(cursor), { weekStartsOn: 0 });
      const last = endOfWeek(endOfMonth(cursor), { weekStartsOn: 0 });
      return eachDayOfInterval({ start: first, end: last });
    }
    if (view === "week") {
      const start = startOfWeek(cursor, { weekStartsOn: 0 });
      return eachDayOfInterval({ start, end: addDays(start, 6) });
    }
    return [startOfDay(cursor)];
  }, [view, cursor]);

  const highlightId = scheduleParam;
  const dialogOpen = dialog !== null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Content calendar"
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center rounded-lg border border-border p-0.5">
              {(["month", "week", "day", "upcoming"] as CalendarView[]).map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => setView(option)}
                  aria-pressed={view === option}
                  className={cn(
                    "rounded-md px-3 py-1.5 text-sm capitalize transition-colors",
                    view === option
                      ? "bg-signal/10 font-medium text-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {option}
                </button>
              ))}
            </div>
            <Button
              type="button"
              onClick={() =>
                setDialog({ mode: "create", date: at(new Date()) })
              }
            >
              <Icon icon={PlusSignIcon} />
              Schedule
            </Button>
          </div>
        }
      />

      <div>
        <Card>
          <CardContent className="space-y-4 p-4 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-1">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Previous"
                  onClick={() =>
                    setCursor((current) => stepCursor(view, current, -1))
                  }
                >
                  <Icon icon={ArrowLeft01Icon} />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => setCursor(new Date())}
                >
                  Today
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Next"
                  onClick={() =>
                    setCursor((current) => stepCursor(view, current, 1))
                  }
                >
                  <Icon icon={ArrowRight01Icon} />
                </Button>
              </div>
              <h2 className="font-heading text-base font-medium">
                {titleFor(view, cursor)}
              </h2>
              <p className="text-xs text-muted-foreground tabular-nums">
                {all.length} slot{all.length === 1 ? "" : "s"} ·{" "}
                {counts.scheduled} scheduled
              </p>
            </div>

            <div className="flex flex-wrap gap-1.5">
              {FILTERS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setFilter(option.value)}
                  aria-pressed={filter === option.value}
                  className={cn(
                    "rounded-full border px-2.5 py-1 text-xs transition-colors",
                    filter === option.value
                      ? "border-signal/50 bg-signal/10 font-medium text-foreground"
                      : "border-border text-muted-foreground hover:text-foreground",
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>

            {schedulesQuery.isLoading ? (
              <div className="grid grid-cols-7 gap-1.5">
                {Array.from({ length: 35 }, (_, index) => (
                  <Skeleton key={index} className="h-24 rounded-lg" />
                ))}
              </div>
            ) : view === "upcoming" ? (
              <div>
                {upcoming.length === 0 ? (
                  <p className="py-10 text-center text-sm text-muted-foreground">
                    Nothing coming up. Schedule a slot to see it here.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {upcoming.map((item) => {
                      const meta = STATUS_META[item.status];
                      return (
                        <li key={item.scheduleId}>
                          <button
                            type="button"
                            onClick={() =>
                              setDialog({ mode: "edit", schedule: item })
                            }
                            className="flex w-full items-center gap-3 rounded-lg border border-border/60 p-3 text-left transition-colors hover:border-border hover:bg-muted/40"
                          >
                            <span
                              className={cn(
                                "h-2 w-2 shrink-0 rounded-full",
                                meta.dot,
                              )}
                            />
                            <PlatformLogo platform={item.platform} />
                            <span className="min-w-0 flex-1">
                              <span className="block truncate text-sm font-medium">
                                {item.title}
                              </span>
                              <span className="block truncate text-xs text-muted-foreground">
                                {nameOf(item)} ·{" "}
                                {format(
                                  new Date(item.scheduledAt),
                                  "EEE d MMM, HH:mm",
                                )}
                              </span>
                            </span>
                            <Badge className={cn("shrink-0", meta.badge)}>
                              {meta.label}
                            </Badge>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            ) : view === "day" ? (
              <DayAgenda
                day={days[0]}
                items={byDay.get(format(days[0], "yyyy-MM-dd")) ?? []}
                nameOf={nameOf}
                onCreate={(date) =>
                  setDialog({ mode: "create", date: at(date) })
                }
                onOpen={(schedule) => setDialog({ mode: "edit", schedule })}
              />
            ) : view === "week" ? (
              <WeekTimeGrid
                weekDays={days}
                byDay={byDay}
                now={now}
                highlightId={highlightId}
                nameOf={nameOf}
                onOpen={(schedule) => setDialog({ mode: "edit", schedule })}
                onCreateAt={(date) => setDialog({ mode: "create", date })}
                onDayHeader={(day) => {
                  setCursor(day);
                  setView("day");
                }}
              />
            ) : (
              <div>
                <div className="grid grid-cols-7 gap-1.5">
                  {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map(
                    (label) => (
                      <p
                        key={label}
                        className="pb-1 text-center text-xs font-medium text-muted-foreground"
                      >
                        {label}
                      </p>
                    ),
                  )}
                </div>
                <div className="grid grid-cols-7 gap-1.5">
                  {days.map((day) => {
                    const key = format(day, "yyyy-MM-dd");
                    const items = byDay.get(key) ?? [];
                    const inMonth = isSameMonth(day, cursor);
                    const visible = items.slice(0, 3);
                    return (
                      <div
                        key={key}
                        className={cn(
                          "min-h-24 rounded-lg border p-1.5 transition-colors",
                          isToday(day)
                            ? "border-signal/50 bg-signal/5"
                            : "border-border/60 hover:border-border",
                          !inMonth && "opacity-40",
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <button
                            type="button"
                            onClick={() => {
                              setCursor(day);
                              setView("day");
                            }}
                            className={cn(
                              "flex h-6 w-6 items-center justify-center rounded-full text-xs tabular-nums",
                              isToday(day)
                                ? "bg-signal font-semibold text-white"
                                : "text-muted-foreground hover:bg-muted hover:text-foreground",
                            )}
                          >
                            {format(day, "d")}
                          </button>
                          <button
                            type="button"
                            aria-label={`Schedule on ${format(day, "d MMM yyyy")}`}
                            onClick={() =>
                              setDialog({ mode: "create", date: at(day) })
                            }
                            className="flex h-6 w-6 items-center justify-center rounded-full text-muted-foreground opacity-0 transition-opacity hover:bg-muted hover:text-foreground focus-visible:opacity-100 group-hover:opacity-100 [.min-h-24:hover_&]:opacity-100"
                          >
                            <Icon icon={PlusSignIcon} />
                          </button>
                        </div>
                        <div className="mt-1 space-y-1">
                          {visible.map((item) => (
                            <EventChip
                              key={item.scheduleId}
                              schedule={item}
                              projectName={nameOf(item)}
                              highlighted={item.scheduleId === highlightId}
                              onOpen={() =>
                                setDialog({ mode: "edit", schedule: item })
                              }
                            />
                          ))}
                          {items.length > visible.length ? (
                            <button
                              type="button"
                              onClick={() => {
                                setCursor(day);
                                setView("day");
                              }}
                              className="w-full truncate rounded-md px-1.5 py-1 text-left text-xs text-muted-foreground hover:bg-muted hover:text-foreground"
                            >
                              +{items.length - visible.length} more
                            </button>
                          ) : null}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {!schedulesQuery.isLoading && all.length === 0 ? (
              <Empty className="border border-dashed py-12">
                <EmptyHeader>
                  <EmptyMedia variant="icon">
                    <Icon icon={Calendar01Icon} />
                  </EmptyMedia>
                  <EmptyTitle>Nothing on the calendar</EmptyTitle>
                </EmptyHeader>
              </Empty>
            ) : null}
          </CardContent>
        </Card>
      </div>

      {dialog?.mode === "create" ? (
        <ScheduleDialog
          key={`create-${dialog.date.getTime()}`}
          initialDate={dialog.date}
          createUpload
          open={dialogOpen}
          onOpenChange={(next) => {
            if (!next) setDialog(null);
          }}
        />
      ) : null}
      {dialog?.mode === "edit" ? (
        <ScheduleDialog
          key={dialog.schedule.scheduleId}
          schedule={dialog.schedule}
          open={dialogOpen}
          onOpenChange={(next) => {
            if (!next) setDialog(null);
          }}
        />
      ) : null}
      {linkedSchedule ? (
        <ScheduleDialog
          key={linkedSchedule.scheduleId}
          schedule={linkedSchedule}
          open
          onOpenChange={(next) => {
            if (!next) setLinkDismissed(true);
          }}
        />
      ) : null}
    </div>
  );
}

function DayAgenda({
  day,
  items,
  nameOf,
  onCreate,
  onOpen,
}: {
  day: Date;
  items: Schedule[];
  nameOf: (schedule: Schedule) => string;
  onCreate: (date: Date) => void;
  onOpen: (schedule: Schedule) => void;
}) {
  if (items.length === 0) {
    return (
      <Empty className="border border-dashed py-12">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <Icon icon={Calendar01Icon} />
          </EmptyMedia>
          <EmptyTitle>{format(day, "EEEE, d MMMM")} is wide open</EmptyTitle>
        </EmptyHeader>
        <div className="mt-4 flex justify-center">
          <Button type="button" onClick={() => onCreate(day)}>
            <Icon icon={PlusSignIcon} />
            Schedule for this day
          </Button>
        </div>
      </Empty>
    );
  }
  return (
    <div className="space-y-2">
      {items.map((item) => {
        const meta = STATUS_META[item.status];
        return (
          <button
            key={item.scheduleId}
            type="button"
            onClick={() => onOpen(item)}
            className="flex w-full items-start gap-3 rounded-lg border border-border/60 p-3 text-left transition-colors hover:border-border hover:bg-muted/40"
          >
            <span className="w-12 shrink-0 pt-0.5 text-sm font-medium tabular-nums">
              {format(new Date(item.scheduledAt), "HH:mm")}
            </span>
            <span
              className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", meta.dot)}
            />
            <PlatformLogo platform={item.platform} className="mt-1" />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-medium">
                {item.title}
              </span>
              <Link
                href={workspaceHref(item.projectId)}
                onClick={(event) => event.stopPropagation()}
                className="block w-fit truncate text-xs text-signal hover:underline"
              >
                {nameOf(item)}
              </Link>
              {item.notes ? (
                <span className="mt-0.5 block truncate text-xs text-muted-foreground">
                  {item.notes}
                </span>
              ) : null}
              {item.publishId ? (
                <span className="mt-0.5 block text-xs text-muted-foreground">
                  Linked upload
                  {item.connectionDisplayName
                    ? ` · ${item.connectionDisplayName}`
                    : ""}
                </span>
              ) : null}
            </span>
            <Badge className={cn("shrink-0", meta.badge)}>{meta.label}</Badge>
          </button>
        );
      })}
      <Button
        type="button"
        variant="outline"
        className="w-full"
        onClick={() => onCreate(day)}
      >
        <Icon icon={PlusSignIcon} />
        Add another slot
      </Button>
    </div>
  );
}

export default function CalendarPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-6xl space-y-6">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-96 w-full rounded-xl" />
        </div>
      }
    >
      <CalendarInner />
    </Suspense>
  );
}

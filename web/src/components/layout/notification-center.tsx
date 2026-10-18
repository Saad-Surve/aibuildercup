"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQueryClient, type QueryClient } from "@tanstack/react-query";
import {
  Calendar01Icon,
  Cancel01Icon,
  CheckmarkCircle01Icon,
  CloudUploadIcon,
  Delete02Icon,
  FileVideoIcon,
  Notification01Icon,
  Tick01Icon,
  TickDouble01Icon,
} from "@hugeicons/core-free-icons";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/auth-provider";
import { Icon } from "@/components/common/icon";
import { Button } from "@/components/ui/button";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import type { listAnalysisRuns } from "@/lib/analysis";
import type { listLocalizations } from "@/lib/dubbing";
import {
  clearNotifications,
  dismissNotification,
  markAllNotificationsRead,
  markNotificationRead,
  notificationTone,
  onNotificationCenterOpen,
  onNotificationPushed,
  openNotificationCenter,
  pushNotification,
  setNotificationScope,
  useNotifications,
  useUnreadCount,
  type AppNotification,
  type NotificationKind,
} from "@/lib/notifications";
import type { listCaptionRenders, listProjects } from "@/lib/projects";
import type { listPublishes } from "@/lib/publishes";
import type { listSchedules } from "@/lib/schedules";
import { useNotificationEvents } from "@/hooks/use-notification-events";
import { workspaceHref } from "@/lib/studio";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ watcher */

/** Last-seen entity states, so the watcher only notifies on transitions. */
interface SeenSnapshot {
  projects: Record<string, { status: string; stage: string | null }>;
  publishes: Record<string, string>;
  schedules: Record<string, string>;
  renders: Record<string, string>;
  dubs: Record<string, string>;
  analyses: Record<string, string>;
  reminded: Record<string, true>;
}

const EMPTY_SNAPSHOT: SeenSnapshot = {
  projects: {},
  publishes: {},
  schedules: {},
  renders: {},
  dubs: {},
  analyses: {},
  reminded: {},
};

function seenKey(uid: string): string {
  return `hc-notify-seen-v1:${uid}`;
}

function readSeen(uid: string): { snapshot: SeenSnapshot; baseline: boolean } {
  try {
    const raw = window.localStorage.getItem(seenKey(uid));
    if (!raw)
      return { snapshot: structuredClone(EMPTY_SNAPSHOT), baseline: true };
    const parsed = JSON.parse(raw) as Partial<SeenSnapshot>;
    return {
      snapshot: { ...structuredClone(EMPTY_SNAPSHOT), ...parsed },
      baseline: false,
    };
  } catch {
    return { snapshot: structuredClone(EMPTY_SNAPSHOT), baseline: true };
  }
}

function writeSeen(uid: string, snapshot: SeenSnapshot): void {
  try {
    window.localStorage.setItem(seenKey(uid), JSON.stringify(snapshot));
  } catch {
    // Private mode: transitions are still detected for this session.
  }
}

function recentlyUpdated(
  value: string | null | undefined,
  hours = 24,
): boolean {
  if (!value) return false;
  const when = new Date(value).getTime();
  if (Number.isNaN(when)) return false;
  return Date.now() - when < hours * 3600 * 1000;
}

const UPCOMING_MS = 60 * 60 * 1000;
const MAX_NEW_PER_POLL = 8;

interface Pending {
  id: string;
  recent: boolean;
  push: () => void;
}

/**
 * Observes the shared query cache (including realtime updates) and records a notification when
 * something transitions into a terminal state: transcription finished/failed,
 * an upload published/failed, a scheduled slot went live, a caption render or
 * dub finished, an analysis run completed. A schedule starting within the hour
 * produces a one-time "going public soon" reminder.
 *
 * On the very first run there is no baseline, so only recently-updated terminal
 * items notify (a returning creator still learns what finished while away)
 * and everything else is recorded silently. No notification scan fetches data.
 * Off-page results appear when the corresponding data is next observed by the app.
 */
async function pollOnce(uid: string, client: QueryClient): Promise<void> {
  const { snapshot: seen, baseline } = readSeen(uid);
  const pending: Pending[] = [];
  function consider(
    id: string,
    recent: boolean,
    push: () => void,
    fresh: boolean,
  ): void {
    // A genuinely new transition always notifies; a baseline item only when
    // it finished recently (and the poll still caps the burst).
    if (fresh || recent) {
      pending.push({ id, recent, push });
    }
  }

  let projects: Awaited<ReturnType<typeof listProjects>>["items"] = [];
  try {
    projects =
      client.getQueryData<Awaited<ReturnType<typeof listProjects>>>([
        "projects",
      ])?.items ?? [];
    const known = new Map(
      projects.map((project) => [project.projectId, project]),
    );
    for (const [, project] of client.getQueriesData<(typeof projects)[number]>({
      queryKey: ["project"],
    })) {
      if (project) known.set(project.projectId, project);
    }
    projects = [...known.values()];
  } catch {
    return; // Offline or signed out mid-poll: try again next round.
  }
  if (projects.length === 0) return;
  const names = new Map(projects.map((p) => [p.projectId, p.name]));

  for (const project of projects) {
    const prev = seen.projects[project.projectId];
    const stage = project.progress?.stage ?? null;
    if (!prev) {
      if (project.status === "ready" || project.status === "failed") {
        consider(
          `project:${project.projectId}:${project.status}`,
          recentlyUpdated(project.updatedAt),
          () =>
            pushNotification({
              id: `project:${project.projectId}:${project.status}`,
              kind: "transcription",
              title:
                project.status === "ready"
                  ? `Transcript ready · ${project.name}`
                  : `Processing failed · ${project.name}`,
              body:
                project.status === "ready"
                  ? "Open the project to read and edit your transcript."
                  : (project.progress?.message ??
                    "Check the project for details."),
              href: workspaceHref(project.projectId),
            }),
          false,
        );
      }
    } else if (prev.status !== project.status) {
      if (project.status === "ready") {
        consider(
          `project:${project.projectId}:ready:${project.updatedAt}`,
          true,
          () =>
            pushNotification({
              id: `project:${project.projectId}:ready:${project.updatedAt}`,
              kind: "transcription",
              title: `Transcript ready · ${project.name}`,
              body: "Open the project to read and edit your transcript.",
              href: workspaceHref(project.projectId),
            }),
          true,
        );
      } else if (
        project.status === "failed" ||
        project.status === "partial_failure"
      ) {
        consider(
          `project:${project.projectId}:${project.status}:${project.updatedAt}`,
          true,
          () =>
            pushNotification({
              id: `project:${project.projectId}:${project.status}:${project.updatedAt}`,
              kind: "transcription",
              title: `Processing failed · ${project.name}`,
              body:
                project.progress?.message ?? "Check the project for details.",
              href: workspaceHref(project.projectId),
            }),
          true,
        );
      }
    }
    seen.projects[project.projectId] = { status: project.status, stage };
  }

  for (const project of projects) {
    const publishes = client.getQueryData<
      Awaited<ReturnType<typeof listPublishes>>
    >(["publishes", project.projectId]) ?? { items: [] };
    const renders = client.getQueryData<
      Awaited<ReturnType<typeof listCaptionRenders>>
    >(["caption-renders", project.projectId]) ?? { items: [] };
    const dubs = client.getQueryData<
      Awaited<ReturnType<typeof listLocalizations>>
    >(["localizations", project.projectId]) ?? { items: [] };
    const analyses = client.getQueryData<
      Awaited<ReturnType<typeof listAnalysisRuns>>
    >(["analysis-runs", project.projectId]) ?? { items: [] };

    for (const publish of publishes.items) {
      const prev = seen.publishes[publish.publishId];
      seen.publishes[publish.publishId] = publish.status;
      if (publish.status !== "published" && publish.status !== "failed")
        continue;
      if (prev === publish.status) continue;
      consider(
        `publish:${publish.publishId}:${publish.status}`,
        recentlyUpdated(publish.updatedAt),
        () =>
          pushNotification({
            id: `publish:${publish.publishId}:${publish.status}`,
            kind: "publish",
            title:
              publish.status === "published"
                ? `“${publish.title}” is live on YouTube`
                : `“${publish.title}” failed to upload`,
            body:
              publish.status === "published"
                ? `${project.name}${publish.publishAt ? ` · went public ${new Date(publish.publishAt).toLocaleString()}` : ""}`
                : (publish.error?.message ?? "Open the project to retry."),
            href: workspaceHref(project.projectId),
          }),
        prev !== undefined,
      );
    }

    for (const render of renders.items) {
      const prev = seen.renders[render.captionRenderId];
      seen.renders[render.captionRenderId] = render.status;
      if (render.status !== "ready" && render.status !== "failed") continue;
      if (prev === render.status) continue;
      consider(
        `render:${render.captionRenderId}:${render.status}`,
        recentlyUpdated(render.createdAt),
        () =>
          pushNotification({
            id: `render:${render.captionRenderId}:${render.status}`,
            kind: "caption",
            title:
              render.status === "ready"
                ? `Captioned video ready in “${project.name}”`
                : `Caption render failed in “${project.name}”`,
            body: null,
            href: workspaceHref(project.projectId),
          }),
        prev !== undefined,
      );
    }

    for (const dub of dubs.items) {
      const prev = seen.dubs[dub.localizationId];
      seen.dubs[dub.localizationId] = dub.status;
      if (dub.status !== "ready" && dub.status !== "failed") continue;
      if (prev === dub.status) continue;
      consider(
        `dub:${dub.localizationId}:${dub.status}`,
        recentlyUpdated(dub.createdAt),
        () =>
          pushNotification({
            id: `dub:${dub.localizationId}:${dub.status}`,
            kind: "dub",
            title:
              dub.status === "ready"
                ? `Dub ready in “${project.name}”`
                : `Dub failed in “${project.name}”`,
            body: null,
            href: workspaceHref(project.projectId),
          }),
        prev !== undefined,
      );
    }

    const runs = analyses.items.slice(0, 5);
    for (const run of runs) {
      const prev = seen.analyses[run.analysisRunId];
      seen.analyses[run.analysisRunId] = run.status;
      if (run.status !== "ready" && run.status !== "failed") continue;
      if (prev === run.status) continue;
      consider(
        `analysis:${run.analysisRunId}:${run.status}`,
        recentlyUpdated(run.createdAt),
        () =>
          pushNotification({
            id: `analysis:${run.analysisRunId}:${run.status}`,
            kind: "transcription",
            title:
              run.status === "ready"
                ? `Review ready for “${project.name}”`
                : `Review failed for “${project.name}”`,
            body:
              run.status === "ready" && run.overallScore != null
                ? `Overall score ${run.overallScore.toFixed(1)}.`
                : null,
            href: workspaceHref(project.projectId),
          }),
        prev !== undefined,
      );
    }
  }

  try {
    const now = Date.now();
    const schedules = [
      ...new Map(
        [
          ...client.getQueriesData<Awaited<ReturnType<typeof listSchedules>>>({
            queryKey: ["schedules"],
          }),
          ...client.getQueriesData<Awaited<ReturnType<typeof listSchedules>>>({
            queryKey: ["project-schedules"],
          }),
        ]
          .flatMap(([, data]) => data?.items ?? [])
          .map((schedule) => [schedule.scheduleId, schedule]),
      ).values(),
    ];
    for (const schedule of schedules) {
      const prev = seen.schedules[schedule.scheduleId];
      seen.schedules[schedule.scheduleId] = schedule.status;
      if (schedule.status === "published" && prev !== "published") {
        consider(
          `schedule:${schedule.scheduleId}:published`,
          recentlyUpdated(schedule.updatedAt),
          () =>
            pushNotification({
              id: `schedule:${schedule.scheduleId}:published`,
              kind: "schedule",
              title: `“${schedule.title}” went live`,
              body: names.get(schedule.projectId) ?? schedule.projectName,
              href: "/calendar",
            }),
          prev !== undefined,
        );
        continue;
      }
      if (schedule.status === "failed" && prev !== "failed") {
        consider(
          `schedule:${schedule.scheduleId}:failed`,
          recentlyUpdated(schedule.updatedAt),
          () =>
            pushNotification({
              id: `schedule:${schedule.scheduleId}:failed`,
              kind: "schedule",
              title: `“${schedule.title}” couldn't go live`,
              body: schedule.statusDetail ?? "Open the calendar for details.",
              href: "/calendar",
            }),
          prev !== undefined,
        );
        continue;
      }
      // A planned slot is blocked, not armed: warn about the blocker instead of
      // promising a go-live that is not coming.
      if (schedule.status === "planned") {
        const at = new Date(schedule.scheduledAt).getTime();
        const key = `${schedule.scheduleId}:blocked`;
        if (
          !Number.isNaN(at) &&
          at - now <= UPCOMING_MS &&
          !seen.reminded[key]
        ) {
          seen.reminded[key] = true;
          consider(
            `schedule:${schedule.scheduleId}:blocked`,
            true,
            () =>
              pushNotification({
                id: `schedule:${schedule.scheduleId}:blocked`,
                kind: "schedule",
                title: `“${schedule.title}” is blocked`,
                body: schedule.statusDetail ?? "Open the calendar for details.",
                href: "/calendar",
              }),
            true,
          );
        }
        continue;
      }
      if (
        schedule.status === "scheduled" &&
        !seen.reminded[schedule.scheduleId]
      ) {
        const at = new Date(schedule.scheduledAt).getTime();
        if (!Number.isNaN(at) && at > now && at - now <= UPCOMING_MS) {
          seen.reminded[schedule.scheduleId] = true;
          consider(
            `schedule:${schedule.scheduleId}:upcoming`,
            true,
            () =>
              pushNotification({
                id: `schedule:${schedule.scheduleId}:upcoming`,
                kind: "schedule",
                title: `“${schedule.title}” goes public soon`,
                body: `${new Date(schedule.scheduledAt).toLocaleString()} · ${names.get(schedule.projectId) ?? schedule.projectName ?? "Calendar"}`,
                href: "/calendar",
              }),
            true,
          );
        }
      }
    }
  } catch {
    // Schedules are a bonus signal; publishes already notified the outcome.
  }

  const fresh = pending.filter((item) => item.recent || !baseline);
  for (const item of fresh.slice(0, MAX_NEW_PER_POLL)) item.push();
  writeSeen(uid, seen);
}

/** How long an outcome toast stays up. Failures linger so they are not missed. */
const TOAST_MS = { success: 8000, info: 8000, warning: 12000, error: 15000 };

/**
 * Pops a toast for every newly recorded notification, so a finished job is
 * noticed wherever the creator is. Pushes landing together (one poll can
 * record several) collapse into a single summary toast.
 */
function useNotificationToasts(): void {
  const router = useRouter();
  useEffect(() => {
    let batch: AppNotification[] = [];
    let timer: number | undefined;
    const flush = () => {
      const items = batch;
      batch = [];
      if (items.length === 1) {
        const [item] = items;
        const tone = notificationTone(item);
        const href = item.href;
        toast[tone](item.title, {
          id: item.id,
          description: item.body ?? undefined,
          duration: TOAST_MS[tone],
          closeButton: true,
          action: href
            ? {
                label: "Open",
                onClick: () => {
                  markNotificationRead(item.id);
                  router.push(href);
                },
              }
            : undefined,
        });
        return;
      }
      const failed = items.filter(
        (item) => notificationTone(item) === "error",
      ).length;
      const tone = failed > 0 ? "error" : "success";
      toast[tone](`${items.length} updates`, {
        description:
          items
            .slice(0, 3)
            .map((item) => item.title)
            .join(" · ") + (items.length > 3 ? " …" : ""),
        duration: TOAST_MS[tone],
        closeButton: true,
        action: { label: "View", onClick: () => openNotificationCenter() },
      });
    };
    const unsubscribe = onNotificationPushed((item) => {
      batch.push(item);
      window.clearTimeout(timer);
      timer = window.setTimeout(flush, 300);
    });
    return () => {
      window.clearTimeout(timer);
      unsubscribe();
    };
  }, [router]);
}

export function NotificationWatcher() {
  const client = useQueryClient();
  const { user } = useAuth();
  const uid = user?.uid ?? null;
  useNotificationEvents(uid);
  useNotificationToasts();
  const busy = useRef(false);

  useEffect(() => {
    setNotificationScope(uid);
    if (!uid) return;
    const scope: string = uid;
    let stopped = false;
    async function tick(): Promise<void> {
      if (busy.current || stopped || document.hidden) return;
      busy.current = true;
      try {
        await pollOnce(scope, client);
      } finally {
        busy.current = false;
      }
    }
    const schedule = () => {
      if (!ready || document.hidden) return;
      window.clearTimeout(timer);
      timer = window.setTimeout(() => void tick(), 250);
    };
    let ready = false;
    const begin = () => {
      ready = true;
      schedule();
    };
    let timer = window.setTimeout(begin, 2000);
    const idle = window.requestIdleCallback?.(
      () => {
        window.clearTimeout(timer);
        begin();
      },
      { timeout: 2000 },
    );
    const unsubscribe = client.getQueryCache().subscribe((event) => {
      if (event.type === "updated" && event.action.type === "success")
        schedule();
    });
    document.addEventListener("visibilitychange", schedule);
    const reminders = window.setInterval(schedule, 60_000);
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      if (idle != null) window.cancelIdleCallback(idle);
      window.clearInterval(reminders);
      unsubscribe();
      document.removeEventListener("visibilitychange", schedule);
    };
  }, [uid, client]);

  return null;
}

/* ------------------------------------------------------------------ visuals */

const KIND_ICON: Record<NotificationKind, typeof Notification01Icon> = {
  transcription: FileVideoIcon,
  publish: CloudUploadIcon,
  schedule: Calendar01Icon,
  caption: FileVideoIcon,
  dub: FileVideoIcon,
};

function NotificationRow({ item }: { item: AppNotification }) {
  const unread = item.readAt === null;
  const body = (
    <span className="flex min-w-0 flex-1 items-start gap-3 px-4 py-3 text-left">
      <span
        className={cn(
          "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
          unread
            ? "bg-signal/10 text-signal"
            : "bg-muted text-muted-foreground",
        )}
      >
        <Icon icon={KIND_ICON[item.kind]} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-start gap-2">
          <span className="min-w-0 flex-1 text-sm leading-snug font-medium wrap-break-word">
            {item.title}
          </span>
          {unread ? (
            <span
              aria-label="Unread"
              className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-signal"
            />
          ) : null}
        </span>
        {item.body ? (
          <span className="mt-0.5 block truncate text-xs text-muted-foreground">
            {item.body}
          </span>
        ) : null}
        <span className="mt-1 block text-[11px] text-muted-foreground tabular-nums">
          {formatDistanceToNow(new Date(item.createdAt), { addSuffix: true })}
        </span>
      </span>
    </span>
  );

  return (
    <li
      className={cn(
        "group relative flex items-stretch rounded-xl border transition-colors",
        unread
          ? "border-signal/30 bg-signal/[0.04]"
          : "border-border/60 hover:border-border",
      )}
    >
      {item.href ? (
        <Link
          href={item.href}
          onClick={() => markNotificationRead(item.id)}
          className="flex min-w-0 flex-1 rounded-l-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
        >
          {body}
        </Link>
      ) : (
        <div className="flex min-w-0 flex-1">{body}</div>
      )}
      <span className="flex shrink-0 flex-col items-center justify-center gap-1 pr-2">
        {unread ? (
          <button
            type="button"
            onClick={() => markNotificationRead(item.id)}
            aria-label="Mark as read"
            title="Mark as read"
            className="flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <Icon icon={Tick01Icon} />
          </button>
        ) : null}
        <button
          type="button"
          onClick={() => dismissNotification(item.id)}
          aria-label="Dismiss notification"
          title="Dismiss"
          className="flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <Icon icon={Cancel01Icon} />
        </button>
      </span>
    </li>
  );
}

export function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const [ringing, setRinging] = useState(false);
  const items = useNotifications();
  const unread = useUnreadCount();

  useEffect(() => onNotificationCenterOpen(() => setOpen(true)), []);

  // Ring the bell for a few seconds whenever something new lands.
  useEffect(() => {
    let timer: number | undefined;
    const unsubscribe = onNotificationPushed(() => {
      setRinging(true);
      window.clearTimeout(timer);
      timer = window.setTimeout(() => setRinging(false), 4000);
    });
    return () => {
      window.clearTimeout(timer);
      unsubscribe();
    };
  }, []);

  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label={
          unread > 0 ? `Notifications, ${unread} unread` : "Notifications"
        }
        title="Notifications"
        onClick={() => setOpen((current) => !current)}
        className={cn(
          "relative",
          ringing && "bg-signal/10 text-signal hover:bg-signal/15",
        )}
      >
        <span className={cn("flex", ringing && "bell-ring")}>
          <Icon icon={Notification01Icon} />
        </span>
        {unread > 0 ? (
          <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center">
            {ringing ? (
              <span className="absolute inset-0 animate-ping rounded-full bg-signal opacity-60 motion-reduce:hidden" />
            ) : null}
            <span className="relative flex h-4 min-w-4 items-center justify-center rounded-full bg-signal px-1 text-[10px] leading-none font-semibold text-white tabular-nums">
              {unread > 99 ? "99+" : unread}
            </span>
          </span>
        ) : null}
      </Button>

      <Drawer open={open} modal={false} onOpenChange={setOpen}>
        <DrawerContent aria-label="Notifications" initialFocus={false}>
          <div className="flex items-center gap-2 border-b border-border/60 px-4 py-3">
            <div className="min-w-0 flex-1">
              <h2 className="font-heading text-sm font-medium">
                Notifications
              </h2>
              <p className="text-xs text-muted-foreground tabular-nums">
                {unread > 0
                  ? `${unread} unread`
                  : items.length > 0
                    ? "You're all caught up"
                    : "Nothing yet"}
              </p>
            </div>
            {items.length > 0 ? (
              <>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => markAllNotificationsRead()}
                  disabled={unread === 0}
                  title="Mark all as read"
                >
                  <Icon icon={TickDouble01Icon} />
                  <span className="hidden sm:inline">Mark all read</span>
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => clearNotifications()}
                  title="Clear all notifications"
                >
                  <Icon icon={Delete02Icon} />
                  <span className="hidden sm:inline">Clear all</span>
                </Button>
              </>
            ) : null}
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label="Close notifications"
              onClick={() => setOpen(false)}
            >
              <Icon icon={Cancel01Icon} />
            </Button>
          </div>

          <div className="flex-1 overflow-y-auto p-3">
            {items.length === 0 ? (
              <Empty className="border border-dashed py-12">
                <EmptyHeader>
                  <EmptyMedia variant="icon">
                    <Icon icon={CheckmarkCircle01Icon} />
                  </EmptyMedia>
                  <EmptyTitle>No notifications</EmptyTitle>
                </EmptyHeader>
                <p className="mt-2 text-center text-xs text-muted-foreground">
                  Finished transcriptions, upload results, and upcoming slots
                  will show up here.
                </p>
              </Empty>
            ) : (
              <ul className="space-y-2">
                {items.map((item) => (
                  <NotificationRow key={item.id} item={item} />
                ))}
              </ul>
            )}
          </div>
        </DrawerContent>
      </Drawer>
    </>
  );
}

"use client";

import { API_BASE_URL } from "@/lib/api-base";
import { auth } from "@/lib/firebase";
import type { JobStatus, ProjectStatus } from "@/lib/types";

/*
 * Realtime client for the project WebSocket (`/api/ws`).
 *
 * One socket is shared by every subscriber in the tab. The client connects
 * lazily when the first project is subscribed, reconnects with backoff, and
 * re-subscribes automatically. The token is re-read on every attempt, so a
 * reconnect after an expiry (or a Cloud Run timeout) never needs a page reload.
 *
 * In prod the socket must target the Cloud Run service URL directly: Firebase
 * Hosting rewrites do not proxy WebSocket upgrades. `NEXT_PUBLIC_WS_BASE_URL`
 * supplies it; otherwise we derive the WS origin from the API base, which is
 * correct for local development.
 */

export type RealtimeStatus = "connecting" | "open" | "closed";

export interface RealtimeProjectProgress {
  stage: string | null;
  percent: number;
  message: string | null;
}

export interface RealtimeJobProgress {
  percent: number;
  step: string | null;
  message: string | null;
}

export interface RealtimeJobSnapshot {
  jobId: string;
  type: string;
  status: JobStatus;
  progress: RealtimeJobProgress | null;
  error: Record<string, unknown> | null;
}

export interface RealtimeReviewerStatus {
  dimension: string;
  status: "queued" | "running" | "succeeded" | "failed";
  findingCount: number | null;
  error: string | null;
}

export type RealtimeMessage =
  | {
      type: "snapshot.project";
      projectId: string;
      status: ProjectStatus;
      progress: RealtimeProjectProgress | null;
      job: RealtimeJobSnapshot | null;
    }
  | {
      type: "project.progress";
      projectId: string;
      status: ProjectStatus;
      progress: RealtimeProjectProgress | null;
    }
  | {
      type: "job.progress";
      projectId: string;
      jobId: string;
      jobType: string | null;
      status: JobStatus;
      progress?: RealtimeJobProgress;
      error: Record<string, unknown> | null;
    }
  | {
      type: "transcript.ready";
      projectId: string;
      transcriptId: string;
      jobId: string | null;
      durationMs: number;
      language: string | null;
    }
  | {
      type: "analysis.progress";
      projectId: string;
      analysisRunId: string;
      status: string;
      completedDimensions: string[];
      reviewerStatuses: RealtimeReviewerStatus[];
    }
  | {
      type: "analysis.ready";
      projectId: string;
      analysisRunId: string;
      status: string;
      overallScore: number | null;
      findingCounts: Record<string, number> | null;
    }
  | { type: "error"; code: string; message: string }
  | { type: "ping" }
  | { type: "pong" };

type MessageHandler = (message: RealtimeMessage) => void;
type StatusHandler = (status: RealtimeStatus) => void;

const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS = 15_000;
/** Reconnect before a Firebase token (1h) or Cloud Run socket lifetime expires. */
const MAX_CONNECTION_MS = 45 * 60 * 1_000;
const CLIENT_PING_MS = 25_000;
/** Keep the socket briefly after the last subscriber unmounts (pane switches). */
const IDLE_CLOSE_MS = 30_000;

const projectHandlers = new Map<string, Set<MessageHandler>>();
const statusHandlers = new Set<StatusHandler>();

let socket: WebSocket | null = null;
let connecting = false;
let connectionAttempt = 0;
let status: RealtimeStatus = "closed";
let reconnectAttempt = 0;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let idleTimer: ReturnType<typeof setTimeout> | null = null;
let pingTimer: ReturnType<typeof setInterval> | null = null;
let maxAgeTimer: ReturnType<typeof setTimeout> | null = null;

function setStatus(next: RealtimeStatus): void {
  if (status === next) return;
  status = next;
  for (const handler of statusHandlers) handler(next);
}

function wsUrl(): string {
  const configured = process.env.NEXT_PUBLIC_WS_BASE_URL?.trim();
  const base = configured && configured.length > 0 ? configured : API_BASE_URL;
  const trimmed = base.replace(/\/+$/, "");
  const withPath = trimmed.endsWith("/api/ws")
    ? trimmed
    : trimmed.endsWith("/api")
      ? `${trimmed}/ws`
      : `${trimmed}/api/ws`;
  return withPath.replace(/^https:/, "wss:").replace(/^http:/, "ws:");
}

function send(payload: Record<string, unknown>): void {
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(payload));
  }
}

function subscribeOnSocket(projectId: string): void {
  send({ type: "subscribe.project", projectId });
}

function clearTimers(): void {
  if (reconnectTimer) clearTimeout(reconnectTimer);
  if (idleTimer) clearTimeout(idleTimer);
  if (pingTimer) clearInterval(pingTimer);
  if (maxAgeTimer) clearTimeout(maxAgeTimer);
  reconnectTimer = null;
  idleTimer = null;
  pingTimer = null;
  maxAgeTimer = null;
}

function teardown(): void {
  connectionAttempt += 1;
  connecting = false;
  clearTimers();
  const current = socket;
  // Clear the reference before closing so the close handler's
  // `socket !== next` guard sees a stale socket and skips reconnecting.
  socket = null;
  if (current) {
    try {
      current.close();
    } catch {
      // Already closed.
    }
  }
}

function scheduleReconnect(): void {
  if (reconnectTimer || projectHandlers.size === 0) return;
  if (
    typeof document !== "undefined" &&
    document.visibilityState === "hidden"
  ) {
    // Wait for the tab to come back rather than burning attempts in the
    // background; visibilitychange triggers an immediate reconnect.
    return;
  }
  const backoff = Math.min(
    RECONNECT_MAX_MS,
    RECONNECT_BASE_MS * 2 ** reconnectAttempt,
  );
  const delay = backoff + Math.floor(Math.random() * 500);
  reconnectAttempt += 1;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    void connect();
  }, delay);
}

async function connect(): Promise<void> {
  if (typeof window === "undefined") return;
  if (socket || connecting || projectHandlers.size === 0) return;

  connecting = true;
  const attempt = ++connectionAttempt;

  setStatus("connecting");
  let token: string | undefined;
  try {
    token = await auth.currentUser?.getIdToken();
  } catch {
    token = undefined;
  }
  if (attempt !== connectionAttempt) return;
  connecting = false;
  if (!token) {
    // Signed out or auth not ready yet; retry with backoff.
    setStatus("closed");
    scheduleReconnect();
    return;
  }
  if (projectHandlers.size === 0) {
    setStatus("closed");
    return;
  }

  let next: WebSocket;
  try {
    next = new WebSocket(`${wsUrl()}?token=${encodeURIComponent(token)}`);
  } catch {
    setStatus("closed");
    scheduleReconnect();
    return;
  }
  socket = next;

  next.addEventListener(
    "open",
    () => {
      if (socket !== next) return;
      reconnectAttempt = 0;
      setStatus("open");
      // Re-subscribe everything: a fresh connect replays no server state.
      for (const projectId of projectHandlers.keys())
        subscribeOnSocket(projectId);
      pingTimer = setInterval(() => send({ type: "ping" }), CLIENT_PING_MS);
      maxAgeTimer = setTimeout(() => {
        // Reconnect under a fresh token before the platform/token limits hit.
        teardown();
        setStatus("closed");
        scheduleReconnect();
      }, MAX_CONNECTION_MS);
    },
    { once: true },
  );

  next.addEventListener("message", (event: MessageEvent<string>) => {
    if (socket !== next) return;
    let message: RealtimeMessage;
    try {
      message = JSON.parse(event.data) as RealtimeMessage;
    } catch {
      return; // A malformed frame is not fatal; the next one resyncs.
    }
    if (message.type === "ping") {
      send({ type: "pong" });
      return;
    }
    if (message.type === "pong" || message.type === "error") return;
    const handlers = projectHandlers.get(message.projectId);
    if (!handlers) return;
    for (const handler of handlers) handler(message);
  });

  next.addEventListener(
    "close",
    () => {
      if (socket !== next) return; // A superseded socket; ignore its close.
      teardown();
      setStatus("closed");
      scheduleReconnect();
    },
    { once: true },
  );
  // No error listener: a WebSocket error is always followed by `close`.
}

function ensureConnected(): void {
  if (typeof window === "undefined") return;
  if (socket || reconnectTimer || projectHandlers.size === 0) return;
  void connect();
}

/**
 * Subscribe to realtime frames for one project. Returns an unsubscribe function.
 * Safe under React StrictMode double-effects: subscriptions are refcounted.
 */
export function subscribeProject(
  projectId: string,
  handler: MessageHandler,
): () => void {
  if (idleTimer) {
    clearTimeout(idleTimer);
    idleTimer = null;
  }
  const handlers = projectHandlers.get(projectId) ?? new Set<MessageHandler>();
  const isNew = handlers.size === 0;
  handlers.add(handler);
  projectHandlers.set(projectId, handlers);

  ensureConnected();
  if (isNew && status === "open") subscribeOnSocket(projectId);

  return () => {
    const current = projectHandlers.get(projectId);
    if (!current) return;
    current.delete(handler);
    if (current.size === 0) {
      projectHandlers.delete(projectId);
      send({ type: "unsubscribe.project", projectId });
      if (projectHandlers.size === 0) {
        idleTimer = setTimeout(() => {
          idleTimer = null;
          if (projectHandlers.size === 0) {
            teardown();
            setStatus("closed");
          }
        }, IDLE_CLOSE_MS);
      }
    }
  };
}

/** Observe connection state (for the degraded-mode polling fallback). */
export function onRealtimeStatus(handler: StatusHandler): () => void {
  statusHandlers.add(handler);
  handler(status);
  return () => {
    statusHandlers.delete(handler);
  };
}

/** Current status without subscribing; for non-React reads. */
export function currentRealtimeStatus(): RealtimeStatus {
  return status;
}

if (typeof window !== "undefined") {
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && projectHandlers.size > 0) {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (!socket) void connect();
    }
  });
}

"use client";

import { useSyncExternalStore } from "react";

/*
 * Local notification center.
 *
 * There is no server inbox: the watcher (`NotificationWatcher`, mounted by the
 * app shell) polls the endpoints the app already has (projects, publishes,
 * schedules, caption renders, localizations) and records a notification when
 * something transitions into a terminal state. Items persist per signed-in
 * user in localStorage, so read/dismissed state survives reloads but never
 * leaks across accounts.
 */

export type NotificationKind =
  | "transcription"
  | "publish"
  | "schedule"
  | "caption"
  | "dub";

export interface AppNotification {
  /** Stable dedupe key, e.g. `publish:<id>:published`. */
  id: string;
  kind: NotificationKind;
  title: string;
  body: string | null;
  /** Deep link, e.g. the project workspace. Null for purely informational items. */
  href: string | null;
  createdAt: string;
  readAt: string | null;
}

export interface NotificationInput {
  id: string;
  kind: NotificationKind;
  title: string;
  body?: string | null;
  href?: string | null;
}

const MAX_ITEMS = 100;

function storageKey(uid: string): string {
  return `hc-notifications-v1:${uid}`;
}

function readStored(uid: string): AppNotification[] {
  try {
    const raw = window.localStorage.getItem(storageKey(uid));
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return (parsed as AppNotification[]).filter(
      (item) =>
        item &&
        typeof item.id === "string" &&
        typeof item.title === "string" &&
        typeof item.createdAt === "string",
    );
  } catch {
    return [];
  }
}

const listeners = new Set<() => void>();
let activeUid: string | null = null;
let items: AppNotification[] = [];

function persist(): void {
  if (!activeUid) return;
  try {
    window.localStorage.setItem(storageKey(activeUid), JSON.stringify(items));
  } catch {
    // Private mode: notifications still work for this session.
  }
}

function emit(): void {
  persist();
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function snapshot(): AppNotification[] {
  return items;
}

/** Switch the store to another signed-in user (null on sign out). */
export function setNotificationScope(uid: string | null): void {
  if (uid === activeUid) return;
  activeUid = uid;
  items = uid ? readStored(uid) : [];
  for (const listener of listeners) listener();
}

export function pushNotification(input: NotificationInput): void {
  if (items.some((item) => item.id === input.id)) return;
  const now = new Date().toISOString();
  items = [
    {
      id: input.id,
      kind: input.kind,
      title: input.title,
      body: input.body ?? null,
      href: input.href ?? null,
      createdAt: now,
      readAt: null,
    },
    ...items,
  ].slice(0, MAX_ITEMS);
  emit();
}

export function markNotificationRead(id: string): void {
  let changed = false;
  items = items.map((item) => {
    if (item.id !== id || item.readAt !== null) return item;
    changed = true;
    return { ...item, readAt: new Date().toISOString() };
  });
  if (changed) emit();
}

export function markAllNotificationsRead(): void {
  if (items.every((item) => item.readAt !== null)) return;
  const now = new Date().toISOString();
  items = items.map((item) =>
    item.readAt === null ? { ...item, readAt: now } : item,
  );
  emit();
}

export function dismissNotification(id: string): void {
  const next = items.filter((item) => item.id !== id);
  if (next.length === items.length) return;
  items = next;
  emit();
}

export function clearNotifications(): void {
  if (items.length === 0) return;
  items = [];
  emit();
}

// Keep other tabs in sync.
if (typeof window !== "undefined") {
  window.addEventListener("storage", (event) => {
    if (!activeUid || event.key !== storageKey(activeUid)) return;
    items = readStored(activeUid);
    for (const listener of listeners) listener();
  });
}

export function useNotifications(): AppNotification[] {
  return useSyncExternalStore(subscribe, snapshot, () => []);
}

export function useUnreadCount(): number {
  const all = useNotifications();
  let count = 0;
  for (const item of all) {
    if (item.readAt === null) count += 1;
  }
  return count;
}

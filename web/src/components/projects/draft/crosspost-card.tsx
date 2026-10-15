"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight01Icon, Loading03Icon } from "@hugeicons/core-free-icons";
import { toast } from "sonner";

import { PlatformLogo } from "@/components/calendar/platform";
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
} from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
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
import { ApiError } from "@/lib/api-client";
import { crosspost, listConnections, syncCrosspost } from "@/lib/connections";
import { draftToText } from "@/lib/draft-export";
import { getDraft } from "@/lib/drafts";
import type { CrosspostPlatform, CrosspostResult, Draft } from "@/lib/types";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";
import { cn } from "@/lib/utils";

function describe(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}

const PLATFORM_LABEL: Record<CrosspostPlatform, string> = {
  medium: "Medium",
  substack: "Substack",
  reddit: "Reddit",
};

/**
 * Cross-post the draft's text to a connected writing platform. Synchronous —
 * the result carries the live URL (or the Substack draft URL) directly.
 * The editor pane is the body: this dialog only edits the title and the
 * platform settings, and posts whatever the draft currently holds. A posted
 * Substack draft links back here, so later edits can sync into it.
 * Prefills the title from the draft cache; safe defaults (Medium/Substack
 * drafts, your own Reddit profile) unless the creator opts into public.
 */
export function CrosspostCard({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const readOnly = useReadOnly();
  const [open, setOpen] = useState(false);
  const [platform, setPlatform] = useState<CrosspostPlatform>("medium");
  const [connectionId, setConnectionId] = useState("");
  const [title, setTitle] = useState<string | null>(null);
  const [publishStatus, setPublishStatus] = useState("draft");
  const [substackMode, setSubstackMode] = useState("draft");
  const [audience, setAudience] = useState("everyone");
  const [sendEmail, setSendEmail] = useState(true);
  const [scheduleAt, setScheduleAt] = useState("");
  const [subreddit, setSubreddit] = useState("");
  const [linkUrl, setLinkUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CrosspostResult | null>(null);

  const connectionsQuery = useQuery({
    queryKey: ["connections"],
    queryFn: listConnections,
    enabled: open,
  });
  const connected = (connectionsQuery.data?.items ?? []).filter(
    (connection) => connection.status === "connected",
  );
  // Only destinations the creator actually connected — never the full platform
  // list. Derived during render (not an effect) so a disconnect mid-session
  // immediately narrows the choices without extra state.
  const connectedPlatforms = (
    Object.keys(PLATFORM_LABEL) as CrosspostPlatform[]
  ).filter((value) =>
    connected.some((connection) => connection.platform === value),
  );
  const effectivePlatform = connectedPlatforms.includes(platform)
    ? platform
    : (connectedPlatforms[0] ?? "medium");
  const options = connected.filter(
    (connection) => connection.platform === effectivePlatform,
  );
  const effectiveConnectionId =
    options.length === 1
      ? // Only one account to pick — choose it instead of an empty dropdown.
        options[0].connectionId
      : options.some((item) => item.connectionId === connectionId)
        ? connectionId
        : "";

  // The linked platform draft, if this draft was posted before. Shares the
  // workspace's draft query, so it re-renders when a post records a link.
  const draftQuery = useQuery({
    queryKey: ["draft", projectId],
    queryFn: () => getDraft(projectId),
    enabled: open,
  });
  const linked =
    (draftQuery.data?.linkedPosts ?? []).find(
      (item) => item.platform === effectivePlatform,
    ) ?? null;
  const syncable = linked !== null && effectivePlatform === "substack";

  function content(): { title: string; body: string } {
    const cached = queryClient.getQueryData<Draft>(["draft", projectId]);
    return {
      title: (title ?? cached?.title ?? "").trim(),
      body: cached ? draftToText(cached).trim() : "",
    };
  }

  function prefill() {
    const cached = queryClient.getQueryData<Draft>(["draft", projectId]);
    if (title === null && cached) setTitle(cached.title);
  }

  const postMutation = useMutation({
    mutationFn: () => {
      if (!effectiveConnectionId)
        throw new Error("Pick a connected account first.");
      const { title: finalTitle, body: finalBody } = content();
      if (!finalTitle || !finalBody) {
        throw new Error("Write the draft first — it needs a title and a body.");
      }
      const extra: Record<string, unknown> =
        effectivePlatform === "medium"
          ? { publishStatus }
          : effectivePlatform === "substack"
            ? {
                mode: substackMode,
                audience,
                send: sendEmail,
                scheduleAt: scheduleAt || undefined,
              }
            : {
                subreddit: subreddit.trim() || undefined,
                kind: linkUrl.trim() ? "link" : "self",
                url: linkUrl.trim() || undefined,
              };
      return crosspost(projectId, {
        platform: effectivePlatform,
        connectionId: effectiveConnectionId,
        title: finalTitle,
        body: finalBody,
        options: extra,
      });
    },
    onSuccess: (posted) => {
      setError(null);
      setResult(posted);
      // A Substack draft/schedule records its link on the draft — refetch so
      // the dialog flips to the linked "Sync changes" state.
      void queryClient.invalidateQueries({ queryKey: ["draft", projectId] });
      toast.success(
        posted.status === "draft"
          ? "Saved as a draft on the platform"
          : posted.status === "scheduled"
            ? "Scheduled on the platform"
            : "Published",
      );
    },
    onError: (caught) => setError(describe(caught, "Could not post.")),
  });

  const syncMutation = useMutation({
    mutationFn: () => {
      const { title: finalTitle, body: finalBody } = content();
      if (!finalTitle || !finalBody) {
        throw new Error("Write the draft first — it needs a title and a body.");
      }
      return syncCrosspost(projectId, {
        platform: effectivePlatform,
        title: finalTitle,
        body: finalBody,
      });
    },
    onSuccess: (synced) => {
      setError(null);
      setResult(synced);
      void queryClient.invalidateQueries({ queryKey: ["draft", projectId] });
      toast.success("Substack draft updated");
    },
    onError: (caught) => {
      // A deleted remote draft clears the link server-side — refetch so the
      // dialog falls back to posting fresh.
      void queryClient.invalidateQueries({ queryKey: ["draft", projectId] });
      setError(describe(caught, "Could not sync."));
    },
  });

  if (!open) {
    return (
      <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
        <Button
          type="button"
          variant="outline"
          size="xs"
          disabled={readOnly}
          onClick={() => {
            setOpen(true);
            prefill();
          }}
        >
          Publish this draft
        </Button>
      </DisabledReason>
    );
  }

  const busy = postMutation.isPending || syncMutation.isPending;
  // Linked + staying a draft -> push edits into it. Picking publish/schedule
  // (or any unlinked platform) posts fresh through the normal flow instead.
  const showSync = syncable && substackMode === "draft";

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setOpen(false);
          setError(null);
        }
      }}
    >
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Cross-post this draft</DialogTitle>
          <DialogDescription>
            Sends the text to one of your connected writing platforms. Posts as
            a draft on the platform, or to your own Reddit profile, by default.
          </DialogDescription>
        </DialogHeader>

        {connectionsQuery.isLoading ? (
          <p className="text-sm text-muted-foreground">
            Loading your connected accounts…
          </p>
        ) : connectedPlatforms.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No writing platforms connected yet.{" "}
            <Link href="/settings" className="text-signal hover:underline">
              Connect one in Settings
            </Link>{" "}
            to post this draft.
          </p>
        ) : (
          <>
            <div className="flex flex-wrap gap-1.5">
              {connectedPlatforms.map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => {
                    setPlatform(value);
                    setConnectionId("");
                    setResult(null);
                  }}
                  aria-pressed={effectivePlatform === value}
                  className={cn(
                    "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors",
                    effectivePlatform === value
                      ? "border-signal/50 bg-signal/10 font-medium text-foreground"
                      : "border-border text-muted-foreground hover:text-foreground",
                  )}
                >
                  <PlatformLogo platform={value} size={14} />
                  {PLATFORM_LABEL[value]}
                </button>
              ))}
            </div>
            {syncable && linked?.url ? (
              <p className="text-xs text-muted-foreground">
                Linked to your Substack draft — edits here sync into it.{" "}
                <a
                  href={linked.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-signal hover:underline"
                >
                  Open draft
                </a>
              </p>
            ) : null}

            <FieldGroup>
              <Field>
                <FieldLabel required>Account</FieldLabel>
                <Select
                  value={effectiveConnectionId}
                  onValueChange={(value) => setConnectionId(value ?? "")}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue
                      placeholder={`Pick your ${PLATFORM_LABEL[effectivePlatform]} account`}
                    >
                      {(value: unknown) =>
                        typeof value === "string" && value.length > 0
                          ? (options.find((item) => item.connectionId === value)
                              ?.displayName ?? value)
                          : `Pick your ${PLATFORM_LABEL[effectivePlatform]} account`
                      }
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {options.map((item) => (
                      <SelectItem
                        key={item.connectionId}
                        value={item.connectionId}
                      >
                        {item.displayName}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </Field>

              <Field>
                <FieldLabel htmlFor="crosspost-title" required>
                  Title
                </FieldLabel>
                <Input
                  id="crosspost-title"
                  value={title ?? ""}
                  maxLength={300}
                  onChange={(event) => setTitle(event.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  The text in the editor is what gets{" "}
                  {syncable ? "synced" : "posted"}.
                </p>
              </Field>

              {effectivePlatform === "medium" ? (
                <Field>
                  <FieldLabel>Visibility</FieldLabel>
                  <Select
                    value={publishStatus}
                    onValueChange={(value) =>
                      setPublishStatus(value ?? "draft")
                    }
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="draft">Draft (only you)</SelectItem>
                      <SelectItem value="unlisted">
                        Unlisted (link only)
                      </SelectItem>
                      <SelectItem value="public">Public</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
              ) : null}

              {effectivePlatform === "substack" ? (
                <>
                  <div className="grid grid-cols-2 gap-4">
                    <Field>
                      <FieldLabel>Mode</FieldLabel>
                      <Select
                        value={substackMode}
                        onValueChange={(value) =>
                          setSubstackMode(value ?? "draft")
                        }
                      >
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="draft">Draft</SelectItem>
                          <SelectItem value="publish">Publish now</SelectItem>
                          <SelectItem value="schedule">Schedule</SelectItem>
                        </SelectContent>
                      </Select>
                    </Field>
                    <Field>
                      <FieldLabel>Audience</FieldLabel>
                      <Select
                        value={audience}
                        onValueChange={(value) =>
                          setAudience(value ?? "everyone")
                        }
                      >
                        <SelectTrigger className="w-full">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="everyone">Everyone</SelectItem>
                          <SelectItem value="subscribers_only">
                            Subscribers
                          </SelectItem>
                          <SelectItem value="paid_subscribers_only">
                            Paid
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </Field>
                  </div>
                  {substackMode === "publish" ? (
                    <label className="flex items-start gap-2 text-sm">
                      <Checkbox
                        checked={sendEmail}
                        onCheckedChange={(value) =>
                          setSendEmail(Boolean(value))
                        }
                      />
                      <span>
                        Email subscribers on publish
                        <span className="block text-xs text-muted-foreground">
                          Irreversible once sent.
                        </span>
                      </span>
                    </label>
                  ) : null}
                  {substackMode === "schedule" ? (
                    <Field>
                      <FieldLabel htmlFor="crosspost-schedule" required>
                        Send at (UTC)
                      </FieldLabel>
                      <Input
                        id="crosspost-schedule"
                        type="datetime-local"
                        value={scheduleAt}
                        onChange={(event) => setScheduleAt(event.target.value)}
                      />
                    </Field>
                  ) : null}
                </>
              ) : null}

              {effectivePlatform === "reddit" ? (
                <div className="grid grid-cols-2 gap-4">
                  <Field>
                    <FieldLabel htmlFor="crosspost-subreddit">
                      Subreddit
                    </FieldLabel>
                    <Input
                      id="crosspost-subreddit"
                      value={subreddit}
                      autoComplete="off"
                      placeholder="Blank = your own profile"
                      onChange={(event) => setSubreddit(event.target.value)}
                    />
                  </Field>
                  <Field>
                    <FieldLabel htmlFor="crosspost-url">
                      Link URL (optional)
                    </FieldLabel>
                    <Input
                      id="crosspost-url"
                      value={linkUrl}
                      autoComplete="off"
                      placeholder="Blank = text post"
                      onChange={(event) => setLinkUrl(event.target.value)}
                    />
                  </Field>
                </div>
              ) : null}

              {error ? <FieldError>{error}</FieldError> : null}
              {result ? (
                <p className="text-xs text-muted-foreground">
                  {result.status === "draft"
                    ? "Draft saved: "
                    : result.status === "scheduled"
                      ? "Scheduled: "
                      : "Live: "}
                  <a
                    href={result.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-signal hover:underline"
                  >
                    Open on {PLATFORM_LABEL[effectivePlatform]}
                    <Icon icon={ArrowUpRight01Icon} className="size-3" />
                  </a>
                </p>
              ) : null}
            </FieldGroup>

            <DialogFooter className="mt-5 flex-wrap gap-2">
              <DialogClose
                render={
                  <Button type="button" variant="outline" disabled={busy} />
                }
              >
                Close
              </DialogClose>
              <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
                <Button
                  type="button"
                  disabled={
                    busy || readOnly || (!showSync && !effectiveConnectionId)
                  }
                  onClick={() =>
                    showSync ? syncMutation.mutate() : postMutation.mutate()
                  }
                  className={cn(busy && "opacity-70")}
                >
                  {busy ? (
                    <Icon icon={Loading03Icon} className="animate-spin" />
                  ) : (
                    <PlatformLogo platform={effectivePlatform} size={14} />
                  )}
                  {postMutation.isPending || syncMutation.isPending
                    ? "Posting…"
                    : showSync
                      ? "Sync changes"
                      : effectivePlatform === "substack" &&
                          substackMode !== "draft"
                        ? substackMode === "schedule"
                          ? "Schedule post"
                          : "Publish"
                        : "Post"}
                </Button>
              </DisabledReason>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

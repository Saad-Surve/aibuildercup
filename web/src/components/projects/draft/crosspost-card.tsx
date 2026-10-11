"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight01Icon, Loading03Icon } from "@hugeicons/core-free-icons";
import { toast } from "sonner";

import { PlatformLogo } from "@/components/calendar/platform";
import { Icon } from "@/components/common/icon";
import { DisabledReason } from "@/components/common/disabled-reason";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
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
import {
  crosspost,
  listConnections,
} from "@/lib/connections";
import { draftToText } from "@/lib/draft-export";
import type {
  CrosspostPlatform,
  CrosspostResult,
  Draft,
} from "@/lib/types";
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
 * Prefills from the draft cache; safe defaults (Medium/Substack drafts, your
 * own Reddit profile) unless the creator opts into public.
 */
export function CrosspostCard({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const readOnly = useReadOnly();
  const [open, setOpen] = useState(false);
  const [platform, setPlatform] = useState<CrosspostPlatform>("medium");
  const [connectionId, setConnectionId] = useState("");
  const [title, setTitle] = useState<string | null>(null);
  const [body, setBody] = useState<string | null>(null);
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
  const options = (connectionsQuery.data?.items ?? []).filter(
    (connection) => connection.platform === platform,
  );

  function prefill() {
    const cached = queryClient.getQueryData<Draft>(["draft", projectId]);
    if (title === null && cached) setTitle(cached.title);
    if (body === null && cached) setBody(draftToText(cached).trim());
  }

  const postMutation = useMutation({
    mutationFn: () => {
      if (!connectionId) throw new Error("Pick a connected account first.");
      const finalTitle = (title ?? "").trim();
      const finalBody = (body ?? "").trim();
      if (!finalTitle || !finalBody) {
        throw new Error("The post needs a title and a body.");
      }
      const extra: Record<string, unknown> =
        platform === "medium"
          ? { publishStatus }
          : platform === "substack"
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
        platform,
        connectionId,
        title: finalTitle,
        body: finalBody,
        options: extra,
      });
    },
    onSuccess: (posted) => {
      setError(null);
      setResult(posted);
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

  if (!open) {
    return (
      <div>
        <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={readOnly}
            onClick={() => {
              setOpen(true);
              prefill();
            }}
          >
            Post to Medium / Substack / Reddit
          </Button>
        </DisabledReason>
      </div>
    );
  }

  const busy = postMutation.isPending;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cross-post this draft</CardTitle>
        <CardDescription>
          Sends the text above to a connected writing platform. Defaults are
          safe: platform drafts and your own Reddit profile.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-1.5">
          {(Object.keys(PLATFORM_LABEL) as CrosspostPlatform[]).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => {
                setPlatform(value);
                setConnectionId("");
                setResult(null);
              }}
              aria-pressed={platform === value}
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors",
                platform === value
                  ? "border-signal/50 bg-signal/10 font-medium text-foreground"
                  : "border-border text-muted-foreground hover:text-foreground",
              )}
            >
              <PlatformLogo platform={value} size={14} />
              {PLATFORM_LABEL[value]}
            </button>
          ))}
        </div>

        <FieldGroup>
          <Field>
            <FieldLabel required>Account</FieldLabel>
            <Select value={connectionId} onValueChange={(value) => setConnectionId(value ?? "")}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder={`Pick a connected ${PLATFORM_LABEL[platform]} account`}>
                  {(value: unknown) =>
                    typeof value === "string" && value.length > 0
                      ? (options.find((item) => item.connectionId === value)?.displayName ?? value)
                      : `Pick a connected ${PLATFORM_LABEL[platform]} account`
                  }
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {options.map((item) => (
                  <SelectItem key={item.connectionId} value={item.connectionId}>
                    {item.displayName}
                    {item.status !== "connected" ? " (needs reconnect)" : ""}
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
          </Field>

          <Field>
            <FieldLabel htmlFor="crosspost-body" required>
              Body (Markdown)
            </FieldLabel>
            <Textarea
              id="crosspost-body"
              value={body ?? ""}
              rows={6}
              onChange={(event) => setBody(event.target.value)}
            />
          </Field>

          {platform === "medium" ? (
            <Field>
              <FieldLabel>Visibility</FieldLabel>
              <Select value={publishStatus} onValueChange={(value) => setPublishStatus(value ?? "draft")}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="draft">Draft (only you)</SelectItem>
                  <SelectItem value="unlisted">Unlisted (link only)</SelectItem>
                  <SelectItem value="public">Public</SelectItem>
                </SelectContent>
              </Select>
            </Field>
          ) : null}

          {platform === "substack" ? (
            <>
              <div className="grid grid-cols-2 gap-4">
                <Field>
                  <FieldLabel>Mode</FieldLabel>
                  <Select value={substackMode} onValueChange={(value) => setSubstackMode(value ?? "draft")}>
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
                  <Select value={audience} onValueChange={(value) => setAudience(value ?? "everyone")}>
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="everyone">Everyone</SelectItem>
                      <SelectItem value="subscribers_only">Subscribers</SelectItem>
                      <SelectItem value="paid_subscribers_only">Paid</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
              </div>
              {substackMode === "publish" ? (
                <label className="flex items-start gap-2 text-sm">
                  <Checkbox
                    checked={sendEmail}
                    onCheckedChange={(value) => setSendEmail(Boolean(value))}
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

          {platform === "reddit" ? (
            <div className="grid grid-cols-2 gap-4">
              <Field>
                <FieldLabel htmlFor="crosspost-subreddit">Subreddit</FieldLabel>
                <Input
                  id="crosspost-subreddit"
                  value={subreddit}
                  autoComplete="off"
                  placeholder="Blank = your own profile"
                  onChange={(event) => setSubreddit(event.target.value)}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="crosspost-url">Link URL (optional)</FieldLabel>
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
              {result.status === "draft" ? "Draft saved: " : result.status === "scheduled" ? "Scheduled: " : "Live: "}
              <a
                href={result.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-signal hover:underline"
              >
                Open on {PLATFORM_LABEL[platform]}
                <Icon icon={ArrowUpRight01Icon} className="size-3" />
              </a>
            </p>
          ) : null}
        </FieldGroup>

        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" disabled={busy} onClick={() => setOpen(false)}>
            Close
          </Button>
          <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
            <Button
              type="button"
              disabled={busy || readOnly || !connectionId}
              onClick={() => postMutation.mutate()}
              className={cn(busy && "opacity-70")}
            >
              {busy ? (
                <Icon icon={Loading03Icon} className="animate-spin" />
              ) : (
                <PlatformLogo platform={platform} size={14} />
              )}
              {postMutation.isPending
                ? "Posting…"
                : platform === "substack" && substackMode !== "draft"
                  ? substackMode === "schedule"
                    ? "Schedule post"
                    : "Publish post"
                  : "Post"}
            </Button>
          </DisabledReason>
        </div>
      </CardContent>
    </Card>
  );
}

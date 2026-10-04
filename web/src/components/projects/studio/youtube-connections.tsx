"use client";

import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Analytics01Icon,
  CheckmarkCircle02Icon,
  Link01Icon,
  Loading03Icon,
  Refresh01Icon,
  SparklesIcon,
  YoutubeIcon,
} from "@hugeicons/core-free-icons";
import { toast } from "sonner";

import { Icon } from "@/components/common/icon";
import { DisabledReason } from "@/components/common/disabled-reason";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api-client";
import {
  deleteConnection,
  listConnections,
  startYouTubeOAuth,
  syncConnection,
  syncConnectionAudience,
  syncConnectionContent,
} from "@/lib/connections";
import { seedYouTubeContent } from "@/lib/seed";
import type { Connection } from "@/lib/types";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";
import { cn } from "@/lib/utils";

function describe(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}

function subtitle(connection: Connection): string {
  const parts: string[] = [];
  if (connection.googleAccountEmail) parts.push(connection.googleAccountEmail);
  if (connection.externalHandle) parts.push(connection.externalHandle);
  if (connection.subscriberCount != null) {
    parts.push(`${connection.subscriberCount.toLocaleString()} subscribers`);
  }
  if (connection.contentItemCount) {
    parts.push(`${connection.contentItemCount} videos read`);
  }
  return parts.join(" · ");
}

function StatusBadge({ connection }: { connection: Connection }) {
  if (connection.status === "connected") {
    return (
      <Badge className="border-sev-good/40 bg-sev-good/10 text-sev-good">
        Connected
      </Badge>
    );
  }
  if (connection.status === "needs_reauth") {
    return (
      <Badge className="border-sev-high/40 bg-sev-high/10 text-sev-high">
        Reconnect needed
      </Badge>
    );
  }
  return <Badge variant="outline">{connection.status}</Badge>;
}

/**
 * Connect and manage YouTube channels.
 *
 * Each "Connect a Google account" click goes through Google's consent screen with
 * `prompt=select_account`, so the creator chooses which Gmail account to connect from. One
 * Google account can own several channels; every channel becomes its own connection.
 *
 * When `selectable`, the list becomes a picker for the publish form.
 */
export function YouTubeConnections({
  redirectPath,
  selectable = false,
  selectedId = null,
  onSelect,
  className,
}: {
  redirectPath?: string;
  selectable?: boolean;
  selectedId?: string | null;
  onSelect?: (connectionId: string) => void;
  className?: string;
}) {
  const queryClient = useQueryClient();
  const readOnly = useReadOnly();
  const connectionsQuery = useQuery({
    queryKey: ["connections"],
    queryFn: listConnections,
  });

  // Surface the result of an OAuth round-trip, then strip it from the URL so a refresh
  // does not replay the toast.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const status = params.get("youtube");
    if (!status) return;
    if (status === "connected") {
      const accounts = params.get("googleAccount");
      toast.success(
        accounts ? `Connected Google account ${accounts}.` : "YouTube connected.",
      );
    } else if (status === "error") {
      toast.error(params.get("reason") ?? "Connecting YouTube failed.");
    }
    params.delete("youtube");
    params.delete("reason");
    params.delete("connections");
    params.delete("googleAccount");
    const query = params.toString();
    window.history.replaceState(
      {},
      "",
      `${window.location.pathname}${query ? `?${query}` : ""}`,
    );
    void queryClient.invalidateQueries({ queryKey: ["connections"] });
  }, [queryClient]);

  const connectMutation = useMutation({
    mutationFn: () => startYouTubeOAuth({ redirectPath }),
    onSuccess: (response) => {
      window.location.assign(response.authorizationUrl);
    },
    onError: (error) => toast.error(describe(error, "Could not start OAuth.")),
  });

  const syncMutation = useMutation({
    mutationFn: (connectionId: string) => syncConnection(connectionId),
    onSuccess: () => {
      toast.success("Channel stats refreshed.");
      void queryClient.invalidateQueries({ queryKey: ["connections"] });
    },
    onError: (error) => toast.error(describe(error, "Could not refresh the channel.")),
  });

  const contentMutation = useMutation({
    mutationFn: (connectionId: string) => syncConnectionContent(connectionId),
    onSuccess: (profile) => {
      toast.success(
        profile.itemCount > 0
          ? `Read ${profile.itemCount} videos — the writer will match your voice.`
          : "No public videos found on this channel yet.",
      );
      void queryClient.invalidateQueries({ queryKey: ["connections"] });
    },
    onError: (error) =>
      toast.error(describe(error, "Could not read the channel content.")),
  });

  const audienceMutation = useMutation({
    mutationFn: (connectionId: string) => syncConnectionAudience(connectionId),
    onSuccess: (profile) => {
      const views = profile.summary.find((metric) => metric.metric === "views")?.value;
      toast.success(
        views != null
          ? `Audience read — ${Math.round(views).toLocaleString()} views in the last ${profile.periodDays} days.`
          : "Audience profile updated.",
      );
      void queryClient.invalidateQueries({ queryKey: ["connections"] });
    },
    onError: (error) =>
      toast.error(describe(error, "Could not read the channel's analytics.")),
  });

  const seedMutation = useMutation({
    mutationFn: () => seedYouTubeContent(),
    onSuccess: (result) => {
      toast.success(
        `Loaded ${result.itemCount} videos from ${result.channel} (CC BY) for the demo.`,
      );
      void queryClient.invalidateQueries({ queryKey: ["connections"] });
    },
    onError: (error) => toast.error(describe(error, "Could not load the demo content.")),
  });

  const disconnectMutation = useMutation({
    mutationFn: (connectionId: string) => deleteConnection(connectionId),
    onSuccess: () => {
      toast.success("Channel disconnected.");
      void queryClient.invalidateQueries({ queryKey: ["connections"] });
    },
    onError: (error) => toast.error(describe(error, "Could not disconnect.")),
  });

  const connections = connectionsQuery.data?.items ?? [];
  const needsReauth = connections.some(
    (connection) => connection.status === "needs_reauth",
  );

  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Icon icon={YoutubeIcon} className="text-muted-foreground" />
          <span className="text-sm font-medium">
            {connections.length === 0
              ? "No channels connected"
              : `${connections.length} channel${connections.length === 1 ? "" : "s"}`}
          </span>
          {needsReauth ? (
            <Badge className="border-sev-high/40 bg-sev-high/10 text-sev-high">
              Reconnect needed
            </Badge>
          ) : null}
        </div>
        <div className="flex items-center gap-1.5">
          <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              title="Load a public CC-BY channel's content for the demo (no account needed)"
              onClick={() => seedMutation.mutate()}
              disabled={seedMutation.isPending || readOnly}
            >
              {seedMutation.isPending ? (
                <Icon icon={Loading03Icon} className="animate-spin" />
              ) : (
                <Icon icon={SparklesIcon} />
              )}
              Load CC-BY demo
            </Button>
          </DisabledReason>
          <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
            <Button
              type="button"
              size="sm"
              variant={connections.length === 0 ? "default" : "outline"}
              onClick={() => connectMutation.mutate()}
              disabled={connectMutation.isPending || readOnly}
            >
              {connectMutation.isPending ? (
                <Icon icon={Loading03Icon} className="animate-spin" />
              ) : (
                <Icon icon={Link01Icon} />
              )}
              Connect a Google account
            </Button>
          </DisabledReason>
        </div>
      </div>

      {connectionsQuery.isLoading ? (
        <p className="text-sm text-muted-foreground">Loading connections…</p>
      ) : null}

      {connectionsQuery.error ? (
        <p className="text-sm text-destructive">
          {describe(connectionsQuery.error, "Could not load connections.")}
        </p>
      ) : null}

      {connections.length > 0 ? (
        <ul className="space-y-2">
          {connections.map((connection) => {
            const isSelected = selectedId === connection.connectionId;
            return (
              <li key={connection.connectionId}>
                <div
                  className={cn(
                    "flex items-start gap-3 rounded-lg border p-3",
                    isSelected ? "border-signal/60 bg-signal/5" : "border-border",
                  )}
                >
                  {connection.avatarUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={connection.avatarUrl}
                      alt=""
                      className="size-9 shrink-0 rounded-full object-cover"
                    />
                  ) : (
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-muted">
                      <Icon icon={YoutubeIcon} className="size-4" />
                    </span>
                  )}
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="truncate text-sm font-medium">
                        {connection.displayName}
                      </span>
                      <StatusBadge connection={connection} />
                      {isSelected ? (
                        <Icon
                          icon={CheckmarkCircle02Icon}
                          className="size-4 text-signal"
                        />
                      ) : null}
                    </div>
                    {subtitle(connection) ? (
                      <p className="truncate text-xs text-muted-foreground">
                        {subtitle(connection)}
                      </p>
                    ) : null}
                    {selectable && onSelect ? (
                      <Button
                        type="button"
                        size="sm"
                        variant={isSelected ? "default" : "outline"}
                        className="mt-2"
                        onClick={() => onSelect(connection.connectionId)}
                      >
                        {isSelected ? "Selected channel" : "Use this channel"}
                      </Button>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 items-center gap-1">
                    <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
                      <Button
                        type="button"
                        size="icon-sm"
                        variant="ghost"
                        aria-label="Read channel content for the AI"
                        title="Read your published videos so the writer can match your style"
                        onClick={() => contentMutation.mutate(connection.connectionId)}
                        disabled={contentMutation.isPending || readOnly}
                      >
                        <Icon
                          icon={SparklesIcon}
                          className={cn(
                            contentMutation.isPending &&
                              contentMutation.variables === connection.connectionId &&
                              "animate-pulse",
                          )}
                        />
                      </Button>
                    </DisabledReason>
                    <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
                      <Button
                        type="button"
                        size="icon-sm"
                        variant="ghost"
                        aria-label="Read channel analytics"
                        title="Read your audience analytics (demographics, traffic, top videos)"
                        onClick={() => audienceMutation.mutate(connection.connectionId)}
                        disabled={audienceMutation.isPending || readOnly}
                      >
                        <Icon
                          icon={Analytics01Icon}
                          className={cn(
                            audienceMutation.isPending &&
                              audienceMutation.variables === connection.connectionId &&
                              "animate-pulse",
                          )}
                        />
                      </Button>
                    </DisabledReason>
                    <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
                      <Button
                        type="button"
                        size="icon-sm"
                        variant="ghost"
                        aria-label="Refresh channel stats"
                        onClick={() => syncMutation.mutate(connection.connectionId)}
                        disabled={syncMutation.isPending || readOnly}
                      >
                        <Icon
                          icon={Refresh01Icon}
                          className={cn(
                            syncMutation.isPending &&
                              syncMutation.variables === connection.connectionId &&
                              "animate-spin",
                          )}
                        />
                      </Button>
                    </DisabledReason>
                    <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() =>
                          disconnectMutation.mutate(connection.connectionId)
                        }
                        disabled={disconnectMutation.isPending || readOnly}
                      >
                        Disconnect
                      </Button>
                    </DisabledReason>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

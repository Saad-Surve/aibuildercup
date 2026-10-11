"use client";

import { Suspense, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link01Icon, Loading03Icon } from "@hugeicons/core-free-icons";
import { toast } from "sonner";

import { PlatformLogo } from "@/components/calendar/platform";
import { Icon } from "@/components/common/icon";
import { InlineArrow } from "@/components/common/inline-arrow";
import { DisabledReason } from "@/components/common/disabled-reason";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api-client";
import {
  connectMedium,
  connectSubstack,
  deleteConnection,
  listConnections,
  startRedditOAuth,
} from "@/lib/connections";
import type { Connection, CrosspostPlatform } from "@/lib/types";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";

function describe(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}

/*
 * Bookmarklet: the `substack.sid` cookie only exists on substack.com, so a page
 * on our origin can't read it. The creator drags this to their bookmarks bar,
 * opens Substack, and clicks it there — it copies the cookie to the clipboard.
 */
const SUBSTACK_COOKIE_BOOKMARKLET =
  "javascript:(()=>{const m=document.cookie.match(/(?:^|;\\s*)substack\\.sid=([^;]+)/);if(!m){alert('Not signed in to Substack in this tab.');return;}const v=decodeURIComponent(m[1]);navigator.clipboard.writeText(v).then(()=>alert('Substack cookie copied. Paste it into Creator Studio.')).catch(()=>prompt('Copy this value:',v));})()";

const PLATFORMS: {
  platform: CrosspostPlatform;
  name: string;
  detail: string;
  connectHint: string;
}[] = [
  {
    platform: "medium",
    name: "Medium",
    detail: "Stories and essays",
    connectHint:
      "Needs a legacy integration token (Medium stopped issuing new ones in Jan 2025).",
  },
  {
    platform: "substack",
    name: "Substack",
    detail: "Newsletters and posts",
    connectHint:
      "Connect with one pasted session cookie — your publication is detected automatically (the cookie expires, so expect to reconnect).",
  },
  {
    platform: "reddit",
    name: "Reddit",
    detail: "Posts and discussions",
    connectHint:
      "OAuth sign-in. Free tier covers personal posting (100 calls/min).",
  },
];

function RedditCallbackNotice() {
  // Surface the result of an OAuth round-trip, then strip it from the URL so
  // a refresh does not replay the toast (same pattern as the YouTube flow).
  const queryClient = useQueryClient();
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const status = params.get("reddit");
    if (!status) return;
    if (status === "connected") {
      toast.success("Reddit connected.");
    } else if (status === "error") {
      toast.error(params.get("reason") ?? "Connecting Reddit failed.");
    }
    params.delete("reddit");
    params.delete("reason");
    params.delete("connections");
    const query = params.toString();
    window.history.replaceState(
      {},
      "",
      `${window.location.pathname}${query ? `?${query}` : ""}`,
    );
    void queryClient.invalidateQueries({ queryKey: ["connections"] });
  }, [queryClient]);
  return null;
}

export function TextPlatformConnections({
  redirectPath,
}: {
  redirectPath?: string;
}) {
  const queryClient = useQueryClient();
  const readOnly = useReadOnly();
  const [dialog, setDialog] = useState<CrosspostPlatform | null>(null);
  const [token, setToken] = useState("");
  const [sid, setSid] = useState("");
  const [subdomain, setSubdomain] = useState("");
  const [publications, setPublications] = useState<
    { subdomain: string; name: string }[]
  >([]);
  const [error, setError] = useState<string | null>(null);

  const connectionsQuery = useQuery({
    queryKey: ["connections"],
    queryFn: listConnections,
  });
  const connections = connectionsQuery.data?.items ?? [];
  const byPlatform = new Map<CrosspostPlatform, Connection[]>();
  for (const connection of connections) {
    if (
      connection.platform === "medium" ||
      connection.platform === "substack" ||
      connection.platform === "reddit"
    ) {
      const list = byPlatform.get(connection.platform) ?? [];
      list.push(connection);
      byPlatform.set(connection.platform, list);
    }
  }

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["connections"] });
  }

  const mediumMutation = useMutation({
    mutationFn: () => connectMedium(token.trim()),
    onSuccess: () => {
      toast.success("Medium connected");
      setToken("");
      setError(null);
      setDialog(null);
      refresh();
    },
    onError: (caught) => setError(describe(caught, "Could not connect Medium.")),
  });

  const substackMutation = useMutation({
    mutationFn: () => connectSubstack(sid.trim(), subdomain.trim() || undefined),
    onSuccess: () => {
      toast.success("Substack connected");
      setSid("");
      setSubdomain("");
      setPublications([]);
      setError(null);
      setDialog(null);
      refresh();
    },
    onError: (caught) => {
      if (
        caught instanceof ApiError &&
        caught.code === "SUBSTACK_MULTIPLE_PUBLICATIONS"
      ) {
        const options =
          (caught.details?.publications as
            | { subdomain: string; name: string }[]
            | undefined) ?? [];
        setPublications(options);
        setError("Pick your publication below, then Connect.");
        return;
      }
      setError(describe(caught, "Could not connect Substack."));
    },
  });

  const redditMutation = useMutation({
    mutationFn: () =>
      startRedditOAuth(
        redirectPath ? { redirectPath } : {},
      ),
    onSuccess: (started) => {
      window.location.href = started.authorizationUrl;
    },
    onError: (caught) => toast.error(describe(caught, "Could not start Reddit OAuth.")),
  });

  const deleteMutation = useMutation({
    mutationFn: (connectionId: string) => deleteConnection(connectionId),
    onSuccess: () => {
      toast.success("Disconnected");
      refresh();
    },
    onError: (caught) => toast.error(describe(caught, "Could not disconnect.")),
  });

  const busy =
    mediumMutation.isPending ||
    substackMutation.isPending ||
    redditMutation.isPending ||
    deleteMutation.isPending;

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <Suspense fallback={null}>
        <RedditCallbackNotice />
      </Suspense>
      {PLATFORMS.map((entry) => {
        const linked = byPlatform.get(entry.platform) ?? [];
        return (
          <div
            key={entry.platform}
            className="space-y-3 rounded-xl border px-4 py-3"
          >
            <div className="flex items-center gap-3">
              <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground">
                <PlatformLogo platform={entry.platform} size={16} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{entry.name}</p>
                <p className="text-xs text-muted-foreground">{entry.detail}</p>
              </div>
            </div>

            {linked.length > 0 ? (
              <ul className="space-y-1.5">
                {linked.map((connection) => (
                  <li
                    key={connection.connectionId}
                    className="flex items-center gap-2 rounded-lg bg-muted/40 px-2.5 py-1.5"
                  >
                    <span className="min-w-0 flex-1 truncate text-xs font-medium">
                      {connection.displayName}
                    </span>
                    {connection.status === "connected" ? (
                      <Badge className="border-sev-good/40 bg-sev-good/10 text-sev-good">
                        Connected
                      </Badge>
                    ) : (
                      <Badge className="border-sev-high/40 bg-sev-high/10 text-sev-high">
                        Reconnect
                      </Badge>
                    )}
                    <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
                      <button
                        type="button"
                        onClick={() => deleteMutation.mutate(connection.connectionId)}
                        disabled={busy || readOnly}
                        className="shrink-0 text-xs text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
                      >
                        Disconnect
                      </button>
                    </DisabledReason>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted-foreground">{entry.connectHint}</p>
            )}

            <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="w-full"
                disabled={busy || readOnly}
                onClick={() => {
                  setError(null);
                  if (entry.platform === "reddit") redditMutation.mutate();
                  else setDialog(entry.platform);
                }}
              >
                {redditMutation.isPending && entry.platform === "reddit" ? (
                  <Icon icon={Loading03Icon} className="animate-spin" />
                ) : (
                  <Icon icon={Link01Icon} />
                )}
                {entry.platform === "reddit"
                  ? "Connect with Reddit"
                  : `Connect ${entry.name}`}
              </Button>
            </DisabledReason>
          </div>
        );
      })}

      <Dialog
        open={dialog !== null}
        onOpenChange={(next) => {
          if (!next) {
            setDialog(null);
            setError(null);
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {dialog === "medium" ? "Connect Medium" : "Connect Substack"}
            </DialogTitle>
          </DialogHeader>
          <FieldGroup>
            {dialog === "medium" ? (
              <Field>
                <FieldLabel htmlFor="medium-token" required>
                  Integration token
                </FieldLabel>
                <Input
                  id="medium-token"
                  type="password"
                  value={token}
                  autoComplete="off"
                  placeholder="181d415f…"
                  onChange={(event) => setToken(event.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Medium <InlineArrow /> Settings <InlineArrow /> Security{" "}
                  <InlineArrow /> Integration tokens. Only pre-2025 tokens work;
                  new ones are no longer issued.
                </p>
              </Field>
            ) : (
              <>
                <Field>
                  <FieldLabel htmlFor="substack-sid" required>
                    Substack session cookie
                  </FieldLabel>
                  <Input
                    id="substack-sid"
                    type="password"
                    value={sid}
                    autoComplete="off"
                    placeholder="substack.sid=… (or just the value)"
                    onChange={(event) => {
                      setSid(event.target.value);
                      setPublications([]);
                      setError(null);
                    }}
                  />
                  <p className="text-xs text-muted-foreground">
                    Fastest: drag{" "}
                    <a
                      href={SUBSTACK_COOKIE_BOOKMARKLET}
                      draggable
                      onClick={(event) => event.preventDefault()}
                      title="Drag me to your bookmarks bar, then click me on Substack"
                      className="cursor-grab font-medium text-signal underline-offset-4 hover:underline"
                    >
                      Copy Substack cookie
                    </a>{" "}
                    to your bookmarks bar, open Substack, click it, then paste
                    here. Or copy <code>substack.sid</code> from devtools{" "}
                    <InlineArrow /> Application <InlineArrow /> Cookies. Paste the
                    value, the <code>substack.sid=…</code> pair, or the whole
                    cookie header — we find it. Your publication is detected for
                    you.
                  </p>
                </Field>
                {publications.length > 0 ? (
                  <Field>
                    <FieldLabel>Publication</FieldLabel>
                    <div className="flex flex-wrap gap-2">
                      {publications.map((publication) => (
                        <button
                          key={publication.subdomain}
                          type="button"
                          onClick={() => setSubdomain(publication.subdomain)}
                          className={`rounded-full border px-3 py-1 text-xs ${
                            subdomain === publication.subdomain
                              ? "border-signal bg-signal/10 text-foreground"
                              : "border-border text-muted-foreground hover:bg-muted"
                          }`}
                        >
                          {publication.name}
                        </button>
                      ))}
                    </div>
                  </Field>
                ) : null}
                <Field>
                  <FieldLabel htmlFor="substack-subdomain">
                    Publication subdomain (optional)
                  </FieldLabel>
                  <Input
                    id="substack-subdomain"
                    value={subdomain}
                    autoComplete="off"
                    placeholder="Auto-detected"
                    onChange={(event) => setSubdomain(event.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Leave blank — the cookie finds your publication. Only fill it
                    in if your account has several.
                  </p>
                </Field>
              </>
            )}
            {error ? <FieldError>{error}</FieldError> : null}
          </FieldGroup>
          <DialogFooter>
            <Button
              type="button"
              disabled={
                busy ||
                readOnly ||
                (dialog === "medium" ? !token.trim() : !sid.trim())
              }
              onClick={() => {
                if (dialog === "medium") mediumMutation.mutate();
                else if (dialog === "substack") substackMutation.mutate();
              }}
            >
              {(mediumMutation.isPending || substackMutation.isPending) &&
              ((dialog === "medium" && mediumMutation.isPending) ||
                (dialog === "substack" && substackMutation.isPending))
                ? "Connecting…"
                : "Connect"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

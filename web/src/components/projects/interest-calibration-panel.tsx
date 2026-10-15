"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import {
  ApiError,
  calibrateInterest,
  getInterestCalibration,
} from "@/lib/api-client";
import { listConnections } from "@/lib/connections";
import { useReadOnly } from "@/lib/read-only";

/** Mounted only while the interest info panel is open; reads never call YouTube. */
export function InterestCalibrationPanel() {
  const readOnly = useReadOnly();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState("");
  const [now, setNow] = useState(() => Date.now());
  const [retryAt, setRetryAt] = useState<string | null>(null);
  const connections = useQuery({
    queryKey: ["connections"],
    queryFn: listConnections,
  });
  const calibration = useQuery({
    queryKey: ["interest-calibration"],
    queryFn: getInterestCalibration,
    refetchInterval: (query) =>
      query.state.data?.status === "calibrating" ? 5000 : false,
  });
  const channels = (connections.data?.items ?? []).filter(
    (connection) =>
      connection.platform === "youtube" && connection.status === "connected",
  );
  const state = calibration.data;
  const connectionId =
    selectedId ||
    channels.find((channel) => channel.connectionId === state?.connectionId)
      ?.connectionId ||
    channels[0]?.connectionId ||
    "";
  const mutation = useMutation({
    mutationFn: calibrateInterest,
    retry: false,
    onSuccess: async (result) => {
      setRetryAt(null);
      queryClient.setQueryData(["interest-calibration"], result);
      await queryClient.invalidateQueries({ queryKey: ["analysis-interest"] });
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        const next = error.details?.nextAllowedAt;
        if (typeof next === "string") setRetryAt(next);
      }
      void queryClient.invalidateQueries({
        queryKey: ["interest-calibration"],
      });
    },
  });
  const nextAllowed = retryAt || state?.nextAllowedAt;
  const coolingDown = !!nextAllowed && new Date(nextAllowed).getTime() > now;
  useEffect(() => {
    if (!nextAllowed) return;
    const remaining = new Date(nextAllowed).getTime() - now;
    if (remaining <= 0) return;
    const timer = window.setTimeout(() => setNow(Date.now()), remaining + 50);
    return () => window.clearTimeout(timer);
  }, [nextAllowed, now]);
  const busy = mutation.isPending || state?.status === "calibrating";
  const error = mutation.error || connections.error || calibration.error;

  return (
    <div className="mt-3 space-y-2 border-t border-border/70 pt-3">
      <p>
        Match the audience-interest curve to your channel&apos;s YouTube
        retention.
      </p>
      {state && state.status !== "not_started" && (
        <div aria-live="polite" className="space-y-1">
          <p>
            {state.channelName && `${state.channelName} · `}
            {state.status === "ready"
              ? "Channel curve ready"
              : state.status === "insufficient_data"
                ? "Not enough data"
                : state.status === "calibrating"
                  ? "Reading channel retention…"
                  : "Calibration unavailable"}
            {state.attemptedAt &&
              ` · ${new Date(state.attemptedAt).toLocaleDateString()}`}
          </p>
          {!busy && (
            <p>
              {state.videos} usable videos · {state.views.toLocaleString()}{" "}
              views
              {state.scannedVideos > 0 &&
                ` · ${state.scannedVideos} uploads checked`}
            </p>
          )}
          {state.buckets.map((bucket) => (
            <p key={bucket.bucket}>
              {bucket.bucket === "short" ? "Up to 3 minutes" : "Over 3 minutes"}
              {`: ${bucket.videos} videos · ${bucket.views.toLocaleString()} views · ${Math.round(bucket.creatorWeight * 100)}% channel shape, remainder generic`}
            </p>
          ))}
          {state.reason && <p>{state.reason}</p>}
        </div>
      )}
      {channels.length > 1 && (
        <label className="flex flex-wrap items-center gap-2">
          Channel
          <select
            value={connectionId}
            onChange={(event) => setSelectedId(event.target.value)}
            disabled={busy || readOnly}
            className="rounded-md border border-border bg-background px-2 py-1 text-xs"
          >
            {channels.map((channel) => (
              <option key={channel.connectionId} value={channel.connectionId}>
                {channel.displayName}
              </option>
            ))}
          </select>
        </label>
      )}
      {channels.length > 0 && (
        <Button
          size="sm"
          variant="outline"
          disabled={readOnly || busy || coolingDown || !connectionId}
          onClick={() => mutation.mutate(connectionId)}
        >
          {busy ? "Calibrating…" : "Calibrate to my channel"}
        </Button>
      )}
      {readOnly ? (
        <p>
          The shared demo is read-only. Sign in with your own account and
          connect YouTube to calibrate to your channel.
        </p>
      ) : coolingDown ? (
        <p>
          Available again {new Date(nextAllowed!).toLocaleString()}. You can
          calibrate once every 24 hours.
        </p>
      ) : channels.length === 0 && !connections.isPending ? (
        <p>Connect YouTube in Settings to calibrate to your channel.</p>
      ) : (
        <p>
          Uses up to 40 recent uploads. Needs three videos per length with at
          least 100 views each. Applies across your workspace.
        </p>
      )}
      {error && (
        <p role="alert" className="text-sev-high">
          {error instanceof Error
            ? error.message
            : "Calibration could not be loaded."}
        </p>
      )}
    </div>
  );
}

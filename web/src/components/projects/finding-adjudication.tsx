"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getAdjudicationEvidenceUrl, formatDurationMs } from "@/lib/analysis";
import type { Finding } from "@/lib/types";
import { cn } from "@/lib/utils";

const VERDICTS = {
  confirm: {
    label: "Confirmed",
    style: "border-sev-none/30 bg-sev-none/10 text-sev-none",
  },
  downgrade: {
    label: "Downgraded",
    style: "border-sev-medium/30 bg-sev-medium/10 text-sev-medium",
  },
  reject: {
    label: "Rejected",
    style: "border-border bg-muted text-muted-foreground",
  },
};

export function FindingAdjudicationCard({
  projectId,
  analysisRunId,
  finding,
  onSeek,
}: {
  projectId: string;
  analysisRunId: string;
  finding: Finding;
  onSeek: (atMs: number) => void;
}) {
  const check = finding.adjudication;
  const [showClip, setShowClip] = useState(false);
  const [imageFailed, setImageFailed] = useState(false);
  const frame = useQuery({
    queryKey: [
      "adjudication-evidence",
      projectId,
      analysisRunId,
      finding.findingId,
      "frame",
    ],
    queryFn: () =>
      getAdjudicationEvidenceUrl(projectId, analysisRunId, finding.findingId),
    enabled: Boolean(check?.evidence.framePath),
    staleTime: 10 * 60 * 1000,
    refetchInterval: 10 * 60 * 1000,
    retry: false,
  });
  const clip = useQuery({
    queryKey: [
      "adjudication-evidence",
      projectId,
      analysisRunId,
      finding.findingId,
      "clip",
    ],
    queryFn: () =>
      getAdjudicationEvidenceUrl(
        projectId,
        analysisRunId,
        finding.findingId,
        "clip",
      ),
    enabled: showClip && Boolean(check?.evidence.clipPath),
    staleTime: 10 * 60 * 1000,
    retry: false,
  });
  if (!check)
    return (
      <div className="flex flex-wrap items-center gap-2 border-t border-border/60 px-3 py-2 text-xs text-muted-foreground">
        <span className="rounded-full border border-border px-2 py-0.5">
          Not checked
        </span>
        <span>This finding could not be checked against the footage.</span>
      </div>
    );
  const verdict = VERDICTS[check.verdict];
  return (
    <div className="space-y-2 border-t border-border/60 bg-muted/20 px-3 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[11px] font-medium tracking-wide text-muted-foreground">
          Footage check
        </span>
        <span
          className={cn(
            "rounded-full border px-2 py-0.5 text-xs font-medium",
            verdict.style,
          )}
        >
          {verdict.label}
        </span>
      </div>
      <div className="flex items-start gap-3">
        <div className="w-28 shrink-0">
          <button
            type="button"
            onClick={() => onSeek(check.evidence.timestampMs)}
            aria-label={`Seek to checked frame at ${formatDurationMs(check.evidence.timestampMs)}`}
            className="block aspect-video w-full overflow-hidden rounded-md border border-border bg-black/70 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            {frame.data && !imageFailed ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={frame.data.url}
                alt={`Frame checked at ${formatDurationMs(check.evidence.timestampMs)}`}
                loading="lazy"
                className="h-full w-full object-contain"
                onError={() => setImageFailed(true)}
              />
            ) : (
              <span className="text-[11px] text-white/70">
                {frame.isLoading ? "Loading frame…" : "Frame unavailable"}
              </span>
            )}
          </button>
          <p className="mt-1 text-[11px] text-muted-foreground">
            Checked at {formatDurationMs(check.evidence.timestampMs)}
          </p>
          {(frame.isError || imageFailed) && (
            <button
              type="button"
              className="text-[11px] text-signal underline"
              onClick={() => {
                setImageFailed(false);
                void frame.refetch();
              }}
            >
              Reload frame
            </button>
          )}
        </div>
        <p className="min-w-0 text-sm text-foreground/90">{check.reason}</p>
      </div>
      {check.evidence.clipPath && (
        <button
          type="button"
          aria-expanded={showClip}
          onClick={() => setShowClip((value) => !value)}
          className="text-xs text-signal underline-offset-4 hover:underline"
        >
          {showClip ? "Hide checked clip" : "Watch checked clip (silent)"}
        </button>
      )}
      {showClip &&
        (clip.data ? (
          <video
            src={clip.data.url}
            muted
            controls
            playsInline
            className="aspect-video w-full rounded-md bg-black"
          />
        ) : (
          <p className="text-xs text-muted-foreground">
            {clip.isLoading ? "Loading clip…" : "Clip unavailable"}
          </p>
        ))}
    </div>
  );
}

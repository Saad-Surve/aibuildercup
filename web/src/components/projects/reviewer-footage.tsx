"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { dimensionLabel, getReviewerContextUrl } from "@/lib/analysis";
import { formatTimestamp } from "@/lib/projects";
import type { ReviewerRun, ReviewerToolCall } from "@/lib/types";

/*
 * Evidence trail: the moments reviewers pulled out of the video while they were
 * deciding. Collapsed by default and fetched lazily - a signed URL is only minted
 * once the user opens a card - so polling a running review never signs anything.
 */

interface FootageItem {
  reviewerRunId: string;
  dimension: string;
  index: number;
  call: ReviewerToolCall;
}

export function ReviewerFootage({
  projectId,
  analysisRunId,
  reviewers,
  onSeek,
}: {
  projectId: string;
  analysisRunId: string;
  reviewers: ReviewerRun[];
  onSeek: (startMs: number) => void;
}) {
  const [open, setOpen] = useState(false);

  const items: FootageItem[] = [];
  const seenPaths = new Set<string>();
  for (const reviewer of reviewers) {
    (reviewer.toolCalls ?? []).forEach((call, index) => {
      // Shared samples are supplied to several reviewers but shown once.
      if (call.contentPath && seenPaths.has(call.contentPath)) return;
      if (call.contentPath) seenPaths.add(call.contentPath);
      items.push({
        reviewerRunId: reviewer.reviewerRunId,
        dimension: reviewer.dimension,
        index,
        call,
      });
    });
  }
  if (items.length === 0) return null;
  items.sort((a, b) => a.call.timestampMs - b.call.timestampMs);

  return (
    <div className="rounded-lg border border-border">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left"
      >
        <span className="text-sm">
          Footage checks{" "}
          <span className="tabular text-muted-foreground">{items.length}</span>
          <span className="ml-1.5 text-muted-foreground">
            — sampled frames and moments inspected during review
          </span>
        </span>
        <span className="text-xs text-muted-foreground">
          {open ? "Hide" : "Show"}
        </span>
      </button>
      {open && (
        <div className="grid grid-cols-1 gap-2 border-t border-border p-2 sm:grid-cols-2 xl:grid-cols-3">
          {items.map((item) => (
            <FootageCard
              key={`${item.reviewerRunId}-${item.index}`}
              projectId={projectId}
              analysisRunId={analysisRunId}
              item={item}
              onSeek={onSeek}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function FootageCard({
  projectId,
  analysisRunId,
  item,
  onSeek,
}: {
  projectId: string;
  analysisRunId: string;
  item: FootageItem;
  onSeek: (startMs: number) => void;
}) {
  const { call } = item;
  const mediaQuery = useQuery({
    queryKey: [
      "reviewer-context",
      projectId,
      analysisRunId,
      item.reviewerRunId,
      item.index,
    ],
    queryFn: () =>
      getReviewerContextUrl(
        projectId,
        analysisRunId,
        item.reviewerRunId,
        item.index,
      ),
    enabled: Boolean(call.contentPath),
    staleTime: 10 * 60 * 1000,
  });

  const url = mediaQuery.data?.url;
  const isImage = call.mimeType.startsWith("image/");
  const isVideo = call.mimeType.startsWith("video/");

  return (
    <div className="overflow-hidden rounded-md border border-border bg-muted/30">
      <button
        type="button"
        onClick={() => onSeek(call.timestampMs)}
        title={`Jump to ${formatTimestamp(call.timestampMs)}`}
        className="flex w-full items-center justify-between gap-2 px-2 py-1.5 text-left"
      >
        <span className="truncate text-xs">
          {call.label.startsWith("Shared sample:")
            ? "Shared sample"
            : dimensionLabel(item.dimension)}
        </span>
        <span className="shrink-0 tabular text-xs text-time underline-offset-2 hover:underline">
          {formatTimestamp(call.timestampMs)}
        </span>
      </button>
      <div className="flex aspect-video items-center justify-center bg-black/80">
        {!call.contentPath ? (
          <span className="text-xs text-muted-foreground">Not captured</span>
        ) : mediaQuery.isLoading ? (
          <span className="text-xs text-muted-foreground">Loading…</span>
        ) : url && isImage ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={url}
            alt={call.label || "Reviewer frame"}
            className="h-full w-full object-contain"
          />
        ) : url && isVideo ? (
          <video
            src={url}
            controls
            muted
            playsInline
            className="h-full w-full"
          />
        ) : (
          <span className="text-xs text-muted-foreground">Unavailable</span>
        )}
      </div>
      <div className="px-2 py-1 text-[11px] text-muted-foreground">
        {call.tool === "cut_clip" ? "Clip" : "Frame"}
        {call.label ? ` · ${call.label}` : ""}
      </div>
    </div>
  );
}

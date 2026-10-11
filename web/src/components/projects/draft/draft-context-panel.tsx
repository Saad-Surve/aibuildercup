"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { SparklesIcon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getDraftContext } from "@/lib/drafts";
import type {
  AudienceBreakdown,
  ContentStyleSummary,
  CreatorContextExample,
} from "@/lib/types";

function StyleSignals({ style }: { style: ContentStyleSummary }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        Style signals
      </p>
      {style.topTags.length ? (
        <div className="flex flex-wrap gap-1.5">
          {style.topTags.slice(0, 8).map((tag) => (
            <Badge key={tag} variant="secondary" className="font-normal">
              {tag}
            </Badge>
          ))}
        </div>
      ) : null}
      <p className="text-xs text-muted-foreground">
        {style.videoCount} videos · ~{style.avgTitleWords} words/title ·{" "}
        {style.titleWithNumberPct}% of titles use a number ·{" "}
        {style.videosPerMonth}/month
      </p>
    </div>
  );
}

function ExampleRow({ example }: { example: CreatorContextExample }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="rounded-lg border p-2.5">
      <div className="flex items-start justify-between gap-3">
        <span className="min-w-0 text-sm font-medium">{example.title}</span>
        {example.viewCount != null ? (
          <span className="shrink-0 text-xs text-muted-foreground">
            {example.viewCount.toLocaleString()} views
          </span>
        ) : null}
      </div>
      {example.tags.length ? (
        <div className="mt-1 flex flex-wrap gap-1">
          {example.tags.slice(0, 5).map((tag) => (
            <span
              key={tag}
              className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground"
            >
              {tag}
            </span>
          ))}
        </div>
      ) : null}
      {example.transcriptExcerpt ? (
        <div className="mt-1.5">
          <button
            type="button"
            className="text-[11px] text-signal hover:underline"
            onClick={() => setOpen((value) => !value)}
          >
            {open ? "Hide transcript excerpt" : "Show transcript excerpt"}
          </button>
          {open ? (
            <p className="mt-1 text-xs text-muted-foreground italic">
              {example.transcriptExcerpt}
            </p>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

function Breakdown({
  title,
  breakdown,
}: {
  title: string;
  breakdown: AudienceBreakdown | null;
}) {
  if (!breakdown || breakdown.rows.length === 0) return null;
  const max = Math.max(...breakdown.rows.map((row) => row.value), 1);
  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
        {title}
      </p>
      {breakdown.rows.slice(0, 5).map((row) => (
        <div key={row.label} className="space-y-0.5">
          <div className="flex items-center justify-between text-xs">
            <span className="truncate">{row.label}</span>
            <span className="text-muted-foreground">
              {row.value.toLocaleString()}
            </span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-signal/60"
              style={{ width: `${Math.round((row.value / max) * 100)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Visual proof of the RAG step: the past videos, style signals, and audience the last generation
 * retrieved from the creator's channel. Read-only; refreshes when a new generation lands.
 */
export function DraftContextPanel({
  projectId,
  enabled,
  refreshKey,
}: {
  projectId: string;
  enabled: boolean;
  refreshKey?: string | number;
}) {
  const query = useQuery({
    queryKey: ["draft-context", projectId, refreshKey],
    queryFn: () => getDraftContext(projectId),
    enabled,
  });
  if (!enabled) return null;
  const context = query.data;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon icon={SparklesIcon} className="text-signal" />
          Style evidence
        </CardTitle>
        <CardDescription>
          {context?.available
            ? `What the writer pulled from ${context.connectionDisplayName ?? "your channel"} to match your voice.`
            : "What the writer pulls from your connected channel to match your voice."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {query.isLoading ? <Skeleton className="h-24 w-full" /> : null}

        {!query.isLoading && !context?.available ? (
          <p className="text-sm text-muted-foreground">
            No channel content yet. Connect your YouTube channel from{" "}
            <span className="font-medium">Profile → Connected channels</span>,
            use “Read channel content for the AI”, then regenerate the draft.
          </p>
        ) : null}

        {context?.available ? (
          <>
            {context.sourceType === "folder_import" ? (
              <Badge variant="outline">Imported creator library</Badge>
            ) : null}
            {context.style ? <StyleSignals style={context.style} /> : null}

            {context.examples.length ? (
              <div className="space-y-2">
                <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                  Retrieved examples ({context.examples.length})
                </p>
                <ul className="space-y-2">
                  {context.examples.map((example) => (
                    <ExampleRow key={example.videoId} example={example} />
                  ))}
                </ul>
              </div>
            ) : null}

            {context.writtenExamples?.length ? (
              <div className="space-y-2">
                <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                  Written examples ({context.writtenExamples.length})
                </p>
                <ul className="space-y-2">
                  {context.writtenExamples.map((example) => (
                    <li
                      key={example.itemId}
                      className="rounded-lg border p-2.5"
                    >
                      <p className="text-sm font-medium">{example.title}</p>
                      <p className="mt-1 text-xs whitespace-pre-wrap text-muted-foreground">
                        {example.excerpt}
                      </p>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {context.audience ? (
              <div className="grid gap-4 sm:grid-cols-2">
                <Breakdown
                  title="Audience demographics"
                  breakdown={context.audience.demographics}
                />
                <Breakdown
                  title="Traffic sources"
                  breakdown={context.audience.trafficSources}
                />
              </div>
            ) : null}
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}

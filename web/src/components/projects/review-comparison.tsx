"use client";

import { useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { HeatmapTracks } from "@/components/projects/heatmap-tracks";
import { SourceVideoPlayer } from "@/components/projects/source-video-player";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  compareAnalysisRuns,
  dimensionLabel,
  formatDurationMs,
  SEVERITY_LABELS,
} from "@/lib/analysis";
import { listAssets } from "@/lib/projects";
import type {
  AnalysisComparison,
  AnalysisRun,
  ComparisonBin,
  ComparisonFinding,
  ComparisonRun,
} from "@/lib/types";

export interface ReviewComparisonProps {
  projectId: string;
  baseRunId: string;
  targetRunId: string;
  /** Native player times, never source-mapped display times. */
  onSeekBase?: (startMs: number) => void;
  onSeekTarget?: (startMs: number) => void;
  /** Embed with external players by supplying seek callbacks and false here. */
  showPlayers?: boolean;
}

/** Rough-cut entry point: mount with the original and completed re-review run IDs. */
export function ReviewComparison({
  projectId,
  baseRunId,
  targetRunId,
  onSeekBase,
  onSeekTarget,
  showPlayers = true,
}: ReviewComparisonProps) {
  const scope = useId();
  const query = useQuery({
    queryKey: ["analysis-comparison", projectId, baseRunId, targetRunId],
    queryFn: () => compareAnalysisRuns(projectId, baseRunId, targetRunId),
    enabled: Boolean(baseRunId && targetRunId && baseRunId !== targetRunId),
    retry: false,
  });
  const assetsQuery = useQuery({
    queryKey: ["assets", projectId],
    queryFn: () => listAssets(projectId),
    enabled: showPlayers && Boolean(query.data),
  });

  function seek(side: "base" | "target", ms: number) {
    const callback = side === "base" ? onSeekBase : onSeekTarget;
    callback?.(ms);
    if (showPlayers)
      window.dispatchEvent(
        new CustomEvent("creator-studio:seek", {
          detail: {
            projectId,
            seconds: ms / 1000,
            seekScope: `${scope}-${side}`,
          },
        }),
      );
  }

  if (!baseRunId || !targetRunId || baseRunId === targetRunId)
    return (
      <p role="status" className="text-sm text-muted-foreground">
        Choose two different completed reviews.
      </p>
    );
  if (query.isPending) return <Skeleton className="h-40 w-full" />;
  if (query.isError)
    return (
      <div role="alert" className="space-y-2 text-sm">
        <p>{query.error.message || "Comparison could not be loaded."}</p>
        <Button
          variant="outline"
          size="sm"
          onClick={() => void query.refetch()}
        >
          Retry comparison
        </Button>
      </div>
    );
  const data = query.data;
  if (!data) return null;
  const summary = data.summary;
  const aligned = data.alignment.targetTimeline === "source";
  const dimensions = [
    ...new Set([...data.base.dimensions, ...data.target.dimensions]),
  ];

  function seekSourceInTarget(sourceMs: number) {
    if (!aligned) {
      seek("target", sourceMs);
      return;
    }
    const segment = data!.alignment.segments.find(
      (s) => sourceMs >= s.sourceStartMs && sourceMs < s.sourceEndMs,
    );
    if (segment)
      seek(
        "target",
        segment.targetStartMs +
          ((sourceMs - segment.sourceStartMs) *
            (segment.targetEndMs - segment.targetStartMs)) /
            (segment.sourceEndMs - segment.sourceStartMs),
      );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-2" aria-label="Review change summary">
        <Stat>
          {summary.flaggedBinsBefore.total} → {summary.flaggedBinsAfter.total}{" "}
          flagged moments
        </Stat>
        <Stat>
          {summary.acceptedFindingsResolved} of {summary.acceptedFindingsTotal}{" "}
          accepted fixes resolved
        </Stat>
        <Stat>
          {summary.newIssuesCount} new{" "}
          {summary.newIssuesCount === 1 ? "issue" : "issues"}
        </Stat>
        <Stat>
          {formatDurationMs(summary.durationMsBefore)} →{" "}
          {formatDurationMs(summary.durationMsAfter)}
        </Stat>
      </div>
      <p className="text-xs text-muted-foreground">
        Critical {summary.flaggedBinsBefore.critical} →{" "}
        {summary.flaggedBinsAfter.critical} · High{" "}
        {summary.flaggedBinsBefore.high} → {summary.flaggedBinsAfter.high} ·
        Medium {summary.flaggedBinsBefore.medium} →{" "}
        {summary.flaggedBinsAfter.medium}. Counts are per five-second moment.
        Accepted fixes include revised decisions.
      </p>
      <div
        role="status"
        className="rounded-lg border border-border bg-muted/30 p-3 text-xs text-muted-foreground"
      >
        {data.alignment.note}{" "}
        {data.alignment.method === "transcript" &&
          `Alignment confidence: ${Math.round(data.alignment.confidence * 100)}%.`}
        {summary.uncomparedFindingsCount > 0 &&
          ` ${summary.uncomparedFindingsCount} findings cannot be compared reliably and are excluded from resolved/new counts.`}
        {(data.base.status === "partial_failure" ||
          data.target.status === "partial_failure") &&
          " Some moments were not reviewed, so they cannot count as fixed."}
      </div>
      {showPlayers && (
        <div className="grid gap-3 lg:grid-cols-2">
          {(["base", "target"] as const).map((side) => {
            const asset = assetsQuery.data?.items.find(
              (a) => a.assetId === data[side].sourceAssetId,
            );
            return (
              <section
                key={side}
                aria-label={`${side === "base" ? "Before" : "After"} player`}
                className="space-y-2"
              >
                <h4 className="text-sm font-medium">
                  {side === "base" ? "Before" : "After"} video
                </h4>
                {asset ? (
                  <SourceVideoPlayer
                    projectId={projectId}
                    asset={asset}
                    seekScope={`${scope}-${side}`}
                  />
                ) : assetsQuery.isPending ? (
                  <Skeleton className="aspect-video w-full" />
                ) : (
                  <p className="text-xs text-muted-foreground">
                    The video for this review is unavailable.
                  </p>
                )}
              </section>
            );
          })}
        </div>
      )}
      {aligned && (
        <ComparisonTransition
          key={`${data.base.runId}-${data.target.runId}`}
          data={data}
          onSeek={(ms) => {
            seek("base", ms);
            seekSourceInTarget(ms);
          }}
        />
      )}
      <section aria-label="Before heatmap" className="space-y-2">
        <h4 className="text-sm font-medium">Before · source timeline</h4>
        <HeatmapTracks
          bins={data.base.bins}
          coverage={data.base.coverage}
          durationMs={data.base.durationMs}
          dimensions={dimensions}
          scores={{}}
          onSeek={(ms) => seek("base", ms)}
          selectedBinId={null}
          onSelectBin={() => {}}
          reviewState={data.base.status === "ready" ? "complete" : "incomplete"}
        />
      </section>
      <section aria-label="After heatmap" className="space-y-2">
        <h4 className="text-sm font-medium">
          After ·{" "}
          {aligned ? "source timeline" : "own timeline (alignment unavailable)"}
        </h4>
        <HeatmapTracks
          bins={data.target.bins}
          coverage={data.target.coverage}
          removedSpans={data.alignment.removedSpans}
          durationMs={aligned ? data.base.durationMs : data.target.durationMs}
          dimensions={dimensions}
          scores={{}}
          onSeek={seekSourceInTarget}
          selectedBinId={null}
          onSelectBin={() => {}}
          reviewState={
            data.target.status === "ready" ? "complete" : "incomplete"
          }
        />
        {data.alignment.removedSpans.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Hatched = removed from the after video:{" "}
            {data.alignment.removedSpans
              .map(
                (s) =>
                  `${formatDurationMs(s.startMs)}–${formatDurationMs(s.endMs)}`,
              )
              .join(", ")}
            .
          </p>
        )}
      </section>
      {data.target.unmappedBins.length > 0 && (
        <section className="space-y-2" aria-label="Unaligned after footage">
          <h4 className="text-sm font-medium">
            After · unmatched footage on its own timeline
          </h4>
          <p className="text-xs text-muted-foreground">
            These moments could not be matched to the source. They still count
            toward the after total.
          </p>
          <HeatmapTracks
            bins={data.target.unmappedBins}
            durationMs={data.target.durationMs}
            dimensions={dimensions}
            scores={{}}
            onSeek={(ms) => seek("target", ms)}
            selectedBinId={null}
            onSelectBin={() => {}}
            reviewState={
              data.target.status === "ready" ? "complete" : "incomplete"
            }
          />
        </section>
      )}
      {data.base.interest.length > 0 && data.target.interest.length > 0 && (
        <InterestComparison data={data} />
      )}
      <div className="space-y-4">
        {(["resolved", "persists", "new", "uncompared"] as const).map(
          (status) => {
            const findings = data.findings.filter((f) => f.status === status);
            if (status === "uncompared" && findings.length === 0) return null;
            return (
              <section
                key={status}
                aria-label={GROUP_LABELS[status]}
                className="space-y-2"
              >
                <h4 className="text-sm font-medium">
                  {GROUP_LABELS[status]}{" "}
                  <span className="text-muted-foreground">
                    ({findings.length})
                  </span>
                </h4>
                {findings.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    No findings in this group.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {findings.map((change) => (
                      <FindingChange
                        key={`${status}-${change.baseFinding?.findingId ?? change.targetFinding?.findingId}`}
                        change={change}
                        targetMomentMs={targetMoment(data, change)}
                        onSeekBase={(ms) => seek("base", ms)}
                        onSeekTarget={(ms) => seek("target", ms)}
                      />
                    ))}
                  </ul>
                )}
              </section>
            );
          },
        )}
      </div>
    </div>
  );
}

const GROUP_LABELS = {
  resolved: "Resolved",
  persists: "Persists",
  new: "New",
  uncompared: "Cannot compare",
};
const REASONS = {
  removed: "Entire flagged span removed",
  no_match: "No comparable finding in the reviewed target span",
  matched: "Comparable finding remains",
  unmatched_target:
    "Newly flagged in the after review; not necessarily caused by the edit",
  alignment_uncertain: "Could not match this to the source timeline",
  review_incomplete: "Not fully reviewed in the after version",
};

function Stat({ children }: { children: React.ReactNode }) {
  return (
    <span className="tabular rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm font-medium">
      {children}
    </span>
  );
}

function targetMoment(
  data: AnalysisComparison,
  change: ComparisonFinding,
): number | null {
  const finding = change.baseFinding;
  if (!finding || data.alignment.targetTimeline !== "source") return null;
  const segment = data.alignment.segments.find(
    (s) =>
      s.sourceStartMs < Math.max(finding.endMs, finding.startMs + 1) &&
      s.sourceEndMs > finding.startMs,
  );
  if (!segment) return null;
  const sourceMs = Math.max(finding.startMs, segment.sourceStartMs);
  return (
    segment.targetStartMs +
    ((sourceMs - segment.sourceStartMs) *
      (segment.targetEndMs - segment.targetStartMs)) /
      (segment.sourceEndMs - segment.sourceStartMs)
  );
}

function FindingChange({
  change,
  onSeekBase,
  onSeekTarget,
  targetMomentMs,
}: {
  change: ComparisonFinding;
  targetMomentMs: number | null;
  onSeekBase: (ms: number) => void;
  onSeekTarget: (ms: number) => void;
}) {
  const finding = change.targetFinding ?? change.baseFinding;
  if (!finding) return null;
  return (
    <li className="space-y-2 rounded-lg border border-border/70 p-3 text-xs">
      <div className="flex flex-wrap items-center gap-2 font-medium">
        <span>{dimensionLabel(finding.dimension)}</span>
        <span>{SEVERITY_LABELS[finding.severity]}</span>
        {change.accepted && (
          <span className="rounded border border-border px-1.5 py-0.5">
            Accepted fix
          </span>
        )}
      </div>
      <p className="text-muted-foreground">{REASONS[change.reason]}</p>
      {[change.baseFinding, change.targetFinding].map(
        (item, index) =>
          item && (
            <div key={`${index}-${item.findingId}`} className="space-y-1">
              <p className="font-medium">
                {index === 0 ? "Before" : "After"} ·{" "}
                {formatDurationMs(item.startMs)}–{formatDurationMs(item.endMs)}
              </p>
              {item.evidence.quote && (
                <blockquote className="border-l-2 border-border pl-2">
                  “{item.evidence.quote}”
                </blockquote>
              )}
              <p>{item.evidence.critique_and_reasoning}</p>
              <p className="text-muted-foreground">
                Proposed edit: {item.suggestion}
              </p>
            </div>
          ),
      )}
      <div className="flex flex-wrap gap-2">
        {!change.targetFinding && targetMomentMs !== null && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onSeekTarget(targetMomentMs)}
          >
            Seek after · {formatDurationMs(targetMomentMs)}
          </Button>
        )}
        {change.baseFinding && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onSeekBase(change.baseFinding!.startMs)}
          >
            Seek before · {formatDurationMs(change.baseFinding.startMs)}
          </Button>
        )}
        {change.targetFinding && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onSeekTarget(change.targetFinding!.startMs)}
          >
            Seek after · {formatDurationMs(change.targetFinding.startMs)}
          </Button>
        )}
        {!change.baseFinding && change.sourceSpans.length > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => onSeekBase(change.sourceSpans[0].startMs)}
          >
            Seek source · {formatDurationMs(change.sourceSpans[0].startMs)}
          </Button>
        )}
      </div>
    </li>
  );
}

const RANK: Record<string, number> = {
  none: 0,
  low: 1,
  medium: 2,
  high: 3,
  critical: 4,
};
const SEVERITY_COLOR: Record<string, string> = {
  none: "var(--muted)",
  low: "var(--sev-low)",
  medium: "var(--sev-medium)",
  high: "var(--sev-high)",
  critical: "var(--sev-critical)",
};

function worst(bins: ComparisonBin[], start: number, end: number) {
  return bins
    .filter((b) => b.startMs < end && b.endMs > start)
    .reduce(
      (severity, b) =>
        RANK[b.severity] > RANK[severity] ? b.severity : severity,
      "none",
    );
}

function momentLabel(bins: ComparisonBin[], start: number, end: number) {
  return bins.some((b) => b.startMs < end && b.endMs > start)
    ? SEVERITY_LABELS[worst(bins, start, end) as keyof typeof SEVERITY_LABELS]
    : "No finding";
}

function ComparisonTransition({
  data,
  onSeek,
}: {
  data: AnalysisComparison;
  onSeek: (ms: number) => void;
}) {
  const [after, setAfter] = useState(false);
  const [rover, setRover] = useState(0);
  const count = Math.ceil(data.base.durationMs / 5000);
  return (
    <section
      className="space-y-2"
      aria-label="Animated before and after changes"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="mr-auto text-sm font-medium">
          Change across the source
        </h4>
        <Button
          size="sm"
          variant="outline"
          aria-pressed={after}
          onClick={() => setAfter((value) => !value)}
        >
          {after ? "Show before" : "Show after"}
        </Button>
      </div>
      <div className="flex h-7 overflow-hidden rounded border border-border">
        {Array.from({ length: count }, (_, index) => {
          const start = index * 5000,
            end = Math.min(start + 5000, data.base.durationMs);
          const beforeSeverity = worst(data.base.bins, start, end),
            afterSeverity = worst(data.target.bins, start, end);
          const removed = data.alignment.removedSpans.some(
            (s) => s.startMs < end && s.endMs > start,
          );
          const beforeLabel = momentLabel(data.base.bins, start, end);
          const afterLabel = data.alignment.removedSpans.some(
            (s) => s.startMs <= start && s.endMs >= end,
          )
            ? "Removed"
            : momentLabel(data.target.bins, start, end);
          return (
            <button
              type="button"
              key={start}
              tabIndex={index === Math.min(rover, count - 1) ? 0 : -1}
              aria-label={`${formatDurationMs(start)}: before ${beforeLabel}, after ${afterLabel}${removed ? ", includes removed footage" : ""}`}
              title={`${formatDurationMs(start)} · ${beforeLabel} → ${afterLabel}${removed ? " · cut" : ""}`}
              onClick={() => onSeek(start)}
              onKeyDown={(event) => {
                const next =
                  event.key === "Home"
                    ? 0
                    : event.key === "End"
                      ? count - 1
                      : event.key === "ArrowRight"
                        ? Math.min(count - 1, index + 1)
                        : event.key === "ArrowLeft"
                          ? Math.max(0, index - 1)
                          : null;
                if (next !== null) {
                  event.preventDefault();
                  setRover(next);
                  const buttons =
                    event.currentTarget.parentElement?.querySelectorAll(
                      "button",
                    );
                  buttons?.[next]?.focus();
                }
              }}
              className="min-w-0 flex-1 border-r border-card/50 transition-colors duration-700 motion-reduce:transition-none focus-visible:z-10 focus-visible:outline-2 focus-visible:outline-signal"
              style={{
                backgroundColor:
                  SEVERITY_COLOR[after ? afterSeverity : beforeSeverity],
                backgroundImage:
                  after && removed
                    ? "repeating-linear-gradient(135deg, transparent 0 3px, var(--muted-foreground) 3px 4px)"
                    : undefined,
              }}
            />
          );
        })}
      </div>
      <p className="text-xs text-muted-foreground" aria-live="polite">
        Showing {after ? "after" : "before"}. Each cell is five source seconds.
        Hatched cells include removed footage. Use arrow keys to navigate and
        Enter to jump.
      </p>
    </section>
  );
}

function curvePaths(
  points: ComparisonRun["interest"],
  duration: number,
): string[] {
  const paths: string[] = [];
  let previousEnd = -1;
  for (const point of points) {
    const x1 = (point.startMs / Math.max(1, duration)) * 1000,
      x2 = (point.endMs / Math.max(1, duration)) * 1000,
      y = 90 - point.value * 80;
    if (point.startMs !== previousEnd) paths.push(`M ${x1} ${y} L ${x2} ${y}`);
    else paths[paths.length - 1] += ` L ${x1} ${y} L ${x2} ${y}`;
    previousEnd = point.endMs;
  }
  return paths;
}

function InterestComparison({ data }: { data: AnalysisComparison }) {
  const aligned = data.alignment.targetTimeline === "source";
  const change = data.summary.interestChange;
  return (
    <section className="space-y-2" aria-label="Interest before and after">
      <h4 className="text-sm font-medium">
        Audience interest ·{" "}
        {aligned ? "before / after overlay" : "separate timelines"}
      </h4>
      <p className="text-xs text-muted-foreground">
        Solid: before. Dashed: after. Shows relative interest, not measured
        retention. Only aligned moments are overlaid.
      </p>
      <svg
        role="img"
        aria-label="Relative audience interest: solid before line and dashed after line"
        viewBox={`0 0 1000 ${aligned ? 100 : 200}`}
        className="h-32 w-full rounded-lg border border-border bg-muted/20"
        preserveAspectRatio="none"
      >
        {curvePaths(data.base.interest, data.base.durationMs).map((path, i) => (
          <path
            key={`before-${i}`}
            d={path}
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            vectorEffect="non-scaling-stroke"
          />
        ))}
        {curvePaths(
          data.target.interest,
          aligned ? data.base.durationMs : data.target.durationMs,
        ).map((path, i) => (
          <path
            key={`after-${i}`}
            d={path}
            transform={aligned ? undefined : "translate(0 100)"}
            fill="none"
            stroke="var(--signal)"
            strokeWidth="2"
            strokeDasharray="6 4"
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>
      {change && (
        <p className="text-xs text-muted-foreground">
          Average lift above typical:{" "}
          {change.meanAboveBaselineBefore.toFixed(3)} →{" "}
          {change.meanAboveBaselineAfter.toFixed(3)} (
          {change.delta >= 0 ? "+" : ""}
          {change.delta.toFixed(3)}). {change.note}
        </p>
      )}
    </section>
  );
}

/** Completed-run picker for the review panel; also usable in a standalone card. */
export function ReviewComparisonPicker({
  projectId,
  runs,
}: {
  projectId: string;
  runs: AnalysisRun[];
}) {
  const id = useId();
  const [selection, setSelection] = useState<{
    base?: string;
    target?: string;
  }>({});
  const [open, setOpen] = useState(false);
  const completed = runs.filter(
    (run) => run.status === "ready" || run.status === "partial_failure",
  );
  if (completed.length < 2) return null;
  const base = completed.some((r) => r.analysisRunId === selection.base)
    ? selection.base!
    : completed[1].analysisRunId;
  const target = completed.some((r) => r.analysisRunId === selection.target)
    ? selection.target!
    : completed[0].analysisRunId;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Before / After</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          {(["base", "target"] as const).map((side) => (
            <div key={side} className="min-w-0 flex-1 space-y-1">
              <label htmlFor={`${id}-${side}`} className="text-xs font-medium">
                {side === "base" ? "Before review" : "After review"}
              </label>
              <select
                id={`${id}-${side}`}
                value={side === "base" ? base : target}
                onChange={(event) => {
                  setSelection((value) => ({
                    ...value,
                    [side]: event.target.value,
                  }));
                }}
                className="h-9 w-full rounded-lg border border-input bg-background px-2 text-xs"
              >
                {completed.map((run) => (
                  <option key={run.analysisRunId} value={run.analysisRunId}>
                    v{runs.length - runs.indexOf(run)} ·{" "}
                    {new Date(run.createdAt).toLocaleString()}
                    {run.status === "partial_failure" ? " · coverage gaps" : ""}
                  </option>
                ))}
              </select>
            </div>
          ))}
          <Button
            size="sm"
            variant="outline"
            aria-expanded={open}
            aria-controls={`${id}-comparison`}
            disabled={base === target}
            onClick={() => setOpen((value) => !value)}
          >
            {open ? "Hide comparison" : "Compare reviews"}
          </Button>
        </div>
        {base === target && (
          <p role="status" className="text-xs text-muted-foreground">
            Choose two different completed reviews.
          </p>
        )}
        {open && base !== target && (
          <div id={`${id}-comparison`}>
            <ReviewComparison
              key={`${base}-${target}`}
              projectId={projectId}
              baseRunId={base}
              targetRunId={target}
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

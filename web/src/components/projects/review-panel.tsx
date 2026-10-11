"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert02Icon,
  Loading03Icon,
  PlayIcon,
  SparklesIcon,
} from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { DisabledReason } from "@/components/common/disabled-reason";
import { FindingsPanel } from "@/components/projects/findings-panel";
import { GroundingPanel } from "@/components/projects/grounding-panel";
import { HeatmapTracks } from "@/components/projects/heatmap-tracks";
import { ReviewerFootage } from "@/components/projects/reviewer-footage";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useProjectTranscript } from "@/hooks/use-project-transcript";
import { ApiError } from "@/lib/api-client";
import {
  formatCostUsd,
  formatScore,
  getAnalysisRun,
  getHeatmap,
  listAnalysisRuns,
  listFindings,
  listReviewers,
  SEVERITY_DOT_CLASS,
  SEVERITY_LABELS,
  SEVERITY_ORDER,
  startAnalysis,
} from "@/lib/analysis";
import type { AnalysisDimension, AnalysisRun, Severity } from "@/lib/types";
import { ANALYSIS_DIMENSIONS } from "@/lib/types";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";
import { WORKSPACE_PANE_SNAP } from "@/lib/workspace";
import { cn } from "@/lib/utils";

/*
 * The review workspace: start a run, watch the reviewers work, read the ribbon.
 *
 * The ribbon is the point of the product, so it gets the space and the colour;
 * everything around it stays monochrome and quiet. Severity chips are both the
 * legend and the filter — the control and the explanation are the same object.
 */

export function ReviewPanel({
  projectId,
  platform,
  onSeek,
  live = false,
  transcriptShouldPoll = false,
}: {
  projectId: string;
  platform: string;
  onSeek: (startMs: number) => void;
  /** Whether the realtime socket is connected; intervals are the fallback only. */
  live?: boolean;
  /** Whether the shared transcript query should fall back to polling. */
  transcriptShouldPoll?: boolean;
}) {
  const queryClient = useQueryClient();
  const readOnly = useReadOnly();
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<Severity[]>([]);
  const [selectedBinId, setSelectedBinId] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);

  // Same query as the transcript panel, so the two can never disagree about
  // whether to keep polling for it.
  const transcriptQuery = useProjectTranscript(projectId, {
    shouldPoll: transcriptShouldPoll,
  });
  const durationMs = transcriptQuery.data?.durationMs ?? 0;
  const hasTranscript = Boolean(transcriptQuery.data);

  const runsQuery = useQuery({
    queryKey: ["analysis-runs", projectId],
    queryFn: () => listAnalysisRuns(projectId),
    retry: false,
    // Realtime `analysis.*` events invalidate this list. The interval below is
    // the degraded fallback: only while a run is in flight AND the socket is
    // down, so a finished review can never leave the panel stuck on "Reviewing".
    refetchInterval: (query) =>
      !live && (query.state.data?.items ?? []).some(isInFlight) ? 8000 : false,
    refetchIntervalInBackground: true,
  });
  const runs = useMemo(() => runsQuery.data?.items ?? [], [runsQuery.data]);
  const activeRun: AnalysisRun | null =
    runs.find((run) => run.analysisRunId === selectedRunId) ?? runs[0] ?? null;
  const activeRunId = activeRun?.analysisRunId ?? null;

  const runQuery = useQuery({
    queryKey: ["analysis-run", projectId, activeRunId],
    queryFn: () => getAnalysisRun(projectId, activeRunId as string),
    enabled: Boolean(activeRunId),
    refetchInterval: (query) =>
      !live && isInFlight(query.state.data) ? 5000 : false,
    refetchIntervalInBackground: true,
  });

  // The freshest view of the run: the realtime-patched single run once it
  // exists, the list row before that. Every decision reads from here, never
  // from the list, so the two cannot disagree about the shown status.
  const run = runQuery.data ?? activeRun;
  const runStatus = run?.status ?? null;
  const isRunning = isInFlight(run);

  // A new video revision brings a new transcript. When the newest review was
  // built from an older transcript, nudge the user to re-run it — otherwise the
  // heatmap silently describes the previous cut of the video.
  const activeTranscriptId = transcriptQuery.data?.transcriptId ?? null;
  const transcriptIsNewer =
    Boolean(activeTranscriptId) &&
    runs.length > 0 &&
    runs[0].transcriptId !== activeTranscriptId &&
    !isRunning;

  const reviewersQuery = useQuery({
    queryKey: ["analysis-reviewers", projectId, activeRunId],
    queryFn: () => listReviewers(projectId, activeRunId as string),
    enabled: Boolean(activeRunId),
    refetchInterval: !live && isRunning ? 5000 : false,
    refetchIntervalInBackground: true,
  });

  const heatmapQuery = useQuery({
    queryKey: ["analysis-heatmap", projectId, activeRunId],
    queryFn: () => getHeatmap(projectId, activeRunId as string),
    enabled: Boolean(activeRunId),
    refetchInterval: !live && isRunning ? 8000 : false,
    refetchIntervalInBackground: true,
  });

  const findingsQuery = useQuery({
    queryKey: ["analysis-findings", projectId, activeRunId],
    queryFn: () => listFindings(projectId, activeRunId as string),
    enabled: Boolean(activeRunId),
    refetchInterval: !live && isRunning ? 8000 : false,
    refetchIntervalInBackground: true,
  });

  // The interval queries stop the instant the run settles, which can drop the
  // very last poll (findings and bins are written just before the run flips to
  // ready). Force one final fetch per run on the in-flight -> settled
  // transition, so a finished review always lands without a manual reload.
  const settledRunRef = useRef<string | null>(null);
  useEffect(() => {
    if (!activeRunId || runStatus === null) return;
    if (isRunning || settledRunRef.current === activeRunId) return;
    settledRunRef.current = activeRunId;
    void queryClient.invalidateQueries({
      queryKey: ["analysis-reviewers", projectId, activeRunId],
    });
    void queryClient.invalidateQueries({
      queryKey: ["analysis-heatmap", projectId, activeRunId],
    });
    void queryClient.invalidateQueries({
      queryKey: ["analysis-findings", projectId, activeRunId],
    });
  }, [activeRunId, runStatus, isRunning, projectId, queryClient]);

  const startMutation = useMutation({
    mutationFn: () =>
      startAnalysis(projectId, {
        platform,
        dimensions: [...ANALYSIS_DIMENSIONS],
      }),
    onSuccess: (response) => {
      setStartError(null);
      setSelectedBinId(null);
      setSeverityFilter([]);
      setSelectedRunId(response.analysisRunId);
      void queryClient.invalidateQueries({
        queryKey: ["analysis-runs", projectId],
      });
    },
    onError: (error) => {
      setStartError(
        error instanceof ApiError
          ? error.message
          : "The analysis could not be started.",
      );
    },
  });

  const reviewers = reviewersQuery.data?.items ?? [];
  const bins = heatmapQuery.data?.bins ?? [];
  const findings = findingsQuery.data?.items ?? [];
  const reviewIncomplete =
    run?.status === "partial_failure" ||
    run?.status === "failed" ||
    reviewers.some((reviewer) => Boolean(reviewer.error));

  // Derived, never reset: a bin id from another run simply is not in these bins,
  // so switching runs drops the selection without any effect or state cleanup.
  const selectedBin = bins.find((bin) => bin.binId === selectedBinId) ?? null;

  const laneDimensions: AnalysisDimension[] = run?.requestedDimensions?.length
    ? run.requestedDimensions
    : [...ANALYSIS_DIMENSIONS];

  const scores = run?.scoreByDimension ?? {};
  const findingCounts = run?.findingCounts ?? {};

  function toggleSeverity(severity: Severity) {
    setSeverityFilter((current) =>
      current.includes(severity)
        ? current.filter((item) => item !== severity)
        : [...current, severity],
    );
  }

  return (
    <>
      <Card className={WORKSPACE_PANE_SNAP}>
        <CardHeader className="shrink-0">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                {isRunning ? (
                  <Icon
                    icon={Loading03Icon}
                    className="animate-spin text-signal"
                  />
                ) : (
                  <Icon icon={PlayIcon} className="text-muted-foreground" />
                )}
                <CardTitle>Review</CardTitle>
                <span className="h-4 w-px bg-border" aria-hidden="true" />
                <span className="text-sm text-muted-foreground">
                  {run?.status === "ready" && reviewIncomplete
                    ? "Finished with gaps"
                    : statusLabel(run, hasTranscript)}
                </span>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {runs.length > 0 && (
                <Select
                  value={activeRunId ?? ""}
                  onValueChange={(value) =>
                    setSelectedRunId(value as string | null)
                  }
                >
                  <SelectTrigger size="sm" className="w-20">
                    <SelectValue placeholder="Latest">
                      {(value) => {
                        const index = runs.findIndex(
                          (item) => item.analysisRunId === value,
                        );
                        return index >= 0
                          ? `v${runs.length - index}`
                          : "Latest";
                      }}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {runs.map((item, index) => (
                      <SelectItem
                        key={item.analysisRunId}
                        value={item.analysisRunId}
                      >
                        v{runs.length - index}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
                <Button
                  size="sm"
                  onClick={() => startMutation.mutate()}
                  disabled={
                    startMutation.isPending ||
                    isRunning ||
                    !hasTranscript ||
                    readOnly
                  }
                  title={
                    hasTranscript
                      ? undefined
                      : "Available once the transcript is ready"
                  }
                >
                  <Icon icon={SparklesIcon} />
                  {startMutation.isPending
                    ? "Starting…"
                    : runs.length > 0
                      ? "Run analysis again"
                      : "Run analysis"}
                </Button>
              </DisabledReason>
            </div>
          </div>
        </CardHeader>

        <CardContent className="min-h-0 flex-1 space-y-4 overflow-y-auto py-2">
          {startError && (
            <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              <Icon icon={Alert02Icon} className="mt-0.5 size-4 shrink-0" />
              <span>{startError}</span>
            </div>
          )}

          {transcriptIsNewer && (
            <div className="flex flex-wrap items-center gap-3 rounded-lg border border-signal/40 bg-signal/5 px-3 py-2 text-sm">
              <Icon
                icon={SparklesIcon}
                className="size-4 shrink-0 text-signal"
              />
              <span className="flex-1">
                A newer transcript is ready. Run the review again to grade this
                revision.
              </span>
              <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
                <Button
                  size="sm"
                  onClick={() => startMutation.mutate()}
                  disabled={startMutation.isPending || readOnly}
                >
                  {startMutation.isPending ? "Starting…" : "Run analysis again"}
                </Button>
              </DisabledReason>
            </div>
          )}

          {/* Instrument readout: flagged-moment score, severity census, spend. */}
          <div className="tabular flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
            <span title="Average quality of reported moments; unmarked time is not graded.">
              Flagged moments{" "}
              <span className="text-foreground">
                {formatScore(run?.overallScore ?? null)}
              </span>
            </span>
            <span>
              Reviewers{" "}
              <span className="text-foreground">
                {
                  reviewers.filter(
                    (item) => item.status === "succeeded" && !item.error,
                  ).length
                }
                /{reviewers.length || laneDimensions.length}
              </span>
            </span>
            <span>
              Cost{" "}
              <span className="text-foreground">
                {formatCostUsd(run?.costEstimateUsd ?? 0)}
              </span>
            </span>
            <span className="ml-auto hidden sm:inline">
              Click a segment to jump there
            </span>
          </div>

          {/* Severity census doubles as the findings filter and the colour legend. */}
          <div className="flex flex-wrap items-center gap-1.5">
            {SEVERITY_ORDER.map((severity) => {
              const count = findingCounts[severity] ?? 0;
              const active = severityFilter.includes(severity);
              return (
                <button
                  key={severity}
                  type="button"
                  aria-pressed={active}
                  onClick={() => toggleSeverity(severity)}
                  title={`Show ${severity} findings`}
                  className={cn(
                    "inline-flex h-7 items-center gap-1.5 rounded-4xl border px-2.5 text-xs transition-colors focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                    active
                      ? "border-signal bg-signal text-signal-foreground"
                      : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
                  )}
                >
                  <span
                    className={cn(
                      "size-1.5 rounded-full",
                      active
                        ? "bg-signal-foreground"
                        : SEVERITY_DOT_CLASS[severity],
                    )}
                  />
                  {SEVERITY_LABELS[severity]}
                  <span className="tabular">{count}</span>
                </button>
              );
            })}
          </div>

          {runsQuery.isLoading ? (
            <Skeleton className="h-full min-h-40 w-full" />
          ) : (
            <HeatmapTracks
              bins={bins}
              durationMs={durationMs}
              dimensions={laneDimensions}
              scores={scores}
              onSeek={onSeek}
              selectedBinId={selectedBin?.binId ?? null}
              onSelectBin={(bin) => setSelectedBinId(bin?.binId ?? null)}
              severityFilter={severityFilter}
              reviewState={
                !run
                  ? "not_started"
                  : isRunning
                    ? "running"
                    : run.status === "ready" && !reviewIncomplete
                      ? "complete"
                      : "incomplete"
              }
            />
          )}

          {activeRunId && (
            <ReviewerFootage
              projectId={projectId}
              analysisRunId={activeRunId}
              reviewers={reviewers}
              onSeek={onSeek}
            />
          )}

          {activeRunId && <GroundingPanel reviewers={reviewers} />}
        </CardContent>
      </Card>

      <FindingsPanel
        findings={findings}
        loading={Boolean(activeRunId) && findingsQuery.isLoading}
        reviewed={Boolean(run && !isRunning)}
        incomplete={reviewIncomplete}
        running={
          isRunning ||
          startMutation.isPending ||
          // The just-started run is selected before the list refetch lands; treat
          // that gap as "searching" instead of flashing an empty state.
          (Boolean(selectedRunId) &&
            !runs.some((item) => item.analysisRunId === selectedRunId))
        }
        severityFilter={severityFilter}
        onToggleSeverity={toggleSeverity}
        selectedFindingIds={selectedBin?.findingIds ?? null}
        onSeek={(startMs) => {
          onSeek(startMs);
        }}
        onClearSelection={() => setSelectedBinId(null)}
      />
    </>
  );
}

function isInFlight(run: { status: string } | null | undefined): boolean {
  return run?.status === "queued" || run?.status === "running";
}

function statusLabel(run: AnalysisRun | null, hasTranscript: boolean): string {
  if (!run) return hasTranscript ? "Not started" : "Waiting for transcript";
  switch (run.status) {
    case "ready":
      return "Finished";
    case "partial_failure":
      return "Finished with gaps";
    case "failed":
      return "Failed";
    case "running":
      return "Reviewing";
    default:
      return "Queued";
  }
}

"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert02Icon,
  Loading03Icon,
  PlayIcon,
  SparklesIcon,
} from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { FindingsPanel } from "@/components/projects/findings-panel";
import { HeatmapTracks } from "@/components/projects/heatmap-tracks";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { CORE_DIMENSIONS } from "@/lib/types";
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
  transcriptShouldPoll,
}: {
  projectId: string;
  platform: string;
  onSeek: (startMs: number) => void;
  /** Whether the shared transcript query should keep polling. Defaults to true. */
  transcriptShouldPoll?: boolean;
}) {
  const queryClient = useQueryClient();
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
  });
  const runs = useMemo(
    () => runsQuery.data?.items ?? [],
    [runsQuery.data],
  );
  const activeRun: AnalysisRun | null =
    runs.find((run) => run.analysisRunId === selectedRunId) ?? runs[0] ?? null;
  const activeRunId = activeRun?.analysisRunId ?? null;
  const isRunning =
    activeRun?.status === "queued" || activeRun?.status === "running";

  const runQuery = useQuery({
    queryKey: ["analysis-run", projectId, activeRunId],
    queryFn: () => getAnalysisRun(projectId, activeRunId as string),
    enabled: Boolean(activeRunId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 2000 : false;
    },
    refetchIntervalInBackground: true,
  });

  const reviewersQuery = useQuery({
    queryKey: ["analysis-reviewers", projectId, activeRunId],
    queryFn: () => listReviewers(projectId, activeRunId as string),
    enabled: Boolean(activeRunId),
    refetchInterval: isRunning ? 2000 : false,
    refetchIntervalInBackground: true,
  });

  const heatmapQuery = useQuery({
    queryKey: ["analysis-heatmap", projectId, activeRunId],
    queryFn: () => getHeatmap(projectId, activeRunId as string),
    enabled: Boolean(activeRunId),
    refetchInterval: isRunning ? 3000 : false,
    refetchIntervalInBackground: true,
  });

  const findingsQuery = useQuery({
    queryKey: ["analysis-findings", projectId, activeRunId],
    queryFn: () => listFindings(projectId, activeRunId as string),
    enabled: Boolean(activeRunId),
    refetchInterval: isRunning ? 3000 : false,
    refetchIntervalInBackground: true,
  });

  const startMutation = useMutation({
    mutationFn: () => startAnalysis(projectId, { platform }),
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

  const run = runQuery.data ?? activeRun;
  const reviewers = reviewersQuery.data?.items ?? [];
  const bins = heatmapQuery.data?.bins ?? [];
  const findings = findingsQuery.data?.items ?? [];

  // Derived, never reset: a bin id from another run simply is not in these bins,
  // so switching runs drops the selection without any effect or state cleanup.
  const selectedBin = bins.find((bin) => bin.binId === selectedBinId) ?? null;

  const laneDimensions: AnalysisDimension[] =
    run?.requestedDimensions?.length
      ? run.requestedDimensions
      : CORE_DIMENSIONS;

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
              <div className="flex flex-wrap items-baseline gap-2">
                {isRunning ? (
                  <Icon
                    icon={Loading03Icon}
                    className="self-center animate-spin text-signal"
                  />
                ) : (
                  <Icon
                    icon={PlayIcon}
                    className="self-center text-muted-foreground"
                  />
                )}
                <CardTitle>Review</CardTitle>
                <span
                  className="h-4 w-px self-center bg-border"
                  aria-hidden="true"
                />
                <span className="text-sm text-muted-foreground">
                  {statusLabel(run, hasTranscript)}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {runs.length > 1 && (
                <Select
                  value={activeRunId ?? ""}
                  onValueChange={(value) =>
                    setSelectedRunId(value as string | null)
                  }
                >
                  <SelectTrigger size="sm" className="w-32">
                    <SelectValue placeholder="Latest run" />
                  </SelectTrigger>
                  <SelectContent>
                    {runs.map((item, index) => (
                      <SelectItem key={item.analysisRunId} value={item.analysisRunId}>
                        Run {runs.length - index}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
              <Button
                size="sm"
                onClick={() => startMutation.mutate()}
                disabled={
                  startMutation.isPending || isRunning || !hasTranscript
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

          {/* Instrument readout: overall score, severity census, spend. */}
          <div className="tabular flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
            <span>
              Overall{" "}
              <span className="text-foreground">
                {formatScore(run?.overallScore ?? null)}
              </span>
            </span>
            <span>
              Reviewers{" "}
              <span className="text-foreground">
                {
                  reviewers.filter((item) => item.status === "succeeded").length
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
            <span className="ml-auto">Click a segment to jump there</span>
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
                      active ? "bg-signal-foreground" : SEVERITY_DOT_CLASS[severity],
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
            />
          )}
        </CardContent>
      </Card>

      <FindingsPanel
        findings={findings}
        loading={Boolean(activeRunId) && findingsQuery.isLoading}
        running={isRunning}
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

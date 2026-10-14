"use client";

import { useState } from "react";
import {
  ArrowRight01Icon,
  Loading03Icon,
  Search01Icon,
  ViewIcon,
  ViewOffIcon,
} from "@hugeicons/core-free-icons";

import { FindingDecisionControls } from "@/components/projects/finding-decision";
import { FindingAdjudicationCard } from "@/components/projects/finding-adjudication";
import { Icon } from "@/components/common/icon";
import { FindingLibraryLinks } from "@/components/projects/finding-library-links";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  dimensionLabel,
  effectiveSeverity,
  formatDurationMs,
  formatScore,
  SEVERITY_DOT_CLASS,
  SEVERITY_LABELS,
} from "@/lib/analysis";
import type { Finding, Severity } from "@/lib/types";
import { WORKSPACE_PANE_SNAP } from "@/lib/workspace";
import { cn } from "@/lib/utils";

const SEVERITY_RANK: Record<Severity, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
  none: 4,
};

function severityRank(severity: Severity): number {
  return SEVERITY_RANK[severity] ?? 4;
}

/*
 * The findings list is the accessible path into the ribbon: every moment the
 * reviewers marked is here as a button, so the heatmap's hover and click are not
 * the only way to reach a timestamp.
 *
 * Filters come from the review panel's severity chips and from whichever bin is
 * selected on the ribbon. Nothing is hidden permanently — clearing is always one
 * click away.
 */

export function FindingsPanel({
  projectId,
  analysisRunId,
  findings,
  loading,
  running,
  reviewed,
  incomplete,
  severityFilter,
  onToggleSeverity,
  selectedFindingIds,
  onSeek,
  onClearSelection,
}: {
  projectId: string;
  analysisRunId: string;
  findings: Finding[];
  loading: boolean;
  running: boolean;
  reviewed: boolean;
  incomplete: boolean;
  severityFilter: Severity[];
  onToggleSeverity: (severity: Severity) => void;
  selectedFindingIds: string[] | null;
  onSeek: (startMs: number) => void;
  onClearSelection: () => void;
}) {
  const selectedSet = selectedFindingIds ? new Set(selectedFindingIds) : null;
  const [decisionFilter, setDecisionFilter] = useState<
    "all" | "open" | "accepted" | "revised" | "dismissed"
  >("all");
  const [showRejected, setShowRejected] = useState(false);
  const rejectedCount = findings.filter(
    (finding) => finding.adjudication?.verdict === "reject",
  ).length;
  const visible = findings
    .filter(
      (finding) => showRejected || finding.adjudication?.verdict !== "reject",
    )
    .filter((finding) => !selectedSet || selectedSet.has(finding.findingId))
    .filter(
      (finding) =>
        severityFilter.length === 0 ||
        severityFilter.includes(effectiveSeverity(finding)),
    )
    .filter(
      (finding) =>
        decisionFilter === "all" ||
        (decisionFilter === "open"
          ? !finding.decision
          : finding.decision?.status === decisionFilter),
    )
    .toSorted(
      (a, b) =>
        severityRank(effectiveSeverity(a)) -
          severityRank(effectiveSeverity(b)) || a.startMs - b.startMs,
    );

  return (
    <Card className={WORKSPACE_PANE_SNAP}>
      <CardHeader className="shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <Icon icon={Search01Icon} className="text-muted-foreground" />
            <CardTitle>Findings</CardTitle>
            <span className="h-4 w-px bg-border" aria-hidden="true" />
            <span className="text-sm text-muted-foreground">
              {selectedSet
                ? `The ${visible.length} moment${
                    visible.length === 1 ? "" : "s"
                  } on the selected segment.`
                : `${visible.length} of ${findings.length} observation${
                    findings.length === 1 ? "" : "s"
                  }, worst first.`}
            </span>
          </div>
          {selectedSet && (
            <button
              type="button"
              onClick={onClearSelection}
              className="text-xs text-signal underline-offset-4 hover:underline"
            >
              Clear selection
            </button>
          )}
        </div>
        <div
          className="flex flex-wrap items-center gap-1.5"
          aria-label="Filter finding decisions"
        >
          {(["all", "open", "accepted", "revised", "dismissed"] as const).map(
            (status) => (
              <button
                key={status}
                type="button"
                aria-pressed={decisionFilter === status}
                onClick={() => setDecisionFilter(status)}
                className={cn(
                  "rounded-full border px-2.5 py-1 text-xs capitalize focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                  decisionFilter === status
                    ? "border-signal bg-signal text-signal-foreground"
                    : "border-border text-muted-foreground hover:bg-muted",
                )}
              >
                {status === "all" ? "All decisions" : status}
              </button>
            ),
          )}
          {rejectedCount > 0 && (
            <label className="ml-auto inline-flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={showRejected}
                onChange={(event) => setShowRejected(event.target.checked)}
                className="accent-signal"
              />
              Show rejected ({rejectedCount})
            </label>
          )}
        </div>
      </CardHeader>

      <CardContent className="scroll-fade-y min-h-0 flex-1 overflow-y-auto py-2">
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        ) : visible.length === 0 ? (
          <EmptyState
            running={running}
            reviewed={reviewed}
            incomplete={incomplete}
            filtered={
              severityFilter.length > 0 ||
              Boolean(selectedSet) ||
              decisionFilter !== "all" ||
              (!showRejected && rejectedCount > 0)
            }
            onClear={() => {
              onClearSelection();
              setDecisionFilter("all");
              setShowRejected(true);
              for (const severity of severityFilter) onToggleSeverity(severity);
            }}
          />
        ) : (
          <ol className="space-y-2">
            {visible.map((finding) => (
              <FindingRow
                key={finding.findingId}
                projectId={projectId}
                analysisRunId={analysisRunId}
                finding={finding}
                allFindings={findings}
                highlighted={selectedSet?.has(finding.findingId) ?? false}
                onSeek={onSeek}
              />
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}

function FindingRow({
  projectId,
  analysisRunId,
  finding,
  allFindings,
  highlighted,
  onSeek,
}: {
  projectId: string;
  analysisRunId: string;
  finding: Finding;
  allFindings: Finding[];
  highlighted: boolean;
  onSeek: (startMs: number) => void;
}) {
  const hasEvidence = Boolean(finding.evidence.quote);
  const severity = effectiveSeverity(finding);
  return (
    <li
      className={cn(
        "group/finding relative overflow-hidden rounded-lg border border-border/70 transition-colors hover:bg-muted/40",
        highlighted && "border-signal bg-signal/10",
        finding.decision?.status === "dismissed" && "bg-muted/20",
      )}
    >
      <button
        type="button"
        onClick={() => onSeek(finding.startMs)}
        className="block w-full px-3 py-2.5 pr-10 text-left focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
          <span className="tabular text-xs text-time">
            {formatDurationMs(finding.startMs)}
          </span>
          <span className="inline-flex items-center gap-1.5 text-xs">
            <span
              className={cn(
                "size-1.5 rounded-full",
                SEVERITY_DOT_CLASS[severity],
              )}
            />
            <span className="text-muted-foreground">
              {SEVERITY_LABELS[severity]}
              {severity !== finding.severity && (
                <span className="ml-1 text-[11px]">
                  (was {SEVERITY_LABELS[finding.severity]})
                </span>
              )}
            </span>
          </span>
          <span className="text-xs text-muted-foreground">
            {dimensionLabel(finding.dimension)}
          </span>
          <span className="tabular ml-auto text-xs text-muted-foreground">
            {formatScore(finding.score)}
          </span>
        </div>

        {finding.evidence.critique_and_reasoning && (
          <p className="mt-1.5 text-sm text-foreground/90">
            {finding.evidence.critique_and_reasoning}
          </p>
        )}

        {finding.suggestion && (
          <p className="mt-1.5 flex items-start gap-1.5 text-sm text-foreground/90">
            <Icon
              icon={ArrowRight01Icon}
              className="mt-0.5 size-3.5 shrink-0 text-signal"
            />
            <span className="min-w-0 break-words">{finding.suggestion}</span>
          </p>
        )}
      </button>

      {(finding.severity === "high" || finding.severity === "critical") && (
        <FindingAdjudicationCard
          projectId={projectId}
          analysisRunId={analysisRunId}
          finding={finding}
          onSeek={onSeek}
        />
      )}

      {finding.reconciliation && (
        <div className="space-y-1.5 border-t border-signal/20 bg-signal/5 px-3 py-2.5">
          <p className="text-xs font-medium text-signal">
            Combined recommendation
          </p>
          <p className="text-sm">{finding.reconciliation.recommendation}</p>
          <p className="text-xs text-muted-foreground">
            {finding.reconciliation.reason}
          </p>
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
            <span>Reconciles</span>
            {finding.reconciliation.findingIds.map((id) => {
              const related = allFindings.find((item) => item.findingId === id);
              return related ? (
                <button
                  key={id}
                  type="button"
                  onClick={() => onSeek(related.startMs)}
                  className="text-signal underline-offset-2 hover:underline"
                >
                  {dimensionLabel(related.dimension)} ·{" "}
                  {formatDurationMs(related.startMs)}
                </button>
              ) : null;
            })}
          </div>
          <p className="text-[11px] text-muted-foreground">
            Use Revise to choose this combined action.
          </p>
        </div>
      )}

      <FindingDecisionControls
        projectId={projectId}
        analysisRunId={analysisRunId}
        finding={finding}
      />

      {/* Grounded reviewers cite the web sources behind a claim. */}
      {finding.citations.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-border/60 px-3 py-1.5">
          <span className="text-[11px] text-muted-foreground">Sources</span>
          {finding.citations.map((citation, index) =>
            citation.url ? (
              <a
                key={citation.url}
                href={citation.url}
                target="_blank"
                rel="noreferrer"
                className="max-w-[18rem] truncate text-[11px] text-signal underline-offset-2 hover:underline"
              >
                {citation.title || citation.url}
              </a>
            ) : (
              <span
                key={`${citation.title}-${index}`}
                className="text-[11px] text-muted-foreground"
              >
                {citation.title}
              </span>
            ),
          )}
        </div>
      )}

      <FindingLibraryLinks links={finding.libraryLinks} />
      {/* The transcript evidence is kept, but tucked away so rows stay scannable. */}
      {hasEvidence && (
        <details className="group border-t border-border/60">
          <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground">
            <Icon icon={ViewIcon} className="size-3.5 group-open:hidden" />
            <Icon
              icon={ViewOffIcon}
              className="hidden size-3.5 group-open:inline"
            />
            <span className="group-open:hidden">Show evidence</span>
            <span className="hidden group-open:inline">Hide evidence</span>
          </summary>
          <div className="space-y-1.5 px-3 pb-2.5">
            {finding.evidence.quote && (
              <p className="text-sm text-foreground/90">
                <span className="text-muted-foreground">“</span>
                {finding.evidence.quote}
                <span className="text-muted-foreground">”</span>
              </p>
            )}
          </div>
        </details>
      )}
    </li>
  );
}

function EmptyState({
  running,
  reviewed,
  incomplete,
  filtered,
  onClear,
}: {
  running: boolean;
  reviewed: boolean;
  incomplete: boolean;
  filtered: boolean;
  onClear: () => void;
}) {
  return (
    <div className="rounded-lg border border-dashed border-border/70 px-4 py-8 text-center">
      {running ? (
        <>
          <Icon
            icon={Loading03Icon}
            className="mx-auto size-5 animate-spin text-signal"
          />
          <p className="mt-2 text-sm text-muted-foreground">
            Findings land here as each reviewer finishes.
          </p>
        </>
      ) : filtered ? (
        <>
          <p className="text-sm text-foreground">
            Nothing matches this filter.
          </p>
          <button
            type="button"
            onClick={onClear}
            className="mt-2 text-xs text-signal underline-offset-4 hover:underline"
          >
            Clear the filters
          </button>
        </>
      ) : reviewed ? (
        <>
          <p className="text-sm text-foreground">
            {incomplete
              ? "The review could not check everything."
              : "No changes flagged."}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            {incomplete
              ? "Run the analysis again to check the remaining parts."
              : "The reviewers found no specific edits to suggest. Unmarked time has no score."}
          </p>
        </>
      ) : (
        <>
          <p className="text-sm text-foreground">No findings yet.</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Run an analysis and the reviewers will mark what works and what
            breaks.
          </p>
        </>
      )}
    </div>
  );
}

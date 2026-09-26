"use client";

import {
  ArrowRight01Icon,
  Loading03Icon,
  Search01Icon,
} from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  dimensionLabel,
  formatDurationMs,
  formatFindingType,
  formatScore,
  SEVERITY_DOT_CLASS,
  SEVERITY_LABELS,
} from "@/lib/analysis";
import type { Finding, Severity } from "@/lib/types";
import { WORKSPACE_PANE_STICKY } from "@/lib/workspace";
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
  findings,
  loading,
  running,
  severityFilter,
  onToggleSeverity,
  selectedFindingIds,
  onSeek,
  onClearSelection,
}: {
  findings: Finding[];
  loading: boolean;
  running: boolean;
  severityFilter: Severity[];
  onToggleSeverity: (severity: Severity) => void;
  selectedFindingIds: string[] | null;
  onSeek: (startMs: number) => void;
  onClearSelection: () => void;
}) {
  const selectedSet = selectedFindingIds ? new Set(selectedFindingIds) : null;
  const visible = findings
    .filter((finding) =>
      selectedSet ? selectedSet.has(finding.findingId) : true,
    )
    .filter((finding) =>
      severityFilter.length === 0
        ? true
        : severityFilter.includes(finding.severity),
    )
    .toSorted(
      // Problems first, then by how early they happen.
      (a, b) =>
        severityRank(a.severity) - severityRank(b.severity) || a.startMs - b.startMs,
    );

  return (
    <Card className={WORKSPACE_PANE_STICKY}>
      <CardHeader className="shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Icon icon={Search01Icon} className="text-muted-foreground" />
              Findings
            </CardTitle>
            <CardDescription>
              {selectedSet
                ? `The ${visible.length} moment${
                    visible.length === 1 ? "" : "s"
                  } marked on the selected segment.`
                : `${visible.length} of ${findings.length} observation${
                    findings.length === 1 ? "" : "s"
                  }, worst first.`}
            </CardDescription>
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
      </CardHeader>

      <CardContent className="min-h-0 flex-1 overflow-y-auto">
        {loading ? (
          <div className="space-y-2">
            <Skeleton className="h-14 w-full" />
            <Skeleton className="h-14 w-full" />
          </div>
        ) : visible.length === 0 ? (
          <EmptyState
            running={running}
            filtered={severityFilter.length > 0 || Boolean(selectedSet)}
            onClear={() => {
              onClearSelection();
              for (const severity of severityFilter) onToggleSeverity(severity);
            }}
          />
        ) : (
          <ol className="space-y-2">
            {visible.map((finding) => (
              <FindingRow
                key={finding.findingId}
                finding={finding}
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
  finding,
  highlighted,
  onSeek,
}: {
  finding: Finding;
  highlighted: boolean;
  onSeek: (startMs: number) => void;
}) {
  const hasEvidence = Boolean(
    finding.evidence.quote || finding.evidence.explanation,
  );
  return (
    <li
      className={cn(
        "overflow-hidden rounded-lg border border-border/70 transition-colors hover:bg-muted/40",
        highlighted && "border-signal bg-signal/10",
      )}
    >
      <button
        type="button"
        onClick={() => onSeek(finding.startMs)}
        className="block w-full px-3 py-2.5 text-left focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
          <span className="tabular text-xs text-signal">
            {formatDurationMs(finding.startMs)}
          </span>
          <span className="inline-flex items-center gap-1.5 text-xs">
            <span
              className={cn(
                "size-1.5 rounded-full",
                SEVERITY_DOT_CLASS[finding.severity],
              )}
            />
            <span className="text-muted-foreground">
              {SEVERITY_LABELS[finding.severity]}
            </span>
          </span>
          <span className="text-xs text-muted-foreground">
            {dimensionLabel(finding.dimension)}
          </span>
          <span className="tabular rounded-4xl bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
            {formatFindingType(finding.findingType)}
          </span>
          <span className="tabular ml-auto text-xs text-muted-foreground">
            {formatScore(finding.score)}
          </span>
        </div>

        {finding.suggestion && (
          <p className="mt-1.5 flex items-start gap-1.5 text-sm text-foreground/90">
            <Icon
              icon={ArrowRight01Icon}
              className="mt-0.5 size-3.5 shrink-0 text-signal"
            />
            <span>{finding.suggestion}</span>
          </p>
        )}
      </button>

      {/* The transcript evidence is kept, but tucked away so rows stay scannable. */}
      {hasEvidence && (
        <details className="group border-t border-border/60">
          <summary className="cursor-pointer list-none px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground">
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
            {finding.evidence.explanation && (
              <p className="text-xs text-muted-foreground">
                {finding.evidence.explanation}
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
  filtered,
  onClear,
}: {
  running: boolean;
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
          <p className="text-sm text-foreground">Nothing matches this filter.</p>
          <button
            type="button"
            onClick={onClear}
            className="mt-2 text-xs text-signal underline-offset-4 hover:underline"
          >
            Clear the filters
          </button>
        </>
      ) : (
        <>
          <p className="text-sm text-foreground">No findings yet.</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Run an analysis and the reviewers will mark what works and what breaks.
          </p>
        </>
      )}
    </div>
  );
}

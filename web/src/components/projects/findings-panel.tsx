"use client";

import { useState } from "react";
import {
  ArrowRight01Icon,
  Cancel01Icon,
  Loading03Icon,
  Search01Icon,
  ViewIcon,
  ViewOffIcon,
} from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import {
  Card,
  CardContent,
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
  // Ignored findings stay visible but greyed and sorted to the bottom.
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const visible = findings
    .filter((finding) =>
      selectedSet ? selectedSet.has(finding.findingId) : true,
    )
    .filter((finding) =>
      severityFilter.length === 0
        ? true
        : severityFilter.includes(finding.severity),
    )
    .toSorted((a, b) => {
      const aDismissed = dismissed.has(a.findingId) ? 1 : 0;
      const bDismissed = dismissed.has(b.findingId) ? 1 : 0;
      if (aDismissed !== bDismissed) return aDismissed - bDismissed;
      // Problems first, then by how early they happen.
      return (
        severityRank(a.severity) - severityRank(b.severity) ||
        a.startMs - b.startMs
      );
    });

  function toggleDismiss(findingId: string) {
    setDismissed((current) => {
      const next = new Set(current);
      if (next.has(findingId)) next.delete(findingId);
      else next.add(findingId);
      return next;
    });
  }

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
                dismissed={dismissed.has(finding.findingId)}
                onDismiss={() => toggleDismiss(finding.findingId)}
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
  dismissed,
  onDismiss,
  onSeek,
}: {
  finding: Finding;
  highlighted: boolean;
  dismissed: boolean;
  onDismiss: () => void;
  onSeek: (startMs: number) => void;
}) {
  const hasEvidence = Boolean(
    finding.evidence.quote || finding.evidence.critique_and_reasoning,
  );
  return (
    <li
      className={cn(
        "group/finding relative overflow-hidden rounded-lg border border-border/70 transition-colors hover:bg-muted/40",
        highlighted && "border-signal bg-signal/10",
        dismissed && "opacity-50 hover:opacity-80",
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

        {dismissed ? (
          <span className="mt-1 inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Icon icon={Cancel01Icon} className="size-3" />
            Ignored
          </span>
        ) : null}

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

      <button
        type="button"
        aria-label={dismissed ? "Unignore finding" : "Ignore finding"}
        title={dismissed ? "Unignore finding" : "Ignore finding"}
        onClick={onDismiss}
        aria-pressed={dismissed}
        className="absolute top-2 right-2 flex size-6 items-center justify-center rounded-md text-muted-foreground opacity-0 transition-opacity group-hover/finding:opacity-100 hover:bg-muted hover:text-foreground focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50 aria-pressed:opacity-100"
      >
        <Icon icon={Cancel01Icon} className="size-3.5" />
      </button>

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

      {/* The transcript evidence is kept, but tucked away so rows stay scannable. */}
      {hasEvidence && (
        <details className="group border-t border-border/60">
          <summary className="flex cursor-pointer list-none items-center gap-1.5 px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground">
            <Icon icon={ViewIcon} className="size-3.5 group-open:hidden" />
            <Icon icon={ViewOffIcon} className="hidden size-3.5 group-open:inline" />
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
            {finding.evidence.critique_and_reasoning && (
              <p className="text-xs text-muted-foreground">
                {finding.evidence.critique_and_reasoning}
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

"use client";

import {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";

import {
  dimensionLabel,
  formatDurationMs,
  formatScore,
  heatFill,
  SEVERITY_DOT_CLASS,
  SEVERITY_LABELS,
} from "@/lib/analysis";
import {
  InterestLanes,
  InterestReadout,
  LABEL_COLUMN,
  usableCurve,
} from "@/components/projects/interest-lanes";
import type {
  AnalysisDimension,
  HeatmapBin,
  HeatmapCoverage,
  InterestCurve,
  InterestMoment,
  Severity,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const EMPTY_BINS: HeatmapBin[] = [];
const EMPTY_SEVERITIES: Severity[] = [];
const EMPTY_COVERAGE: HeatmapCoverage[] = [];

/** What the readout strip is describing: a bin, an interest point, or a gap. */
type Hover =
  | { kind: "bin"; bin: HeatmapBin }
  | { kind: "interest"; index: number }
  | { kind: "gap"; dimension: AnalysisDimension; covered: boolean };

/*
 * The review ribbon: one signal trace per reviewer dimension, plotted against the
 * video timeline. Time runs left to right, a row is a dimension, colour is quality.
 *
 * Colour is the review signal in this product, so it is not the only channel:
 * a critical bin carries a bright notch in its centre, which makes the dangerous
 * moments findable by silhouette alone. Unreviewed stretches stay quiet rather
 * than being painted with invented scores.
 *
 * Hovering paints the readout strip at the top of the block instead of floating a
 * tooltip — a scope meter, always in the same place, that also announces to screen
 * readers. Every bin is clickable: it seeks the video and selects that moment's
 * findings.
 *
 * Keyboard access uses a roving tabindex: Tab lands on each reviewer track once,
 * then the arrow keys walk the bins on that track. That keeps one stop per reviewer
 * instead of one stop per five-second bin, while still reaching every moment.
 */

export function HeatmapTracks({
  bins,
  coverage = EMPTY_COVERAGE,
  interest = null,
  onSelectMoment,
  durationMs,
  dimensions,
  scores,
  onSeek,
  selectedBinId,
  onSelectBin,
  severityFilter = EMPTY_SEVERITIES,
  reviewState = "not_started",
}: {
  bins: HeatmapBin[];
  /** Spans each dimension read; empty for older runs (gaps then stay blank). */
  coverage?: HeatmapCoverage[];
  /** Predicted audience-interest curve; null hides the interest and signal lanes. */
  interest?: InterestCurve | null;
  onSelectMoment?: (moment: InterestMoment) => void;
  durationMs: number;
  dimensions: AnalysisDimension[];
  scores: Record<string, number>;
  onSeek: (startMs: number) => void;
  selectedBinId: string | null;
  onSelectBin: (bin: HeatmapBin | null) => void;
  /** Severities the review panel is currently filtering to; others are dimmed. */
  severityFilter?: Severity[];
  reviewState?: "not_started" | "running" | "complete" | "incomplete";
}) {
  const [hover, setHover] = useState<Hover | null>(null);
  const setHovered = useCallback(
    (bin: HeatmapBin | null) => setHover(bin ? { kind: "bin", bin } : null),
    [],
  );
  const setHoveredGap = useCallback(
    (gap: { dimension: AnalysisDimension; covered: boolean } | null) =>
      setHover((current) =>
        gap === null
          ? current?.kind === "gap"
            ? null
            : current
          : current?.kind === "gap" &&
              current.dimension === gap.dimension &&
              current.covered === gap.covered
            ? current
            : { kind: "gap", ...gap },
      ),
    [],
  );
  const setHoveredPoint = useCallback(
    (index: number | null) =>
      setHover(index === null ? null : { kind: "interest", index }),
    [],
  );

  const curve = usableCurve(interest);
  const coverageByDimension = useMemo(() => {
    const map = new Map<AnalysisDimension, HeatmapCoverage[]>();
    for (const span of coverage) {
      const list = map.get(span.dimension) ?? [];
      list.push(span);
      map.set(span.dimension, list);
    }
    return map;
  }, [coverage]);

  const byDimension = useMemo(() => {
    const map = new Map<AnalysisDimension, HeatmapBin[]>();
    for (const bin of bins) {
      const list = map.get(bin.dimension) ?? [];
      list.push(bin);
      map.set(bin.dimension, list);
    }
    for (const list of map.values()) {
      list.sort((a, b) => a.startMs - b.startMs);
    }
    return map;
  }, [bins]);

  const rulerTicks = useMemo(() => makeTicks(durationMs), [durationMs]);
  const byId = useMemo(
    () => new Map(bins.map((bin) => [bin.binId, bin])),
    [bins],
  );
  // Drop a hover that belongs to a previous run rather than showing stale data.
  const hoveredBin =
    hover?.kind === "bin" ? (byId.get(hover.bin.binId) ?? null) : null;
  const hoveredPoint =
    hover?.kind === "interest" ? (curve?.points[hover.index] ?? null) : null;
  const hoveredGap = hover?.kind === "gap" ? hover : null;
  const selectedBin = selectedBinId ? byId.get(selectedBinId) : null;
  const select = useCallback(
    (bin: HeatmapBin) => {
      onSelectBin(bin);
      onSeek(bin.startMs);
    },
    [onSelectBin, onSeek],
  );

  if (durationMs <= 0 || dimensions.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No timeline to plot against yet.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <ReadoutStrip
        bin={hoveredBin}
        point={hoveredPoint}
        gap={hoveredGap}
        dimensions={dimensions.length}
      />

      <div className="overflow-hidden rounded-lg border border-border/70 bg-card/40">
        <TimeRuler ticks={rulerTicks} />

        <div className="space-y-[6px] p-1">
          {curve && onSelectMoment && (
            <InterestLanes
              curve={curve}
              durationMs={durationMs}
              hoverIndex={hover?.kind === "interest" ? hover.index : null}
              onHoverIndex={setHoveredPoint}
              onSeek={onSeek}
              onSelectMoment={onSelectMoment}
            />
          )}
          {bins.length === 0 && (
            <p className="px-2 py-6 text-center text-sm text-muted-foreground">
              {reviewState === "complete"
                ? "No moments flagged."
                : reviewState === "incomplete"
                  ? "Review incomplete. No findings available."
                  : reviewState === "running"
                    ? "Findings will appear as reviewers finish."
                    : "Run a review to find moments worth editing."}
            </p>
          )}
          {dimensions.map((dimension) => {
            const dimensionBins = byDimension.get(dimension) ?? EMPTY_BINS;
            return (
              <TrackRow
                key={dimension}
                dimension={dimension}
                bins={dimensionBins}
                coverage={
                  coverage.length > 0
                    ? (coverageByDimension.get(dimension) ?? EMPTY_COVERAGE)
                    : null
                }
                durationMs={durationMs}
                score={scores[dimension]}
                hoveredBinId={
                  hoveredBin?.dimension === dimension ? hoveredBin.binId : null
                }
                selectedBinId={
                  selectedBin?.dimension === dimension
                    ? selectedBin.binId
                    : null
                }
                severityFilter={severityFilter}
                onHover={setHovered}
                onHoverGap={setHoveredGap}
                onSelect={select}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}

/** Hairline time ruler. Ticks sit at their true percentage, not evenly spaced. */
function TimeRuler({ ticks }: { ticks: number[] }) {
  // Mirror the TrackRow layout (inset + label column + gap + score column) so
  // the ticks line up with the bars instead of floating over the labels.
  return (
    <div className="flex items-center gap-1.5 border-b border-border/70 px-1 sm:gap-2">
      <span className="w-20 shrink-0 sm:w-[8.5rem]" aria-hidden="true" />
      <div className="relative h-5 flex-1">
        {ticks.map((tick, index) => {
          const position =
            ticks.length > 1 ? (index / (ticks.length - 1)) * 100 : 0;
          return (
            <span
              key={tick}
              className={cn(
                "tabular absolute bottom-0.5 text-[10px] leading-none text-muted-foreground/80",
                index === 0
                  ? "left-0"
                  : index === ticks.length - 1
                    ? "right-0"
                    : "-translate-x-1/2",
                // Five labels collide on a phone-width track; keep 0/50/100%.
                index % 2 === 1 && "hidden sm:inline",
              )}
              style={
                index === 0 || index === ticks.length - 1
                  ? undefined
                  : { left: `${position}%` }
              }
            >
              {formatDurationMs(tick)}
            </span>
          );
        })}
      </div>
      <span className="w-9 shrink-0" aria-hidden="true" />
    </div>
  );
}

const TrackRow = memo(function TrackRow({
  dimension,
  bins,
  coverage,
  durationMs,
  score,
  hoveredBinId,
  selectedBinId,
  severityFilter,
  onHover,
  onHoverGap,
  onSelect,
}: {
  dimension: AnalysisDimension;
  bins: HeatmapBin[];
  /** This dimension's reviewed spans, or null when the run has no coverage data. */
  coverage: HeatmapCoverage[] | null;
  durationMs: number;
  score: number | undefined;
  hoveredBinId: string | null;
  selectedBinId: string | null;
  severityFilter: Severity[];
  onHover: (bin: HeatmapBin | null) => void;
  onHoverGap: (
    gap: { dimension: AnalysisDimension; covered: boolean } | null,
  ) => void;
  onSelect: (bin: HeatmapBin) => void;
}) {
  // Roving tabindex: the row is one tab stop, arrows walk its bins.
  const [rover, setRover] = useState(0);
  const trackRef = useRef<HTMLDivElement | null>(null);
  // Clamp at render time too, so a shorter run cannot leave the row unfocusable.
  const active = Math.min(rover, Math.max(0, bins.length - 1));

  // Clearing the readout on pointer exit is a DOM concern, not a JSX one: a
  // `mouseleave` prop on a plain div is a lint failure with no a11y meaning.
  useEffect(() => {
    const node = trackRef.current;
    if (!node) return;
    const leave = () => onHover(null);
    node.addEventListener("mouseleave", leave);
    return () => node.removeEventListener("mouseleave", leave);
  }, [onHover]);

  // Over empty track (not a bin), say whether that time was read. Only when the
  // run carries coverage; older runs keep the plain blank gap.
  useEffect(() => {
    const node = trackRef.current;
    if (!node || coverage === null) return;
    const move = (event: MouseEvent) => {
      if ((event.target as Element).closest("button")) return;
      const rect = node.getBoundingClientRect();
      if (rect.width <= 0) return;
      const ms = ((event.clientX - rect.left) / rect.width) * durationMs;
      onHoverGap({
        dimension,
        covered: coverage.some((span) => ms >= span.startMs && ms < span.endMs),
      });
    };
    node.addEventListener("mousemove", move);
    return () => node.removeEventListener("mousemove", move);
  }, [coverage, durationMs, dimension, onHoverGap]);

  function focusBin(button: HTMLButtonElement, next: number) {
    const clamped = Math.max(0, Math.min(bins.length - 1, next));
    setRover(clamped);
    const siblings = button.parentElement?.querySelectorAll("button");
    siblings?.[clamped]?.focus();
  }

  function onBinKeyDown(
    event: ReactKeyboardEvent<HTMLButtonElement>,
    index: number,
  ) {
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      event.preventDefault();
      focusBin(event.currentTarget, index + 1);
    } else if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault();
      focusBin(event.currentTarget, index - 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      focusBin(event.currentTarget, 0);
    } else if (event.key === "End") {
      event.preventDefault();
      focusBin(event.currentTarget, bins.length - 1);
    }
  }

  return (
    <div className="flex items-center gap-1.5 sm:gap-2">
      <span
        className={cn(
          LABEL_COLUMN,
          "truncate text-[11px] text-muted-foreground",
        )}
      >
        {dimensionLabel(dimension)}
      </span>

      <div
        ref={trackRef}
        className="relative h-5 flex-1 overflow-hidden rounded-[3px] bg-muted/60"
      >
        {/* Read but nothing flagged: a faint tint, so quiet is distinct from unread. */}
        {coverage?.map((span, index) => (
          <span
            key={`${span.startMs}-${index}`}
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 bg-foreground/[0.07]"
            style={{
              left: `${(span.startMs / durationMs) * 100}%`,
              width: `${((span.endMs - span.startMs) / durationMs) * 100}%`,
            }}
          />
        ))}
        {bins.map((bin, index) => {
          const left = (bin.startMs / durationMs) * 100;
          const width = ((bin.endMs - bin.startMs) / durationMs) * 100;
          const isHovered = bin.binId === hoveredBinId;
          const isSelected = bin.binId === selectedBinId;
          const isDimmed =
            severityFilter.length > 0 && !severityFilter.includes(bin.severity);
          return (
            <button
              key={bin.binId}
              type="button"
              // One stop per track; arrows move within it.
              tabIndex={index === active ? 0 : -1}
              aria-label={`${dimensionLabel(dimension)} ${formatDurationMs(
                bin.startMs,
              )}, score ${formatScore(bin.score)}, ${SEVERITY_LABELS[bin.severity]}`}
              onMouseEnter={() => onHover(bin)}
              onFocus={() => onHover(bin)}
              onClick={() => onSelect(bin)}
              onKeyDown={(event) => onBinKeyDown(event, index)}
              className={cn(
                "absolute top-0 bottom-0 border-r border-card/70 transition-[filter,opacity,transform] duration-150",
                heatFill(bin),
                isDimmed && !isHovered && !isSelected && "opacity-25",
                isHovered && "z-10 brightness-125",
                isSelected && "z-20 ring-2 ring-signal ring-inset",
              )}
              style={{
                left: `${left}%`,
                width: `max(2px, calc(${width}% - 1px))`,
              }}
            >
              {/* Critical moments notch the bar so they are findable without colour. */}
              {bin.severity === "critical" && (
                <span className="absolute inset-y-[3px] left-1/2 w-[2px] -translate-x-1/2 rounded-full bg-card/90" />
              )}
            </button>
          );
        })}
      </div>

      <span
        className="tabular w-9 shrink-0 text-right text-[11px] text-muted-foreground"
        aria-hidden="true"
      >
        {score === undefined ? "—" : formatScore(score)}
      </span>
    </div>
  );
});

function ReadoutStrip({
  bin,
  point,
  gap,
  dimensions,
}: {
  bin: HeatmapBin | null;
  point: InterestCurve["points"][number] | null;
  gap: { dimension: AnalysisDimension; covered: boolean } | null;
  dimensions: number;
}) {
  return (
    <div
      aria-live="polite"
      className="tabular flex min-h-8 flex-wrap items-center gap-x-3 gap-y-0.5 rounded-lg border border-border/70 bg-muted/40 px-3 text-[11px] text-muted-foreground"
    >
      {point ? (
        <InterestReadout point={point} />
      ) : gap ? (
        <>
          <span className="text-foreground">
            {dimensionLabel(gap.dimension)}
          </span>
          <span>
            {gap.covered ? "Reviewed — nothing flagged" : "Not reviewed"}
          </span>
        </>
      ) : bin ? (
        <>
          <span className="text-time">
            {formatDurationMs(bin.startMs)}–{formatDurationMs(bin.endMs)}
          </span>
          <span className="text-foreground">{formatScore(bin.score)}</span>
          <span className="inline-flex items-center gap-1.5">
            <span
              className={cn(
                "size-1.5 rounded-full",
                SEVERITY_DOT_CLASS[bin.severity],
              )}
            />
            {SEVERITY_LABELS[bin.severity]}
          </span>
          <span className="truncate">
            {dimensionLabel(bin.dimension)}
            {bin.findingIds.length > 0 &&
              ` · ${bin.findingIds.length} finding${
                bin.findingIds.length === 1 ? "" : "s"
              }`}
          </span>
          <span className="ml-auto hidden text-muted-foreground/70 sm:inline">
            Click to jump
          </span>
        </>
      ) : (
        <span>
          {dimensions} reviewer {dimensions === 1 ? "track" : "tracks"} · hover
          a segment to inspect it. Gaps have no score.
        </span>
      )}
    </div>
  );
}

function makeTicks(durationMs: number): number[] {
  if (durationMs <= 0) return [];
  const count = 5;
  return Array.from({ length: count }, (_, index) =>
    Math.round((durationMs * index) / (count - 1)),
  );
}

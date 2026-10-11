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
import type { AnalysisDimension, HeatmapBin, Severity } from "@/lib/types";
import { cn } from "@/lib/utils";

const EMPTY_BINS: HeatmapBin[] = [];
const EMPTY_SEVERITIES: Severity[] = [];

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
 * then the arrow keys walk the bins on that track. That keeps a six-stop tab order
 * instead of one stop per five-second bin, while still reaching every moment.
 */

export function HeatmapTracks({
  bins,
  durationMs,
  dimensions,
  scores,
  onSeek,
  selectedBinId,
  onSelectBin,
  severityFilter = EMPTY_SEVERITIES,
}: {
  bins: HeatmapBin[];
  durationMs: number;
  dimensions: AnalysisDimension[];
  scores: Record<string, number>;
  onSeek: (startMs: number) => void;
  selectedBinId: string | null;
  onSelectBin: (bin: HeatmapBin | null) => void;
  /** Severities the review panel is currently filtering to; others are dimmed. */
  severityFilter?: Severity[];
}) {
  const [hovered, setHovered] = useState<HeatmapBin | null>(null);

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
  const hoveredBin = hovered ? (byId.get(hovered.binId) ?? null) : null;
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
      <ReadoutStrip bin={hoveredBin} dimensions={dimensions.length} />

      <div className="overflow-hidden rounded-lg border border-border/70 bg-card/40">
        <TimeRuler ticks={rulerTicks} />

        <div className="space-y-[6px] p-1">
          {bins.length === 0 ? (
            <p className="px-2 py-6 text-center text-sm text-muted-foreground">
              No reviewer has marked this timeline yet.
            </p>
          ) : (
            dimensions.map((dimension) => {
              const dimensionBins = byDimension.get(dimension) ?? EMPTY_BINS;
              return (
                <TrackRow
                  key={dimension}
                  dimension={dimension}
                  bins={dimensionBins}
                  durationMs={durationMs}
                  score={scores[dimension]}
                  hoveredBinId={
                    hoveredBin?.dimension === dimension
                      ? hoveredBin.binId
                      : null
                  }
                  selectedBinId={
                    selectedBin?.dimension === dimension
                      ? selectedBin.binId
                      : null
                  }
                  severityFilter={severityFilter}
                  onHover={setHovered}
                  onSelect={select}
                />
              );
            })
          )}
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
  durationMs,
  score,
  hoveredBinId,
  selectedBinId,
  severityFilter,
  onHover,
  onSelect,
}: {
  dimension: AnalysisDimension;
  bins: HeatmapBin[];
  durationMs: number;
  score: number | undefined;
  hoveredBinId: string | null;
  selectedBinId: string | null;
  severityFilter: Severity[];
  onHover: (bin: HeatmapBin | null) => void;
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
      <span className="w-20 shrink-0 truncate text-[11px] text-muted-foreground sm:w-[8.5rem]">
        {dimensionLabel(dimension)}
      </span>

      <div
        ref={trackRef}
        className="relative h-5 flex-1 overflow-hidden rounded-[3px] bg-muted/60"
      >
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
  dimensions,
}: {
  bin: HeatmapBin | null;
  dimensions: number;
}) {
  return (
    <div
      aria-live="polite"
      className="tabular flex min-h-8 items-center gap-3 rounded-lg border border-border/70 bg-muted/40 px-3 text-[11px] text-muted-foreground"
    >
      {bin ? (
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
          a segment to inspect it
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

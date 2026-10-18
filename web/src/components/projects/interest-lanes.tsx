"use client";

import {
  useId,
  useMemo,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
} from "react";
import {
  ArrowDown01Icon,
  ArrowRight01Icon,
  ArrowUp01Icon,
  InformationCircleIcon,
} from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { InterestCalibrationPanel } from "@/components/projects/interest-calibration-panel";
import { formatDurationMs } from "@/lib/analysis";
import type { InterestCurve, InterestMoment, InterestPoint } from "@/lib/types";
import { cn } from "@/lib/utils";

/*
 * Audience interest: a predicted, relative curve over the same timeline as the
 * reviewer tracks. It ranks moments within this video; it is not retention, so
 * the UI only ever says a qualitative level, never a percentage.
 *
 * Each lane is one slider-like stop: hover or the arrow keys pick a point, which
 * paints the shared readout strip; click or Enter seeks. Peak and dip markers are
 * separate buttons so they can also pull up the findings that overlap them.
 */

// Lane geometry in viewBox percent: padding keeps markers inside the lane.
const Y_TOP = 20;
const Y_SPAN = 60;

export const LABEL_COLUMN = "w-20 shrink-0 sm:w-[8.5rem]";

export function interestLevel(value: number): string {
  if (value >= 0.8) return "High";
  if (value >= 0.6) return "Above average";
  if (value >= 0.4) return "Average";
  if (value >= 0.2) return "Below average";
  return "Low";
}

function xPct(point: { startMs: number; endMs: number }, durationMs: number) {
  return ((point.startMs + point.endMs) / 2 / durationMs) * 100;
}

function yPct(value: number) {
  return Y_TOP + Y_SPAN * (1 - Math.min(1, Math.max(0, value)));
}

/** Flat-tangent cubic through the points: smooth without overshooting 0 or 1. */
function smoothPath(coords: Array<[number, number]>): string {
  if (coords.length === 0) return "";
  let path = `M${coords[0][0]},${coords[0][1]}`;
  for (let i = 1; i < coords.length; i++) {
    const [x0, y0] = coords[i - 1];
    const [x1, y1] = coords[i];
    const mid = (x0 + x1) / 2;
    path += ` C${mid},${y0} ${mid},${y1} ${x1},${y1}`;
  }
  return path;
}

function straightPath(coords: Array<[number, number]>): string {
  return coords.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x},${y}`).join(" ");
}

function pointIndexAt(points: InterestPoint[], ms: number): number {
  let found = 0;
  for (let i = 0; i < points.length; i++) {
    if (points[i].startMs <= ms) found = i;
    else break;
  }
  return found;
}

export function usableCurve(curve: InterestCurve | null | undefined) {
  return curve && curve.status !== "failed" && curve.points.length > 0
    ? curve
    : null;
}

/** Hover, focus, click and arrow-key handling shared by every lane. */
function ScrubLane({
  points,
  durationMs,
  hoverIndex,
  onHoverIndex,
  onSeek,
  label,
  valueText,
  className,
  children,
}: {
  points: InterestPoint[];
  durationMs: number;
  hoverIndex: number | null;
  onHoverIndex: (index: number | null) => void;
  onSeek: (startMs: number) => void;
  label: string;
  valueText: string;
  className?: string;
  children: ReactNode;
}) {
  function indexFromPointer(event: ReactMouseEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    if (rect.width <= 0) return 0;
    const fraction = Math.min(
      1,
      Math.max(0, (event.clientX - rect.left) / rect.width),
    );
    return pointIndexAt(points, fraction * durationMs);
  }

  function onKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    const current = hoverIndex ?? 0;
    let next: number | null = null;
    if (event.key === "ArrowRight" || event.key === "ArrowUp")
      next = current + 1;
    else if (event.key === "ArrowLeft" || event.key === "ArrowDown")
      next = current - 1;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = points.length - 1;
    else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      const point = points[Math.min(current, points.length - 1)];
      if (point) onSeek(point.startMs);
      return;
    }
    if (next !== null) {
      event.preventDefault();
      onHoverIndex(Math.max(0, Math.min(points.length - 1, next)));
    }
  }

  return (
    <div
      role="slider"
      tabIndex={0}
      aria-label={label}
      aria-orientation="horizontal"
      aria-valuemin={0}
      aria-valuemax={durationMs}
      aria-valuenow={points[hoverIndex ?? 0]?.startMs ?? 0}
      aria-valuetext={valueText}
      onMouseMove={(event) => onHoverIndex(indexFromPointer(event))}
      onMouseLeave={() => onHoverIndex(null)}
      onClick={(event) => {
        const point = points[indexFromPointer(event)];
        if (point) onSeek(point.startMs);
      }}
      onFocus={() => {
        if (hoverIndex === null) onHoverIndex(0);
      }}
      onBlur={() => onHoverIndex(null)}
      onKeyDown={onKeyDown}
      className={cn(
        "absolute inset-0 cursor-pointer rounded-[3px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60",
        className,
      )}
    >
      {children}
    </div>
  );
}

function CursorLine({
  point,
  durationMs,
}: {
  point: InterestPoint | undefined;
  durationMs: number;
}) {
  if (!point) return null;
  return (
    <span
      aria-hidden="true"
      className="pointer-events-none absolute inset-y-0 w-px bg-foreground/40"
      style={{ left: `${xPct(point, durationMs)}%` }}
    />
  );
}

export function InterestLanes({
  curve,
  durationMs,
  hoverIndex,
  onHoverIndex,
  onSeek,
  onSelectMoment,
}: {
  curve: InterestCurve;
  durationMs: number;
  hoverIndex: number | null;
  onHoverIndex: (index: number | null) => void;
  onSeek: (startMs: number) => void;
  onSelectMoment: (moment: InterestMoment) => void;
}) {
  const { points } = curve;
  const [infoOpen, setInfoOpen] = useState(false);
  const [signalsOpen, setSignalsOpen] = useState(false);
  const infoId = useId();

  const coords = useMemo<Array<[number, number]>>(
    () => points.map((point) => [xPct(point, durationMs), yPct(point.value)]),
    [points, durationMs],
  );
  const linePath = useMemo(() => smoothPath(coords), [coords]);
  const baselinePath = useMemo(
    () =>
      points.every((point) => typeof point.baseline === "number")
        ? smoothPath(
            points.map((point) => [
              xPct(point, durationMs),
              yPct(point.baseline ?? 0),
            ]),
          )
        : "",
    [points, durationMs],
  );
  const areaPath =
    coords.length > 0
      ? `${linePath} L${coords[coords.length - 1][0]},100 L${coords[0][0]},100 Z`
      : "";

  const hovered = hoverIndex === null ? undefined : points[hoverIndex];
  const moments = [...(curve.peaks ?? []), ...(curve.dips ?? [])];
  const hasSignals = SIGNAL_ROWS.some((row) =>
    points.some((point) => typeof point.signals?.[row.key] === "number"),
  );

  return (
    <div className="space-y-[6px]">
      <div className="flex items-center gap-1.5 sm:gap-2">
        <span
          className={cn(
            LABEL_COLUMN,
            "flex items-center gap-1 text-[11px] text-muted-foreground",
          )}
        >
          <span className="truncate">Audience interest</span>
          <button
            type="button"
            aria-expanded={infoOpen}
            aria-controls={infoId}
            aria-label="About audience interest"
            onClick={() => setInfoOpen((open) => !open)}
            className="rounded-full text-muted-foreground/80 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
          >
            <Icon icon={InformationCircleIcon} className="size-3.5" />
          </button>
        </span>

        <div className="relative h-14 flex-1 overflow-hidden rounded-[3px] bg-muted/60">
          <svg
            aria-hidden="true"
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            className="absolute inset-0 size-full"
          >
            <path d={areaPath} className="fill-time/20" />
            {baselinePath && (
              <path
                d={baselinePath}
                fill="none"
                strokeWidth={1}
                strokeDasharray="3 3"
                vectorEffect="non-scaling-stroke"
                className="stroke-muted-foreground/70"
              />
            )}
            <path
              d={linePath}
              fill="none"
              strokeWidth={1.5}
              vectorEffect="non-scaling-stroke"
              strokeLinejoin="round"
              className="stroke-time"
            />
          </svg>
          <ScrubLane
            points={points}
            durationMs={durationMs}
            hoverIndex={hoverIndex}
            onHoverIndex={onHoverIndex}
            onSeek={onSeek}
            label="Audience interest timeline"
            valueText={
              hovered
                ? `${formatDurationMs(hovered.startMs)}, ${interestLevel(hovered.value)}`
                : "Use arrow keys to inspect, Enter to jump"
            }
          >
            <CursorLine point={hovered} durationMs={durationMs} />
          </ScrubLane>
          {moments.map((moment, index) => {
            const isPeak = moment.kind === "peak";
            const findingCount = moment.findingIds?.length ?? 0;
            return (
              <button
                key={`${moment.kind}-${moment.startMs}-${index}`}
                type="button"
                aria-label={`${isPeak ? "Peak" : "Dip"} in interest at ${formatDurationMs(
                  moment.startMs,
                )}${
                  findingCount > 0
                    ? `, ${findingCount} finding${findingCount === 1 ? "" : "s"}`
                    : ""
                }`}
                title={[
                  `${isPeak ? "Beats" : "Falls short of"} the typical drop-off`,
                  formatDurationMs(moment.startMs),
                  ...(moment.drivers ?? []),
                ].join(" · ")}
                onClick={() => onSelectMoment(moment)}
                className={cn(
                  "absolute z-10 flex size-4 -translate-x-1/2 items-center justify-center text-[9px] leading-none text-foreground motion-safe:transition-transform hover:scale-125 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60",
                  isPeak ? "-translate-y-full" : "",
                )}
                style={{
                  left: `${xPct(moment, durationMs)}%`,
                  top: `${yPct(moment.value)}%`,
                }}
              >
                <Icon
                  icon={isPeak ? ArrowUp01Icon : ArrowDown01Icon}
                  className="size-3.5"
                  strokeWidth={2.5}
                />
              </button>
            );
          })}
        </div>

        <span className="w-10 shrink-0" aria-hidden="true" />
      </div>

      <div className="flex items-center gap-1.5 sm:gap-2">
        <span className={LABEL_COLUMN} aria-hidden="true" />
        <div className="flex flex-1 items-center justify-between gap-3 text-[10px] text-muted-foreground">
          <span className="inline-flex min-w-0 items-center gap-1.5 truncate">
            <span className="w-4 border-t border-dashed border-muted-foreground/70" />
            {curve.baselineSource?.source === "creator"
              ? `Channel curve · ${curve.baselineSource.channelName ?? "your audience"} · ${curve.baselineSource.videos} videos`
              : "Typical drop-off"}
          </span>
          {hasSignals ? (
            <button
              type="button"
              aria-expanded={signalsOpen}
              onClick={() => setSignalsOpen((open) => !open)}
              className="inline-flex shrink-0 items-center gap-1 rounded text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60"
            >
              <Icon
                icon={signalsOpen ? ArrowDown01Icon : ArrowRight01Icon}
                className="size-3"
              />
              Signals
            </button>
          ) : null}
        </div>
        <span className="w-10 shrink-0" aria-hidden="true" />
      </div>

      {infoOpen && (
        <div
          id={infoId}
          className="rounded-md border border-border/70 bg-muted/40 px-3 py-2 text-[11px] leading-relaxed text-muted-foreground"
        >
          <p>{infoText(curve)}</p>
          <InterestCalibrationPanel />
        </div>
      )}

      <SignalLanes
        points={points}
        durationMs={durationMs}
        open={signalsOpen}
        hoverIndex={hoverIndex}
        onHoverIndex={onHoverIndex}
        onSeek={onSeek}
      />
    </div>
  );
}

function infoText(curve: InterestCurve): string {
  const calibration = curve.calibration;
  const parts: string[] = [];
  const hasNumbers =
    calibration &&
    calibration.videos !== undefined &&
    calibration.heldOutSpearman !== undefined &&
    calibration.positionBaselineSpearman !== undefined;
  if (hasNumbers) {
    parts.push(
      `Predicted from the transcript by a model trained on ${calibration.videos} public YouTube videos' Most Replayed data. On held-out channels it ranks moments with ρ = ${calibration.heldOutSpearman?.toFixed(2)} (position-only baseline ${calibration.positionBaselineSpearman?.toFixed(2)}).`,
    );
  } else {
    parts.push(
      "Predicted from the transcript by a model trained on public YouTube videos' Most Replayed data.",
    );
  }
  const source = curve.baselineSource;
  if (source?.source === "creator") {
    const date = source.calibratedAt
      ? new Date(source.calibratedAt).toLocaleDateString()
      : "the last calibration";
    parts.push(
      `The dashed line uses ${source.channelName ?? "your channel"}'s viewing pattern, blended with the typical curve: ${source.videos} videos and ${source.views.toLocaleString()} views, calibrated ${date}. This adapts the drop-off shape to your audience; it does not measure how well the content model fits them. The public-data scores above do not evaluate channel calibration.`,
    );
  } else {
    parts.push(
      `The dashed line shows the typical curve. ${source?.reason === "Using the generic drop-off shape." ? "" : (source?.reason ?? "")}`.trim(),
    );
  }
  parts.push(
    "Peak and dip markers show where this video's content is predicted to beat or fall short of that baseline.",
  );
  if (
    source?.source !== "creator" &&
    typeof calibration?.liftSpearman === "number"
  ) {
    parts.push(
      `Beyond position alone, the model's deviations correlate with the real ones at ρ = ${calibration.liftSpearman.toFixed(2)} on public held-out videos.`,
    );
  }
  parts.push(
    "It ranks moments within this video; it is not a retention prediction or a quality score. Treat the markers as places to look, not verdicts.",
  );
  if (curve.featureSource === "transcript") {
    parts.push("This run used transcript timing and wording only.");
  }
  return parts.join(" ");
}

const SIGNAL_ROWS = [
  { key: "wpm", label: "Pace", unit: "words/min" },
  { key: "pauseMs", label: "Pauses", unit: "ms" },
] as const;

function SignalLanes({
  points,
  durationMs,
  open,
  hoverIndex,
  onHoverIndex,
  onSeek,
}: {
  points: InterestPoint[];
  durationMs: number;
  open: boolean;
  hoverIndex: number | null;
  onHoverIndex: (index: number | null) => void;
  onSeek: (startMs: number) => void;
}) {
  const rows = SIGNAL_ROWS.filter((row) =>
    points.some((point) => typeof point.signals?.[row.key] === "number"),
  );
  if (rows.length === 0 || !open) return null;
  const hovered = hoverIndex === null ? undefined : points[hoverIndex];

  return (
    <div className="space-y-[6px]">
      {rows.map((row) => {
        const defined = points.filter(
          (point) => typeof point.signals?.[row.key] === "number",
        );
        const max = Math.max(
          1,
          ...defined.map((p) => p.signals?.[row.key] ?? 0),
        );
        const coords = defined.map((point): [number, number] => [
          xPct(point, durationMs),
          95 - ((point.signals?.[row.key] ?? 0) / max) * 90,
        ]);
        const line = straightPath(coords);
        return (
          <div key={row.key} className="flex items-center gap-1.5 sm:gap-2">
            <span
              className={cn(
                LABEL_COLUMN,
                "truncate pl-[18px] text-[11px] text-muted-foreground",
              )}
            >
              {row.label}
            </span>
            <div className="relative h-7 flex-1 overflow-hidden rounded-[3px] bg-muted/60">
              <svg
                aria-hidden="true"
                viewBox="0 0 100 100"
                preserveAspectRatio="none"
                className="absolute inset-0 size-full"
              >
                <path
                  d={`${line} L${coords[coords.length - 1][0]},100 L${coords[0][0]},100 Z`}
                  className="fill-muted-foreground/15"
                />
                <path
                  d={line}
                  fill="none"
                  strokeWidth={1}
                  vectorEffect="non-scaling-stroke"
                  className="stroke-muted-foreground"
                />
              </svg>
              <ScrubLane
                points={points}
                durationMs={durationMs}
                hoverIndex={hoverIndex}
                onHoverIndex={onHoverIndex}
                onSeek={onSeek}
                label={`${row.label} timeline`}
                valueText={
                  hovered?.signals?.[row.key] !== undefined
                    ? `${formatDurationMs(hovered.startMs)}, ${Math.round(hovered.signals[row.key])} ${row.unit}`
                    : "Use arrow keys to inspect, Enter to jump"
                }
              >
                <CursorLine point={hovered} durationMs={durationMs} />
              </ScrubLane>
            </div>
            <span className="w-10 shrink-0" aria-hidden="true" />
          </div>
        );
      })}
    </div>
  );
}

/** Readout for the hovered point: time, qualitative level, drivers, pace, pause. */
export function InterestReadout({ point }: { point: InterestPoint }) {
  const level = interestLevel(point.value);
  // Against the typical drop-off when the curve carries it; else by the level alone.
  const gap =
    typeof point.baseline === "number" ? point.value - point.baseline : null;
  const above = gap !== null ? gap > 0.05 : point.value >= 0.6;
  const below = gap !== null ? gap < -0.05 : point.value < 0.4;
  const drivers = above
    ? { icon: ArrowUp01Icon, items: point.driversUp }
    : below
      ? { icon: ArrowDown01Icon, items: point.driversDown }
      : null;
  const relation =
    gap === null
      ? null
      : above
        ? "above typical here"
        : below
          ? "below typical here"
          : "about typical here";
  const wpm = point.signals?.wpm;
  const pause = point.signals?.pauseMs;
  return (
    <>
      <span className="text-time">
        {formatDurationMs(point.startMs)}–{formatDurationMs(point.endMs)}
      </span>
      <span className="text-foreground">
        Audience interest: {level}
        {relation && (
          <span className="text-muted-foreground"> ({relation})</span>
        )}
      </span>
      {drivers && drivers.items && drivers.items.length > 0 && (
        <span className="inline-flex min-w-0 items-center gap-1">
          <Icon icon={drivers.icon} className="size-3" />
          <span className="truncate">
            {drivers.items.slice(0, 3).join(", ")}
          </span>
        </span>
      )}
      {typeof wpm === "number" && <span>{Math.round(wpm)} words/min</span>}
      {typeof pause === "number" && (
        <span>longest pause {(pause / 1000).toFixed(1)}s</span>
      )}
      <span className="ml-auto hidden text-muted-foreground/70 sm:inline">
        Click to jump
      </span>
    </>
  );
}

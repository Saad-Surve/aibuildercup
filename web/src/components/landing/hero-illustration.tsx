const SEVERITY_COLOR: Record<string, string> = {
  good: "var(--sev-good)",
  low: "var(--sev-low)",
  medium: "var(--sev-medium)",
  high: "var(--sev-high)",
  critical: "var(--sev-critical)",
};

const TRACKS: string[][] = [
  [
    "good",
    "good",
    "low",
    "medium",
    "good",
    "good",
    "low",
    "good",
    "medium",
    "good",
    "good",
    "low",
  ],
  [
    "medium",
    "high",
    "critical",
    "high",
    "medium",
    "low",
    "good",
    "medium",
    "high",
    "critical",
    "medium",
    "low",
  ],
  [
    "good",
    "low",
    "good",
    "good",
    "low",
    "good",
    "good",
    "low",
    "good",
    "good",
    "low",
    "good",
  ],
];

const BIN_W = 30;
const BIN_GAP = 4;
const TRACK_H = 14;
const TRACK_GAP = 8;
const START_X = 24;
const START_Y = 196;

export function HeroIllustration({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 420 300"
      className={className}
      role="img"
    >
      <defs>
        <linearGradient id="frame" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="var(--signal)" stopOpacity="0.14" />
          <stop offset="100%" stopColor="var(--sev-low)" stopOpacity="0.12" />
        </linearGradient>
      </defs>

      {/* video frame */}
      <rect x="24" y="20" width="372" height="150" rx="16" fill="url(#frame)" />
      <rect
        x="24.5"
        y="20.5"
        width="371"
        height="149"
        rx="15.5"
        fill="none"
        stroke="var(--border)"
      />

      {/* play button */}
      <circle cx="210" cy="95" r="26" fill="var(--signal)" />
      <path d="M202 83 L226 95 L202 107 Z" fill="var(--signal-foreground)" />

      {/* heatmap tracks */}
      {TRACKS.map((track, row) =>
        track.map((severity, index) => (
          <rect
            key={`${row}-${index}`}
            x={START_X + index * (BIN_W + BIN_GAP)}
            y={START_Y + row * (TRACK_H + TRACK_GAP)}
            width={BIN_W}
            height={TRACK_H}
            rx={4}
            fill={SEVERITY_COLOR[severity]}
            opacity={0.85}
          />
        )),
      )}

      {/* transcript lines */}
      <rect
        x="24"
        y="272"
        width="150"
        height="6"
        rx="3"
        fill="var(--muted-foreground)"
        opacity="0.5"
      />
      <rect
        x="182"
        y="272"
        width="90"
        height="6"
        rx="3"
        fill="var(--muted-foreground)"
        opacity="0.35"
      />
      <rect
        x="280"
        y="272"
        width="116"
        height="6"
        rx="3"
        fill="var(--muted-foreground)"
        opacity="0.25"
      />
    </svg>
  );
}

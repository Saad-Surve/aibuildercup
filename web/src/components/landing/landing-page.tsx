"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import {
  ArrowDown01Icon,
  ArrowRight01Icon,
  ChartBarBigIcon,
  Rocket01Icon,
  Upload01Icon,
} from "@hugeicons/core-free-icons";

import { AuthLoadingScreen } from "@/components/auth/auth-loading-screen";
import { useAuth } from "@/components/auth/auth-provider";
import { GoogleSignInButton } from "@/components/auth/google-sign-in-button";
import { Icon } from "@/components/common/icon";
import { InlineArrow } from "@/components/common/inline-arrow";
import { Logo } from "@/components/common/logo";
import { LandingBackground } from "@/components/landing/landing-background";
import { Button } from "@/components/ui/button";

/*
 * Long-form marketing page. Hero keeps the centred serif composition on the
 * static peripheral backdrop; below it sit a capability strip, a platforms
 * flow section (derivatives -> studio -> brand destinations, original SVGs),
 * an asymmetric feature bento with hands-on mini demos, a dotted three-step
 * workflow, a gradient CTA panel, and a footer with a force-fit SVG wordmark.
 *
 * Nothing moves on its own except the orchestrated flow packets and typing
 * dots, both gated behind prefers-reduced-motion. Everything else is
 * scroll-driven or hover/drag/click interaction. The page owns its scroll
 * container (`no-scrollbar`) so no scrollbar chrome is shown.
 */

const CARD_SURFACE =
  "rounded-2xl border-transparent bg-card text-foreground shadow-[0_1px_2px_rgba(23,23,23,0.05),0_16px_40px_-24px_rgba(23,23,23,0.28)] ring-1 ring-foreground/10 transition-shadow duration-200 hover:shadow-[0_2px_4px_rgba(23,23,23,0.05),0_24px_56px_-24px_rgba(23,23,23,0.32)]";

const PLATFORMS = [
  {
    logo: "/youtube.svg",
    name: "YouTube",
    detail: "Videos, captions, thumbnails",
    brand: "#FF0000",
  },
  {
    logo: "/medium.svg",
    name: "Medium",
    detail: "Stories and essays",
    brand: "#242424",
  },
  {
    logo: "/substack.svg",
    name: "Substack",
    detail: "Newsletters and posts",
    brand: "#FF6719",
  },
  {
    logo: "/reddit.svg",
    name: "Reddit",
    detail: "Posts and discussions",
    brand: "#FF4500",
  },
];

const ALSO_ON = PLATFORMS.slice(1);

const DERIVS: { title: string; meta: ReactNode; color: string }[] = [
  { title: "Thumbnail", meta: "YouTube · 16:9", color: "#f43f5e" },
  {
    title: "Captions",
    meta: (
      <>
        EN <InlineArrow /> HI
      </>
    ),
    color: "#6366f1",
  },
  { title: "Blog draft", meta: "Ready to publish", color: "#f59e0b" },
];

/* ——— flow orchestration: one master rAF timeline ———
 *
 * A single loop drives the whole platforms stage: input packets arrive
 * Thumbnail -> Captions -> Blog draft, the centre pulses while processing,
 * then output packets distribute top to bottom, then a calm settle before
 * the loop restarts. Packets are HTML dots positioned each frame with
 * path.getPointAtLength(), so they follow the true elbow geometry around
 * corners. Base dotted trunks stay static; only the active packet glows.
 * The loop idles offscreen (IntersectionObserver) and never starts under
 * prefers-reduced-motion.
 */
const FLOW_LOOP = 6.5;
const FLOW_IN = [
  { at: 0, dur: 0.7 },
  { at: 0.7, dur: 0.7 },
  { at: 1.4, dur: 0.7 },
];
const FLOW_PROCESS = { at: 2.1, dur: 0.5 };
const FLOW_OUT = [2.6, 3.2, 3.8, 4.4].map((at) => ({ at, dur: 0.6 }));

function easeInOutCubic(p: number) {
  return p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2;
}

function useFlowStage() {
  // Callback ref: the stage mounts only after auth resolves (the loading
  // state short-circuits the render first), so a plain useRef + mount-run
  // effect would execute while the stage is absent and never re-run.
  const [stage, setStage] = useState<HTMLDivElement | null>(null);
  const stageRef = useCallback((node: HTMLDivElement | null) => {
    setStage(node);
  }, []);

  useEffect(() => {
    if (!stage) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const paths = Array.from(
      stage.querySelectorAll<SVGPathElement>("[data-flow-path]"),
    );
    const dots = Array.from(
      stage.querySelectorAll<HTMLSpanElement>("[data-flow-dot]"),
    );
    const dotEls = dots;
    const centerEl = stage.querySelector<HTMLDivElement>("[data-flow-center]");
    if (paths.length === 0 || dots.length === 0) return;
    const lens = paths.map((p) => p.getTotalLength());

    let raf = 0;
    let t = 0;
    let last = performance.now();

    // The overlay SVG fills the stage exactly (inset-0, none-scaled), so an
    // SVG point (x, y) in 0..100 space maps directly onto container pixels.
    // No screen matrices involved — immune to scroll, zoom, and hidden trees.
    const place = (
      boxW: number,
      boxH: number,
      i: number,
      at: number,
      dur: number,
    ) => {
      const dot = dots[i];
      const path = paths[i];
      if (!dot || !path || boxW === 0 || boxH === 0) return;
      const local = (t - at) / dur;
      if (local < 0 || local > 1) {
        dot.style.opacity = "0";
        return;
      }
      const pt = path.getPointAtLength(easeInOutCubic(local) * lens[i]);
      const x = (pt.x / 100) * boxW;
      const y = (pt.y / 100) * boxH;
      dot.style.opacity = String(
        Math.min(1, local / 0.12) * Math.min(1, (1 - local) / 0.15),
      );
      dot.style.transform = `translate3d(${x.toFixed(1)}px, ${y.toFixed(1)}px, 0) translate(-50%, -50%)`;
    };

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;
      t = (t + dt) % FLOW_LOOP;
      const box = stage.getBoundingClientRect();
      FLOW_IN.forEach((s, k) => place(box.width, box.height, k, s.at, s.dur));
      FLOW_OUT.forEach((s, j) =>
        place(box.width, box.height, 3 + j, s.at, s.dur),
      );
      if (centerEl) {
        const lp = (t - FLOW_PROCESS.at) / FLOW_PROCESS.dur;
        if (lp >= 0 && lp <= 1) {
          const k = Math.sin(Math.PI * lp);
          centerEl.style.transform = `scale(${(1 + 0.02 * k).toFixed(4)})`;
          centerEl.style.boxShadow = `0 16px 40px -16px rgba(23,23,23,0.45), 0 0 ${(26 * k).toFixed(1)}px ${(4 * k).toFixed(1)}px rgba(99,102,241,${(0.4 * k).toFixed(3)})`;
        } else {
          centerEl.style.transform = "";
          centerEl.style.boxShadow = "";
        }
      }
    };
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      dotEls.forEach((d) => {
        d.style.opacity = "";
        d.style.transform = "";
      });
      if (centerEl) {
        centerEl.style.transform = "";
        centerEl.style.boxShadow = "";
      }
    };
  }, [stage]);

  return { flowStageRef: stageRef };
}

function PillNav({ onSignIn }: { onSignIn: () => void }) {
  const sentinelRef = useRef<HTMLDivElement>(null);
  const [condensed, setCondensed] = useState(false);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => setCondensed(!entry.isIntersecting),
      { threshold: 0 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <>
      <div ref={sentinelRef} aria-hidden="true" className="h-px w-full" />
      <header className="fixed inset-x-0 top-0 z-20 flex justify-center px-4">
        <div
          className={`grid w-full grid-cols-[1fr_auto_1fr] items-center transition-all duration-300 motion-reduce:transition-none ${
            condensed
              ? "mt-3 h-[52px] max-w-2xl rounded-full border-transparent bg-background/85 px-3 shadow-[0_12px_40px_-16px_rgba(23,23,23,0.35)] ring-1 ring-foreground/10 backdrop-blur-md"
              : "h-16 max-w-6xl bg-transparent"
          }`}
        >
          <div className="flex justify-start">
            {condensed ? <Logo compact /> : <Logo />}
          </div>
          <nav className="hidden items-center gap-7 text-sm text-muted-foreground md:flex">
            <a
              href="#features"
              className="transition-colors hover:text-foreground"
            >
              Features
            </a>
            <a
              href="#workflow"
              className="transition-colors hover:text-foreground"
            >
              Workflow
            </a>
            <a
              href="#platforms"
              className="transition-colors hover:text-foreground"
            >
              Platforms
            </a>
          </nav>
          <div className="flex justify-end">
            <Button
              variant="outline"
              size="sm"
              onClick={onSignIn}
              className={condensed ? "rounded-full" : undefined}
            >
              Sign in
            </Button>
          </div>
        </div>
      </header>
    </>
  );
}

/* ——— demo 1: draggable review cursor with positional feedback ——— */

const HEAT_ROWS = [
  [0, 0, 1, 2, 0, 3, 1, 0],
  [0, 1, 0, 1, 2, 0, 0, 1],
];
const HEAT_TONES = ["#34d399", "#facc15", "#fb923c", "#f87171"];
const HEAT_FEEDBACK = [
  { until: 20, msg: "Intro can be punchier", text: "text-amber-700" },
  { until: 42, msg: "Strong hook — keep this", text: "text-emerald-700" },
  { until: 58, msg: "Factual error flagged here", text: "text-red-700" },
  { until: 80, msg: "Pacing dips — tighten it", text: "text-orange-700" },
  { until: 101, msg: "Outro lands well", text: "text-emerald-700" },
];
const HEAT_TOTAL_S = 8 * 60 + 40;

function useReducedMotion() {
  const [reduced] = useState(
    () =>
      typeof window !== "undefined" &&
      !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches,
  );
  return reduced;
}

function HeatDemo({ active }: { active: boolean }) {
  const [pos, setPos] = useState(52);
  const trackRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);
  const reduced = useReducedMotion();

  useEffect(() => {
    if (!active || reduced) return;
    const id = window.setInterval(() => {
      if (draggingRef.current) return;
      setPos((p) => (p >= 100 ? 0 : p + 1));
    }, 80);
    return () => window.clearInterval(id);
  }, [active, reduced]);

  const setFromClientX = (clientX: number) => {
    const el = trackRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    setPos(
      Math.min(100, Math.max(0, ((clientX - rect.left) / rect.width) * 100)),
    );
  };

  const feedback = HEAT_FEEDBACK.find((f) => pos < f.until) ?? HEAT_FEEDBACK[0];
  const t = Math.round((pos / 100) * HEAT_TOTAL_S);
  const stamp = `${String(Math.floor(t / 60)).padStart(2, "0")}:${String(
    t % 60,
  ).padStart(2, "0")}`;

  return (
    <div className="rounded-xl border border-black/[0.06] bg-white/85 p-3">
      <div
        ref={trackRef}
        role="slider"
        tabIndex={0}
        aria-label="Review timeline scrubber. Drag to inspect findings."
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pos)}
        aria-valuetext={`${stamp} — ${feedback.msg}`}
        className="relative cursor-ew-resize touch-pan-y rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50"
        onPointerDown={(e) => {
          draggingRef.current = true;
          e.currentTarget.setPointerCapture(e.pointerId);
          setFromClientX(e.clientX);
        }}
        onPointerMove={(e) => {
          if (draggingRef.current) setFromClientX(e.clientX);
        }}
        onPointerUp={() => {
          draggingRef.current = false;
        }}
        onPointerCancel={() => {
          draggingRef.current = false;
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft") setPos((p) => Math.max(0, p - 2));
          if (e.key === "ArrowRight") setPos((p) => Math.min(100, p + 2));
        }}
      >
        <svg viewBox="0 0 248 54" className="w-full">
          {HEAT_ROWS.map((row, r) => (
            <g key={r}>
              {row.map((tone, i) => (
                <rect
                  key={i}
                  x={i * 31}
                  y={r * 30}
                  width={25}
                  height={20}
                  rx={6}
                  fill={HEAT_TONES[tone]}
                  fillOpacity={0.85}
                />
              ))}
            </g>
          ))}
        </svg>
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
        >
          <div
            className="absolute top-[-4px] bottom-0 w-px bg-foreground/60"
            style={{ left: `${pos}%` }}
          >
            <span className="absolute -top-1 -left-[5px] size-[11px] rounded-full border-2 border-white bg-foreground shadow" />
          </div>
        </div>
      </div>
      <div className="mt-2 flex items-center gap-2 border-t border-black/[0.05] pt-2">
        <span className="tabular text-[0.68rem] font-semibold text-foreground/70">
          {stamp}
        </span>
        <span
          className={`rounded-full bg-foreground/[0.06] px-2.5 py-0.5 text-[0.7rem] font-medium ${feedback.text}`}
        >
          {feedback.msg}
        </span>
      </div>
    </div>
  );
}

/* ——— demo 2: realistic SRT transcript ——— */

const TRANSCRIPT_CUES = [
  {
    n: "1",
    time: "00:00:00,000 --> 00:00:03,500",
    text: "Welcome to today's podcast episode.",
  },
  {
    n: "2",
    time: "00:00:03,500 --> 00:00:07,200",
    text: "Today we break down the perfect hook.",
  },
];

function TranscriptDemo({ active }: { active: boolean }) {
  const [idx, setIdx] = useState(0);
  const reduced = useReducedMotion();

  useEffect(() => {
    if (!active || reduced) return;
    const id = window.setInterval(
      () => setIdx((i) => (i + 1) % TRANSCRIPT_CUES.length),
      1400,
    );
    return () => window.clearInterval(id);
  }, [active, reduced]);

  return (
    <div className="rounded-xl border border-black/[0.06] bg-white/85 p-3 font-mono text-[11px] leading-relaxed">
      {TRANSCRIPT_CUES.map((cue, i) => (
        <div
          key={cue.n}
          className={`-mx-1 rounded-md px-1 transition-colors duration-300 ${
            i > 0 ? "mt-2" : ""
          } ${active && idx === i ? "bg-amber-400/20" : ""}`}
        >
          <p className="font-semibold text-amber-600">{cue.n}</p>
          <p className="text-foreground/50">{cue.time}</p>
          <p className="text-foreground/85">{cue.text}</p>
        </div>
      ))}
    </div>
  );
}

/* ——— demo 3: preview an accepted removal ——— */

const CUT_BARS = [
  6, 10, 8, 14, 9, 12, 7, 11, 16, 22, 27, 20, 25, 29, 23, 18, 10, 8, 12, 7, 9,
  11, 8, 6,
];

function renderCutBars(bars: number[], tone: string) {
  return bars.map((h, i) => (
    <span
      key={i}
      style={{ height: `${h * 2}px` }}
      className={`w-full rounded-full ${tone}`}
    />
  ));
}

function EditRevisionDemo({ active }: { active: boolean }) {
  const [cut, setCut] = useState(false);
  const reduced = useReducedMotion();
  const before = CUT_BARS.slice(0, 8);
  const zone = CUT_BARS.slice(8, 16);
  const after = CUT_BARS.slice(16);

  useEffect(() => {
    if (!active || reduced) return;
    const id = window.setTimeout(() => setCut(true), 700);
    return () => window.clearTimeout(id);
  }, [active, reduced]);

  return (
    <div className="rounded-xl border border-black/[0.06] bg-white/85 p-3">
      <div className="flex h-[76px] items-end gap-1.5 overflow-hidden">
        <div
          className="flex h-full min-w-0 items-end gap-[3px] overflow-hidden transition-all duration-500"
          style={{ flex: "1 1 0%" }}
        >
          {renderCutBars(before, "bg-foreground/15")}
        </div>
        <div
          className="relative flex h-full min-w-0 items-end gap-[3px] transition-all duration-500"
          style={{ flex: cut ? "0 1 0%" : "1 1 0%", opacity: cut ? 0 : 1 }}
        >
          {!cut && (
            <>
              <span
                aria-hidden="true"
                className="absolute top-0 -bottom-1 left-[-3px] w-1 rounded-full bg-rose-500"
              />
              <span
                aria-hidden="true"
                className="absolute top-0 -bottom-1 right-[-3px] w-1 rounded-full bg-rose-500"
              />
            </>
          )}
          {renderCutBars(
            zone,
            cut
              ? "bg-rose-500"
              : "bg-rose-400/80 transition-colors group-hover:bg-rose-500",
          )}
        </div>
        <div
          className="flex h-full min-w-0 items-end gap-[3px] overflow-hidden transition-all duration-500"
          style={{ flex: "1 1 0%" }}
        >
          {renderCutBars(after, "bg-foreground/15")}
        </div>
      </div>
      <div className="mt-2.5 flex items-center justify-between border-t border-black/[0.05] pt-2.5">
        <button
          type="button"
          onClick={() => setCut((c) => !c)}
          className="cursor-pointer rounded-full bg-rose-600 px-3 py-1 text-[0.68rem] font-semibold text-white transition-colors hover:bg-rose-700"
        >
          {cut ? "Show original" : "Show edited revision"}
        </button>
        <span className="tabular text-[0.68rem] font-medium text-foreground/55">
          {cut ? "After · edited in your editor" : "Demo · accepted removal"}
        </span>
      </div>
    </div>
  );
}

/* ——— demo 4: two-step translation ——— */

function LocaleDemo({ active }: { active: boolean }) {
  const [step, setStep] = useState<1 | 2>(1);
  const reduced = useReducedMotion();

  useEffect(() => {
    if (!active || reduced) return;
    const id = window.setInterval(
      () => setStep((s) => (s === 1 ? 2 : 1)),
      1400,
    );
    return () => window.clearInterval(id);
  }, [active, reduced]);

  return (
    <div className="rounded-xl border border-black/[0.06] bg-white/85 p-3">
      <div className="flex items-center gap-2">
        {(
          [
            { n: 1, label: "Original" },
            { n: 2, label: "हिन्दी" },
          ] as const
        ).map((s, i) => (
          <div key={s.n} className="flex items-center gap-2">
            {i > 0 && <span className="h-px w-4 bg-foreground/15" />}
            <button
              type="button"
              onClick={() => setStep(s.n)}
              className={`flex cursor-pointer items-center gap-1.5 rounded-full px-2.5 py-1 text-[0.65rem] font-semibold transition-colors ${
                step === s.n
                  ? "bg-indigo-600 text-white"
                  : "bg-foreground/[0.06] text-foreground/55 hover:text-foreground"
              }`}
            >
              <span className="tabular">{s.n}</span> {s.label}
            </button>
          </div>
        ))}
      </div>
      <div className="mt-2.5 rounded-lg bg-foreground/[0.04] p-2.5">
        {step === 1 ? (
          <>
            <p className="text-[0.62rem] font-semibold tracking-wide text-foreground/45 uppercase">
              EN · Original
            </p>
            <p className="mt-1 text-[0.78rem] leading-snug text-foreground">
              The monsoon arrived early this year.
            </p>
          </>
        ) : (
          <>
            <p className="text-[0.62rem] font-semibold tracking-wide text-indigo-600/80 uppercase">
              HI · Translated
            </p>
            <p className="mt-1 text-[0.78rem] leading-snug text-foreground">
              मानसून इस साल जल्दी आ गया।
            </p>
            <p className="mt-1 text-[0.65rem] text-foreground/50">
              Glossary applied · Dub ready
            </p>
          </>
        )}
      </div>
    </div>
  );
}

/* ——— demo 5: a scheduled month ——— */

interface ScheduledPost {
  day: number;
  project: string;
  platform: string;
  time: string;
  color: string;
  logo: string;
}

const CAL_MONTH = "November 2026";
const CAL_DAYS = 30;
const CAL_START_OFFSET = 0; // Sunday-first; Nov 1 2026 lands on a Sunday
const CAL_WEEKDAYS = ["S", "M", "T", "W", "T", "F", "S"];

/*
 * Three posts spread across the month. Colours stay in the fuchsia/violet
 * family of the old chat demo, so the card keeps its identity while the days
 * read as distinct. Each event is a badge on the day's top-right; hovering,
 * focusing, or the auto-play loop morphs it into a rounded square carrying the
 * project, platform, and slot.
 */
const SCHEDULED_POSTS: ScheduledPost[] = [
  {
    day: 5,
    project: "Fireside Ep. 12",
    platform: "YouTube",
    time: "9:00 AM",
    color: "#d946ef", // fuchsia-500
    logo: "/youtube.svg",
  },
  {
    day: 13,
    project: "The hook, explained",
    platform: "YouTube",
    time: "6:30 PM",
    color: "#8b5cf6", // violet-500
    logo: "/youtube.svg",
  },
  {
    day: 21,
    project: "Behind the scenes",
    platform: "YouTube",
    time: "12:00 PM",
    color: "#f43f5e", // rose-500
    logo: "/youtube.svg",
  },
];

// Only the first scheduled day self-demos; the rest wait for a hover.
const CAL_AUTOPLAY_DAY = 5;

function CalendarDemo({ active }: { active: boolean }) {
  const reduced = useReducedMotion();
  const [hoverDay, setHoverDay] = useState<number | null>(null);
  const [demoDay, setDemoDay] = useState<number | null>(null);

  // Demo loop: while the card is hovered, one scheduled day pops open on a loop
  // so the card shows what a hover reveals — the same trigger as the other
  // demos. It stops and hides when the pointer leaves, and idles under reduced
  // motion.
  useEffect(() => {
    if (!active || reduced) return;
    let openTimer = 0;
    let gapTimer = 0;
    const cycle = () => {
      setDemoDay(CAL_AUTOPLAY_DAY);
      openTimer = window.setTimeout(() => {
        setDemoDay(null);
        gapTimer = window.setTimeout(cycle, 1600);
      }, 1500);
    };
    gapTimer = window.setTimeout(cycle, 1000);
    return () => {
      window.clearTimeout(openTimer);
      window.clearTimeout(gapTimer);
    };
  }, [active, reduced]);

  // Derived, not state: the demo day only counts while the card is hovered.
  const openDay = hoverDay ?? (active ? demoDay : null);

  // Leading blanks + the month's days, padded to whole weeks so the grid keeps
  // its shape and event days never shift between renders.
  const cells: (number | null)[] = [
    ...Array.from({ length: CAL_START_OFFSET }, () => null),
    ...Array.from({ length: CAL_DAYS }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  const clearHover = (day: number) =>
    setHoverDay((current) => (current === day ? null : current));

  return (
    <div className="rounded-xl border border-black/[0.06] bg-white/85 p-3">
      <div className="flex items-baseline justify-between px-0.5 pb-1.5">
        <span className="text-[0.72rem] font-semibold text-foreground/80">
          {CAL_MONTH}
        </span>
        <span className="text-[0.62rem] font-medium text-foreground/35">
          {SCHEDULED_POSTS.length} scheduled
        </span>
      </div>
      <div className="grid grid-cols-7 gap-x-1">
        {CAL_WEEKDAYS.map((weekday, i) => (
          <span
            key={i}
            className="pb-1 text-center text-[0.58rem] font-medium text-foreground/35"
          >
            {weekday}
          </span>
        ))}
        {cells.map((day, i) => {
          if (!day) {
            return <span key={i} className="h-6" />;
          }
          const post = SCHEDULED_POSTS.find((p) => p.day === day);
          const isOpen = openDay === day;
          return (
            <div
              key={i}
              className="relative flex h-6 items-center justify-center"
            >
              <span className="relative text-[0.58rem] tabular-nums text-foreground/55">
                {day}
                {post ? (
                  <button
                    type="button"
                    aria-label={`${post.project} — ${post.platform}, Nov ${day} at ${post.time}`}
                    onMouseEnter={() => setHoverDay(day)}
                    onMouseLeave={() => clearHover(day)}
                    onFocus={() => setHoverDay(day)}
                    onBlur={() => clearHover(day)}
                    style={{
                      backgroundColor: post.color,
                      boxShadow:
                        active && !isOpen
                          ? `0 0 0 3px ${post.color}33`
                          : undefined,
                    }}
                    className={`absolute -top-1 -right-2.5 flex cursor-pointer flex-col overflow-hidden text-left text-white transition-all duration-150 ease-out motion-reduce:transition-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 ${
                      isOpen
                        ? "z-30 size-24 justify-between rounded-2xl p-2 shadow-[0_18px_40px_-16px_rgba(23,23,23,0.5)]"
                        : "z-10 size-2 rounded-full"
                    }`}
                  >
                    <span
                      className={`flex flex-col transition-opacity duration-100 ${
                        isOpen ? "opacity-100 delay-75" : "opacity-0"
                      }`}
                    >
                      <span className="flex items-center gap-1 text-[0.5rem] font-semibold tracking-wide text-white/85 uppercase">
                        <Image
                          src={post.logo}
                          alt=""
                          width={10}
                          height={10}
                          className="size-2.5 object-contain brightness-0 invert"
                        />
                        {post.platform}
                      </span>
                      <span className="mt-0.5 line-clamp-2 text-[0.62rem] leading-tight font-medium">
                        {post.project}
                      </span>
                    </span>
                    <span
                      className={`flex items-center justify-center transition-opacity duration-100 ${
                        isOpen ? "opacity-100 delay-75" : "opacity-0"
                      }`}
                    >
                      <span className="flex size-5 items-center justify-center rounded-full bg-white p-0.5">
                        <Image
                          src={post.logo}
                          alt=""
                          width={16}
                          height={16}
                          className="size-full object-contain"
                        />
                      </span>
                    </span>
                    <span
                      className={`text-[0.54rem] font-medium text-white/85 transition-opacity duration-100 ${
                        isOpen ? "opacity-100 delay-75" : "opacity-0"
                      }`}
                    >
                      Nov {day} · {post.time}
                    </span>
                  </button>
                ) : null}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ——— demo 6: draft -> edit -> final ——— */

function PostsDemo({ active }: { active: boolean }) {
  const pages = [
    {
      label: "Draft",
      note: "+2 lines",
      noteClass: "text-emerald-600",
      bars: ["w-full", "w-11/12", "w-full", "w-4/5", "w-full"],
      extra: ["w-3/5", "w-2/3"],
    },
    {
      label: "Edit",
      note: "−2 lines",
      noteClass: "text-red-600",
      bars: ["w-full", "w-11/12", "w-full", "w-4/5", "w-full"],
      extra: [],
      removed: [1, 3],
    },
    {
      label: "Final",
      note: "Ready",
      noteClass: "text-emerald-600",
      bars: ["w-full", "w-11/12", "w-full", "w-4/5"],
      extra: [],
    },
  ];
  return (
    <div className="relative">
      <div className="grid grid-cols-3 gap-6">
        {pages.map((page, pi) => (
          <div
            key={page.label}
            style={{ transitionDelay: `${pi * 70}ms` }}
            className="rounded-xl border border-black/[0.06] bg-white/85 p-2.5 transition-transform duration-300 group-hover:-translate-y-1"
          >
            <p className="text-[0.62rem] font-semibold tracking-wide text-foreground/50 uppercase">
              {page.label}
            </p>
            <div className="mt-2 space-y-1.5">
              {page.bars.map((w, i) => {
                const removed = page.removed?.includes(i);
                return (
                  <div
                    key={i}
                    style={{ animationDelay: `${(pi * 7 + i) * 55}ms` }}
                    className={`h-1 rounded-full ${w} ${
                      removed
                        ? `bg-red-400/80 ${active ? "bar-blink" : ""}`
                        : `bg-foreground/12 ${active ? "bar-in" : ""}`
                    }`}
                  />
                );
              })}
              {page.extra.map((w, i) => (
                <div
                  key={`x-${i}`}
                  style={{
                    animationDelay: `${(pi * 7 + page.bars.length + i) * 55}ms`,
                  }}
                  className={`h-1 rounded-full ${w} bg-emerald-400/80 ${
                    active ? "bar-in" : ""
                  }`}
                />
              ))}
            </div>
            <p
              className={`mt-2 text-[0.62rem] font-semibold ${page.noteClass}`}
            >
              {page.note}
            </p>
          </div>
        ))}
      </div>
      {["page-arrow-1", "page-arrow-2"].map((id, i) => (
        <svg
          key={id}
          aria-hidden="true"
          viewBox="0 0 24 24"
          className="absolute top-1/2 z-10 h-5 w-5 -translate-y-1/2"
          style={{ left: `calc(${(i + 1) * 33.333}% - 10px)` }}
        >
          <defs>
            <marker
              id={id}
              markerWidth="7"
              markerHeight="7"
              refX="5"
              refY="3"
              orient="auto"
            >
              <path
                d="M0.5,0.5 L5.5,3 L0.5,5.5"
                fill="none"
                stroke="var(--foreground)"
                strokeOpacity={0.45}
                strokeWidth={1.2}
              />
            </marker>
          </defs>
          <path
            d="M3 12 H18"
            fill="none"
            stroke="var(--foreground)"
            strokeOpacity={0.35}
            strokeWidth={1.5}
            strokeLinecap="round"
            strokeDasharray="2.5 2.5"
            markerEnd={`url(#${id})`}
          />
        </svg>
      ))}
    </div>
  );
}

interface Feature {
  title: string;
  copy: string;
  render: (active: boolean) => ReactNode;
  hover: string;
  className?: string;
  horizontal?: boolean;
}

const FEATURES: Feature[] = [
  {
    title: "A review you can check",
    copy: "Nine reviewers flag moments with proposed edits. Fact checks are grounded with Google Search. Accept, revise, or dismiss each finding.",
    render: (active) => (
      <HeatDemo key={active ? "on" : "off"} active={active} />
    ),
    hover: "group-hover:text-emerald-600",
    className: "sm:col-span-2 lg:col-span-2",
  },
  {
    title: "Every word, pinned to the frame",
    copy: "A searchable transcript with word-level timestamps. Jump anywhere, quote with confidence.",
    render: (active) => (
      <TranscriptDemo key={active ? "on" : "off"} active={active} />
    ),
    hover: "group-hover:text-amber-600",
  },
  {
    title: "Export cuts → upload revision → see what changed",
    copy: "Download a cut list and edit plan from accepted findings. Edit in your own editor, upload the revision, and re-review to see what changed.",
    render: (active) => (
      <EditRevisionDemo key={active ? "on" : "off"} active={active} />
    ),
    hover: "group-hover:text-rose-600",
  },
  {
    title: "Fluent in your audience",
    copy: "Localized captions and dubbed audio, with a glossary that keeps names right.",
    render: (active) => (
      <LocaleDemo key={active ? "on" : "off"} active={active} />
    ),
    hover: "group-hover:text-indigo-600",
  },
  {
    title: "Your YouTube publishing calendar",
    copy: "Schedule YouTube uploads and plan your next posts in one calendar.",
    render: (active) => <CalendarDemo active={active} />,
    hover: "group-hover:text-fuchsia-600",
  },
  {
    title: "Keep writing in your voice",
    copy: "Draft posts for Medium, Substack, and Reddit with a writing partner that draws on your creator library.",
    render: (active) => (
      <PostsDemo key={active ? "on" : "off"} active={active} />
    ),
    hover: "group-hover:text-sky-600",
    className: "sm:col-span-2 lg:col-span-3",
    horizontal: true,
  },
];

const STEPS = [
  {
    icon: Upload01Icon,
    title: "Drop in one video",
    copy: "Start with a timestamped transcript you can search and edit.",
  },
  {
    icon: ChartBarBigIcon,
    title: "Review and decide",
    copy: "Check findings on the heatmap. Accept, revise, or dismiss the proposed edits.",
  },
  {
    icon: Rocket01Icon,
    title: "Publish and cross-post",
    copy: "Prepare captions, dubs, thumbnails, and a listing. Publish to YouTube or cross-post your writing.",
  },
];

export function LandingPage() {
  const {
    profile,
    status,
    error,
    signInWithGoogle,
    signInAsDemo,
    demoAvailable,
    signOut,
  } = useAuth();
  const router = useRouter();
  const [hoverCard, setHoverCard] = useState<string | null>(null);
  const { flowStageRef } = useFlowStage();

  useEffect(() => {
    if (status === "signed_in" && profile) {
      router.replace(
        profile.onboardingCompleted ? "/dashboard" : "/onboarding",
      );
    }
  }, [status, profile, router]);

  const redirecting =
    status === "loading" || (status === "signed_in" && Boolean(profile));

  if (redirecting) {
    return (
      <main className="flex min-h-[100dvh] flex-col items-center justify-center bg-background px-6 text-foreground">
        <AuthLoadingScreen label="Taking you to your studio…" />
      </main>
    );
  }

  return (
    <main
      id="top"
      className="no-scrollbar h-[100dvh] overflow-x-clip overflow-y-auto scroll-smooth bg-background text-foreground motion-reduce:scroll-auto"
    >
      <PillNav onSignIn={signInWithGoogle} />

      {/* ——— hero ——— */}
      <section className="relative overflow-hidden">
        <LandingBackground />
        <div className="relative mx-auto flex min-h-[100dvh] w-full max-w-2xl flex-col items-center justify-center px-6 pt-24 pb-16 text-center">
          <Image
            src="/logo.png"
            alt="Resonance"
            width={194}
            height={145}
            priority
            className="h-auto w-[170px] sm:w-[200px]"
          />

          <h1 className="mt-6 max-w-[16ch] font-serif text-5xl leading-[1.05] font-medium tracking-tight text-balance sm:text-6xl lg:text-7xl">
            Review before you publish
          </h1>

          <p className="mt-6 max-w-xl text-pretty text-base text-muted-foreground sm:text-lg">
            An editorial review for YouTube creators, with findings you can
            check. AI suggests. The creator decides.
          </p>

          <div className="mt-8 flex flex-col items-center gap-4">
            {status === "error" ? (
              <div className="flex flex-col items-center gap-3">
                <p role="alert" className="text-sm text-destructive">
                  {error ?? "We couldn't reach your studio. Please try again."}
                </p>
                <Button
                  variant="outline"
                  onClick={signOut}
                  className="rounded-full"
                >
                  Sign out and try again
                </Button>
              </div>
            ) : (
              <>
                <GoogleSignInButton onClick={signInWithGoogle} />
                {demoAvailable ? (
                  <button
                    type="button"
                    onClick={signInAsDemo}
                    className="cursor-pointer text-sm font-medium text-muted-foreground underline-offset-4 transition-colors hover:text-foreground hover:underline"
                  >
                    or explore the read-only demo
                  </button>
                ) : null}
                <a
                  href="#features"
                  className="inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                >
                  Explore features
                  <Icon icon={ArrowDown01Icon} className="size-3.5" />
                </a>
              </>
            )}
          </div>
        </div>
      </section>

      {/* ——— capability strip ——— */}
      <section className="border-y border-border/60 bg-muted/30">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-2 px-6 py-8">
          {[
            "Timestamped transcript",
            "Heatmap review",
            "Export cuts & compare revisions",
            "Captions & dubbing",
            "Thumbnails & listing",
          ].map((pill) => (
            <span
              key={pill}
              className="rounded-full border-transparent bg-card px-3.5 py-1.5 text-xs text-muted-foreground shadow-[0_1px_2px_rgba(23,23,23,0.06)] ring-1 ring-foreground/10"
            >
              {pill}
            </span>
          ))}
        </div>
      </section>

      {/* ——— platforms: derivatives -> studio -> destinations ——— */}
      <section id="platforms" className="scroll-mt-28">
        <div className="mx-auto max-w-6xl px-6 py-16 sm:py-20">
          <h2 className="max-w-xl font-heading text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            Publish to YouTube. Cross-post your writing.
          </h2>
          <p className="mt-3 max-w-xl text-pretty text-muted-foreground">
            Publish videos, captions, and thumbnails to YouTube. Cross-post
            drafts to Medium, Substack, and Reddit.
          </p>

          {/* mobile: stacked flow */}
          <div className="mt-10 md:hidden">
            <div className="flex flex-wrap justify-center gap-2">
              {DERIVS.map((d) => (
                <span
                  key={d.title}
                  className="rounded-full border-transparent bg-card px-3.5 py-1.5 text-xs text-muted-foreground shadow-[0_1px_2px_rgba(23,23,23,0.06)] ring-1 ring-foreground/10"
                >
                  {d.title} · {d.meta}
                </span>
              ))}
            </div>
            <div className="mx-auto mt-6 flex w-fit flex-col items-center gap-2 rounded-2xl border-transparent bg-card px-5 py-4 shadow-[0_12px_32px_-16px_rgba(23,23,23,0.4)] ring-1 ring-foreground/10">
              <Image
                src="/logo-mark.png"
                alt=""
                width={96}
                height={72}
                className="h-10 w-auto"
              />
              <span className="rounded-full bg-signal/10 px-2.5 py-0.5 text-[0.65rem] font-semibold text-signal">
                Connected
              </span>
            </div>
            <ul className="mt-6 divide-y divide-border/70 border-y border-border/70">
              {PLATFORMS.map((platform) => (
                <li
                  key={platform.name}
                  className="flex items-center gap-4 py-3"
                >
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-white shadow-sm ring-1 ring-foreground/10">
                    <Image
                      src={platform.logo}
                      alt=""
                      width={20}
                      height={20}
                      className="h-5 w-5 object-contain"
                    />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold">
                      {platform.name}
                    </span>
                    <span className="block truncate text-xs text-muted-foreground">
                      {platform.detail}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          </div>

          {/* desktop: flow stage — one orchestrated timeline */}
          <div
            ref={flowStageRef}
            data-flow-stage="true"
            aria-hidden="true"
            className="relative mt-10 hidden h-[420px] rounded-3xl bg-[radial-gradient(circle,rgba(0,0,0,0.07)_1px,transparent_1px)] bg-[size:18px_18px] select-none md:block"
          >
            <svg
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              className="absolute inset-0 h-full w-full"
            >
              {/* rectangular dotted trunks — static base layer */}
              {[18, 50, 82].map((y, k) => (
                <path
                  key={`in-${y}`}
                  data-flow-path={k}
                  d={y === 50 ? `M19 ${y} H42.5` : `M19 ${y} H30.5 V50 H42.5`}
                  fill="none"
                  stroke="var(--foreground)"
                  strokeOpacity={0.2}
                  strokeWidth={1.5}
                  strokeLinecap="round"
                  strokeDasharray="0.5 3.5"
                  vectorEffect="non-scaling-stroke"
                />
              ))}
              {[12, 37, 63, 88].map((y, j) => (
                <path
                  key={`out-${y}`}
                  data-flow-path={3 + j}
                  d={y === 50 ? `M57.5 50 H83` : `M57.5 50 H70.5 V${y} H83`}
                  fill="none"
                  stroke="var(--foreground)"
                  strokeOpacity={0.2}
                  strokeLinecap="round"
                  strokeWidth={1.5}
                  strokeDasharray="0.5 3.5"
                  vectorEffect="non-scaling-stroke"
                />
              ))}
            </svg>
            {/* travelling packets, positioned every frame by the timeline */}
            {Array.from({ length: 3 + PLATFORMS.length }).map((_, i) => {
              const color = i < 3 ? DERIVS[i].color : PLATFORMS[i - 3].brand;
              return (
                <span
                  key={i}
                  data-flow-dot={i}
                  className="absolute top-0 left-0 z-[5] size-2 rounded-full opacity-0 will-change-transform"
                  style={{
                    backgroundColor: color,
                    boxShadow: `0 0 10px 2px ${color}66`,
                  }}
                />
              );
            })}

            {DERIVS.map((d, i) => (
              <div
                key={d.title}
                className="absolute left-[2%] w-40 rounded-xl border-transparent bg-card px-3 py-2 shadow-[0_8px_24px_-12px_rgba(23,23,23,0.4)] ring-1 ring-foreground/10"
                style={{
                  top: `${[18, 50, 82][i]}%`,
                  transform: "translateY(-50%)",
                }}
              >
                <p className="text-xs font-semibold">{d.title}</p>
                <p className="tabular mt-0.5 text-[10px] text-muted-foreground">
                  {d.meta}
                </p>
              </div>
            ))}

            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2">
              <div
                data-flow-center="true"
                className="flex flex-col items-center gap-2 rounded-2xl border-transparent bg-card px-5 py-4 shadow-[0_16px_40px_-16px_rgba(23,23,23,0.45)] ring-1 ring-foreground/10 will-change-transform"
              >
                <Image
                  src="/logo-mark.png"
                  alt=""
                  width={96}
                  height={72}
                  className="h-12 w-auto"
                />
                <span className="rounded-full bg-signal/10 px-2.5 py-0.5 text-[0.65rem] font-semibold text-signal">
                  Connected
                </span>
              </div>
            </div>

            {PLATFORMS.map((platform, i) => (
              <div
                key={platform.name}
                className="absolute flex w-20 -translate-x-1/2 flex-col items-center gap-1.5"
                style={{
                  left: "86%",
                  top: `${[12, 37, 63, 88][i]}%`,
                  transform: "translate(-50%, -50%)",
                }}
              >
                <span className="flex size-14 items-center justify-center rounded-2xl border-transparent bg-white shadow-[0_12px_32px_-16px_rgba(23,23,23,0.45)] ring-1 ring-foreground/10">
                  <Image
                    src={platform.logo}
                    alt=""
                    width={28}
                    height={28}
                    className="h-7 w-7 object-contain"
                  />
                </span>
                <span className="text-[11px] font-medium text-foreground/70">
                  {platform.name}
                </span>
              </div>
            ))}
          </div>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-x-8 gap-y-3">
            <span className="text-xs font-medium text-muted-foreground">
              Cross-post drafts to
            </span>
            {ALSO_ON.map((item) => (
              <span
                key={item.name}
                className="inline-flex items-center gap-2 text-sm font-medium text-foreground/70 transition-colors hover:text-foreground"
              >
                <Image
                  src={item.logo}
                  alt=""
                  width={16}
                  height={16}
                  className="h-4 w-4 object-contain"
                />
                {item.name}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ——— features bento ——— */}
      <section
        id="features"
        className="scroll-mt-28 border-t border-border/60 bg-muted/40"
      >
        <div className="mx-auto max-w-6xl px-6 py-16 sm:py-20">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-signal">
            Features
          </p>
          <h2 className="mt-3 max-w-xl font-heading text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            From first review to ready to publish
          </h2>
          <p className="mt-3 max-w-xl text-pretty text-muted-foreground">
            Check the nine-reviewer heatmap alongside a relative
            audience-interest curve learned from YouTube Most Replayed data.
            These interactive examples show the workflow.
          </p>
          {/* oxlint-disable jsx-a11y/no-noninteractive-element-interactions -- card hover only previews each demo; every demo stays fully operable via keyboard and buttons. */}
          <div className="mt-8 grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((feature) => (
              <article
                key={feature.title}
                onMouseEnter={() => setHoverCard(feature.title)}
                onMouseLeave={() => setHoverCard(null)}
                className={`group flex flex-col p-5 ${CARD_SURFACE} ${
                  feature.horizontal
                    ? "sm:flex-row sm:items-center sm:gap-6"
                    : ""
                } ${feature.className ?? ""}`}
              >
                <div
                  className={
                    feature.horizontal ? "flex-1 sm:min-w-0" : undefined
                  }
                >
                  <h3
                    className={`font-heading text-xl font-semibold tracking-tight transition-colors duration-200 ${feature.hover}`}
                  >
                    {feature.title}
                  </h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                    {feature.copy}
                  </p>
                </div>
                <div
                  className={`mt-4 flex flex-1 flex-col justify-end ${
                    feature.horizontal
                      ? "sm:mt-0 sm:w-full sm:max-w-xs sm:shrink-0"
                      : ""
                  }`}
                >
                  {feature.render(hoverCard === feature.title)}
                </div>
              </article>
            ))}
          </div>
          {/* oxlint-enable jsx-a11y/no-noninteractive-element-interactions */}
        </div>
      </section>

      {/* ——— workflow ——— */}
      <section id="workflow" className="scroll-mt-28 border-t border-border/60">
        <div className="mx-auto max-w-6xl px-6 py-16 sm:py-20">
          <h2 className="mx-auto max-w-xl text-center font-heading text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            From raw footage to published in three steps
          </h2>
          <ol className="relative mt-14 grid gap-10 sm:grid-cols-3 sm:gap-6">
            <div
              aria-hidden="true"
              className="absolute top-[5px] right-[16%] left-[16%] hidden border-t-2 border-dotted border-foreground/20 sm:block"
            />
            {STEPS.map((step) => (
              <li key={step.title} className="relative text-center">
                <span className="relative z-10 mx-auto flex size-3 items-center justify-center">
                  <span className="size-2.5 rounded-full bg-signal ring-4 ring-signal/15" />
                </span>
                <span className="mx-auto mt-6 flex size-11 items-center justify-center rounded-2xl border-transparent bg-card shadow-[0_1px_2px_rgba(23,23,23,0.06),0_12px_32px_-20px_rgba(23,23,23,0.3)] ring-1 ring-foreground/10">
                  <Icon icon={step.icon} className="size-5" />
                </span>
                <h3 className="mt-4 font-heading text-lg font-semibold tracking-tight">
                  {step.title}
                </h3>
                <p className="mx-auto mt-1.5 max-w-[28ch] text-sm leading-relaxed text-muted-foreground">
                  {step.copy}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ——— CTA ——— */}
      <section className="border-t border-border/60">
        <div className="mx-auto max-w-6xl px-6 py-16 sm:py-20">
          <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-sky-700 via-violet-700 to-amber-600 px-6 py-16 text-center sm:px-12">
            <div
              aria-hidden="true"
              className="absolute -top-24 left-1/2 h-64 w-[36rem] -translate-x-1/2 rounded-full bg-white/15 blur-3xl"
            />
            <div className="relative mx-auto flex max-w-xl flex-col items-center">
              <h2 className="font-serif text-3xl leading-tight font-medium tracking-tight text-balance text-white sm:text-5xl">
                Your next video deserves a studio
              </h2>
              <p className="mt-4 max-w-md text-pretty text-sm text-white/80 sm:text-base">
                Bring your video to Resonance for a review you can check, edits
                you control, and a publishing workflow that follows through.
              </p>
              <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
                <button
                  type="button"
                  onClick={signInWithGoogle}
                  className="inline-flex h-12 cursor-pointer items-center justify-center gap-2 rounded-full bg-white px-7 text-sm font-semibold whitespace-nowrap text-zinc-900 shadow-[0_16px_40px_-16px_rgba(0,0,0,0.5)] transition-all duration-200 hover:-translate-y-px hover:shadow-[0_20px_48px_-16px_rgba(0,0,0,0.55)] active:translate-y-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-2 focus-visible:ring-offset-transparent"
                >
                  Sign in with Google
                  <Icon icon={ArrowRight01Icon} className="size-4" />
                </button>
                {demoAvailable ? (
                  <button
                    type="button"
                    onClick={signInAsDemo}
                    className="inline-flex h-12 cursor-pointer items-center justify-center gap-2 rounded-full border border-white/40 px-6 text-sm font-semibold text-white transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/70 focus-visible:ring-offset-2 focus-visible:ring-offset-transparent"
                  >
                    Try the read-only demo
                  </button>
                ) : null}
              </div>
              <p className="mt-5 text-xs text-white/70">
                AI suggests. The creator decides.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ——— footer ——— */}
      <footer className="border-t border-border/60">
        <div className="mx-auto max-w-6xl px-6 pt-12">
          <div className="flex flex-col gap-10 sm:flex-row sm:justify-between">
            <div className="max-w-xs">
              <Logo />
              <p className="mt-4 text-sm leading-relaxed text-muted-foreground">
                AI review studio for YouTube creators.
              </p>
            </div>
            <div className="flex gap-16">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Product
                </p>
                <ul className="mt-3 space-y-2.5 text-sm">
                  <li>
                    <a
                      href="#features"
                      className="transition-colors hover:text-foreground"
                    >
                      Features
                    </a>
                  </li>
                  <li>
                    <a
                      href="#workflow"
                      className="transition-colors hover:text-foreground"
                    >
                      Workflow
                    </a>
                  </li>
                  <li>
                    <a
                      href="#platforms"
                      className="transition-colors hover:text-foreground"
                    >
                      Platforms
                    </a>
                  </li>
                </ul>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Studio
                </p>
                <ul className="mt-3 space-y-2.5 text-sm">
                  <li>
                    <button
                      type="button"
                      onClick={signInWithGoogle}
                      className="cursor-pointer transition-colors hover:text-foreground"
                    >
                      Sign in
                    </button>
                  </li>
                  <li>
                    <a
                      href="/dashboard"
                      className="transition-colors hover:text-foreground"
                    >
                      Dashboard
                    </a>
                  </li>
                  <li>
                    <a
                      href="#top"
                      className="transition-colors hover:text-foreground"
                    >
                      Back to top
                    </a>
                  </li>
                </ul>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Legal
                </p>
                <ul className="mt-3 space-y-2.5 text-sm">
                  <li>
                    <a
                      href="/privacy"
                      className="transition-colors hover:text-foreground"
                    >
                      Privacy Policy
                    </a>
                  </li>
                  <li>
                    <a
                      href="/terms"
                      className="transition-colors hover:text-foreground"
                    >
                      Terms of Service
                    </a>
                  </li>
                  <li>
                    <a
                      href="/data-deletion"
                      className="transition-colors hover:text-foreground"
                    >
                      Data Deletion
                    </a>
                  </li>
                </ul>
              </div>
            </div>
          </div>
          <div className="mt-12 flex flex-col gap-2 border-t border-border/60 pt-6 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
            <p>Resonance · AI review studio for creators</p>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
              <a
                href="/privacy"
                className="transition-colors hover:text-foreground"
              >
                Privacy Policy
              </a>
              <p>
                © {new Date().getFullYear()} Resonance. Review, refine, publish.
              </p>
            </div>
          </div>
        </div>
        <div aria-hidden="true" className="overflow-hidden select-none">
          <div className="mx-auto max-w-6xl px-6">
            <svg
              viewBox="0 0 1200 210"
              className="block h-auto w-full"
              role="presentation"
            >
              <text
                x="600"
                y="172"
                textAnchor="middle"
                textLength="1130"
                lengthAdjust="spacing"
                fontSize="180"
                fontWeight={700}
                letterSpacing="8"
                fill="none"
                stroke="var(--foreground)"
                strokeOpacity={0.16}
                strokeWidth={1.5}
                style={{
                  fontFamily: "var(--font-schibsted)",
                  paintOrder: "stroke",
                  strokeLinejoin: "round",
                }}
              >
                Resonance
              </text>
            </svg>
          </div>
        </div>
      </footer>
    </main>
  );
}

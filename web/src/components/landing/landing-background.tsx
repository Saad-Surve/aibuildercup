import { InlineArrow } from "@/components/common/inline-arrow";

/*
 * Landing atmosphere: a clean light base with warm / cool haze at the edges,
 * plus a small, deliberately art-directed set of creator-motif vignettes kept
 * strictly at the periphery so the hero stays dominant:
 *
 *   left edge  — review-timeline card (the flagship heatmap critique),
 *   right edge — dubbed-video card (thumbnail + captions + locale),
 *   bottom     — a loose waveform sculpture (left) and an export chip (right).
 *
 * The two side cards mirror each other (equal size, opposing ±8° tilt, same
 * surface treatment) so the composition reads as balanced, not random. Detail
 * vignettes render only on lg+ screens; on smaller viewports only the haze,
 * grain, and the bottom waveform remain. Everything here is deliberately
 * static — no ambient loops — so the hero stays calm and dominant.
 */
export function LandingBackground() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 overflow-hidden"
    >
      {/* clean base with a soft top lift */}
      <div className="absolute inset-0 bg-background" />
      <div className="absolute left-1/2 top-[-20%] h-[40rem] w-[60rem] -translate-x-1/2 rounded-full bg-[radial-gradient(ellipse,rgba(255,255,255,0.9),transparent_70%)] blur-2xl" />

      {/* coloured haze at the edges */}
      <div className="absolute -left-48 -top-44 h-[48rem] w-[48rem] rounded-full bg-[radial-gradient(circle,rgba(217,119,6,0.12),transparent_66%)] blur-3xl" />
      <div className="absolute -right-56 -top-28 h-[52rem] w-[52rem] rounded-full bg-[radial-gradient(circle,rgba(124,58,237,0.11),transparent_66%)] blur-3xl" />
      <div className="absolute -bottom-60 left-1/2 h-[46rem] w-[66rem] -translate-x-1/2 rounded-full bg-[radial-gradient(ellipse,rgba(56,189,248,0.09),transparent_70%)] blur-3xl" />

      {/* ——— left vignette: review timeline ——— */}
      <div className="absolute -left-20 top-[20%] hidden w-72 lg:block">
        <div className="relative -rotate-[8deg]">
          {/* soft wash behind the card */}
          <div className="absolute -inset-6 rounded-[2rem] bg-[radial-gradient(circle,rgba(217,119,6,0.14),transparent_70%)] blur-2xl" />
          <div className="relative rounded-2xl border border-black/[0.06] bg-white/75 p-4 shadow-xl shadow-black/[0.06] backdrop-blur-xl">
            {/* header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="size-1.5 rounded-full bg-emerald-500" />
                <span className="text-[0.6rem] font-semibold uppercase tracking-[0.16em] text-foreground/60">
                  Review · Truth
                </span>
              </div>
              <span className="tabular rounded-full bg-foreground/[0.06] px-2 py-0.5 text-[0.65rem] font-semibold text-foreground/70">
                8.2
              </span>
            </div>
            {/* transcript lines */}
            <div className="mt-3 space-y-1.5">
              <div className="h-1.5 w-11/12 rounded-full bg-foreground/[0.09]" />
              <div className="h-1.5 w-3/4 rounded-full bg-foreground/[0.07]" />
              <div className="h-1.5 w-5/6 rounded-full bg-foreground/[0.08]" />
            </div>
            {/* heatmap track */}
            <div className="relative mt-3">
              <div className="flex gap-1">
                {[
                  "bg-emerald-400/70",
                  "bg-emerald-400/70",
                  "bg-yellow-400/80",
                  "bg-orange-400/80",
                  "bg-emerald-400/70",
                  "bg-red-400/70",
                  "bg-yellow-400/80",
                  "bg-emerald-400/70",
                ].map((tone, i) => (
                  <span
                    key={i}
                    className={`h-3.5 flex-1 rounded-[4px] ${tone}`}
                  />
                ))}
              </div>
              {/* playhead */}
              <div className="absolute -top-1 bottom-[-6px] left-[38%] w-px bg-foreground/50">
                <span className="absolute -left-[3px] -top-[3px] size-[7px] rounded-full border border-white bg-foreground/60" />
              </div>
            </div>
            {/* footer */}
            <div className="mt-3 flex items-center justify-between">
              <span className="tabular text-[0.65rem] text-foreground/45">
                02:14 / 08:40
              </span>
              <span className="text-[0.65rem] font-medium text-foreground/50">
                3 findings
              </span>
            </div>
          </div>
          {/* pinned cutter badge */}
          <div className="absolute -right-4 -top-4 flex size-9 items-center justify-center rounded-full border border-black/[0.06] bg-white shadow-md">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-foreground/55"
            >
              <circle cx="6" cy="6" r="2.5" />
              <circle cx="6" cy="18" r="2.5" />
              <path d="M8.5 8.5 20 19M8.5 15.5 20 5" />
            </svg>
          </div>
        </div>
      </div>

      {/* ——— right vignette: dubbed video ——— */}
      <div className="absolute -right-20 top-[16%] hidden w-72 lg:block">
        <div className="relative rotate-[8deg]">
          <div className="absolute -inset-6 rounded-[2rem] bg-[radial-gradient(circle,rgba(124,58,237,0.13),transparent_70%)] blur-2xl" />
          <div className="relative rounded-2xl border border-black/[0.06] bg-white/75 p-3.5 shadow-xl shadow-black/[0.06] backdrop-blur-xl">
            <div className="flex items-center justify-between px-0.5">
              <span className="text-[0.6rem] font-semibold uppercase tracking-[0.16em] text-foreground/60">
                Dubbed video · demo
              </span>
              <span className="tabular text-[0.65rem] text-foreground/45">
                08:40
              </span>
            </div>
            {/* thumbnail */}
            <div className="relative mt-2.5 aspect-video overflow-hidden rounded-xl bg-gradient-to-br from-sky-500 via-violet-500 to-amber-500">
              <div className="absolute inset-0 bg-gradient-to-t from-black/25 to-transparent" />
              {/* stylised waveform etched on the thumbnail */}
              <div className="absolute inset-x-6 bottom-2.5 flex items-end justify-center gap-[3px] opacity-80">
                {[5, 9, 6, 12, 8, 14, 7, 10, 5, 11, 6, 9, 5, 8].map((h, i) => (
                  <span
                    key={i}
                    style={{ height: `${h}px` }}
                    className="w-[3px] rounded-full bg-white/85"
                  />
                ))}
              </div>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="flex size-9 items-center justify-center rounded-full bg-white/95 shadow-md">
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                    className="ml-0.5 text-foreground/80"
                  >
                    <path d="M8 5.5v13l11-6.5z" />
                  </svg>
                </span>
              </div>
            </div>
            {/* captions + locale */}
            <div className="mt-3 space-y-1.5 px-0.5">
              <div className="h-1.5 w-10/12 rounded-full bg-foreground/[0.09]" />
              <div className="h-1.5 w-2/3 rounded-full bg-foreground/[0.07]" />
            </div>
            <div className="mt-2.5 flex items-center gap-1.5 px-0.5">
              <span className="flex items-center gap-1 rounded-full bg-foreground/[0.06] px-2 py-0.5 text-[0.62rem] font-semibold text-foreground/60">
                EN <InlineArrow /> HI
              </span>
              <span className="rounded-full bg-foreground/[0.06] px-2 py-0.5 text-[0.62rem] font-semibold text-foreground/60">
                CC
              </span>
            </div>
          </div>
          {/* pinned globe badge */}
          <div className="absolute -left-4 -top-4 flex size-9 items-center justify-center rounded-full border border-black/[0.06] bg-white shadow-md">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              className="text-foreground/55"
            >
              <circle cx="12" cy="12" r="8.5" />
              <path d="M3.5 12h17M12 3.5c2.5 2.4 3.8 5.3 3.8 8.5s-1.3 6.1-3.8 8.5c-2.5-2.4-3.8-5.3-3.8-8.5s1.3-6.1 3.8-8.5Z" />
            </svg>
          </div>
        </div>
      </div>

      {/* ——— bottom-left: loose waveform sculpture ——— */}
      <div className="absolute bottom-[11%] left-[5%] hidden items-end gap-1 sm:flex">
        {[10, 18, 8, 22, 14, 26, 12, 20, 9, 24, 13, 19, 8, 16, 11].map(
          (h, i) => (
            <span
              key={i}
              style={{ height: `${h}px` }}
              className="w-1.5 rounded-full bg-gradient-to-t from-sky-700 via-violet-700 to-amber-600"
            />
          ),
        )}
        <span className="tabular ml-2 self-center text-[0.62rem] font-semibold text-foreground/65">
          VO · −12dB
        </span>
      </div>

      {/* ——— bottom-right: export chip ——— */}
      <div className="absolute bottom-[9%] right-[4%] hidden lg:block">
        <div className="relative rotate-[5deg]">
          <div className="flex items-center gap-3 rounded-2xl border border-black/[0.06] bg-white/70 py-2.5 pl-3.5 pr-4 shadow-lg shadow-black/[0.05] backdrop-blur-xl">
            <span className="flex size-7 items-center justify-center rounded-full bg-foreground/[0.06]">
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="text-foreground/60"
              >
                <path d="M12 4v11m0 0 4-4m-4 4-4-4M4.5 19.5h15" />
              </svg>
            </span>
            <span>
              <span className="block text-[0.68rem] font-semibold text-foreground/70">
                Captions ready
              </span>
              <span className="mt-1 block h-1 w-28 overflow-hidden rounded-full bg-foreground/[0.08]">
                <span className="block h-full w-3/4 rounded-full bg-gradient-to-r from-sky-500/80 via-violet-500/80 to-amber-500/80" />
              </span>
            </span>
            <span className="tabular text-[0.62rem] text-foreground/45">
              MP4
            </span>
          </div>
        </div>
      </div>

      {/* faint film grain */}
      <div className="grain absolute inset-0 opacity-[0.02]" />
    </div>
  );
}

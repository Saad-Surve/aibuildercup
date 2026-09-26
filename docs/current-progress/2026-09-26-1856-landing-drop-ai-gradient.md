# 2026-09-26-1856 — landing page: kill the AI gradient

**What I did.** Removed the generic `sky → violet → amber` tri-color gradient from the public
landing page and replaced it with the product's own visual language: a review timeline. The
flag was a design-brief change request ("remove the awful AI gradient"), not a bug.

**Where the gradient was (all replaced).**

| File | Element | Was | Now |
|---|---|---|---|
| `landing-page.tsx` | CTA panel | `bg-gradient-to-br from-sky-700 via-violet-700 to-amber-600` + white blur glow | solid ink panel (`bg-foreground text-background`) with a severity heatmap ribbon across its base |
| `landing-background.tsx` | edge haze (3 blobs) | amber / violet / sky radial gradients | neutral `bg-foreground/[0.025–0.04]` blobs |
| `landing-background.tsx` | left review-card wash | amber radial | neutral `bg-foreground/[0.05]` |
| `landing-background.tsx` | right clip-card wash | violet radial | neutral `bg-foreground/[0.05]` |
| `landing-background.tsx` | clip thumbnail | `from-sky-500 via-violet-500 to-amber-500` | solid `bg-zinc-900` video frame |
| `landing-background.tsx` | waveform sculpture bars | sky/violet/amber vertical gradient | `bg-foreground/30` |
| `landing-background.tsx` | export progress bar | sky/violet/amber horizontal gradient | `bg-signal` (progress genuinely means the interactive accent) |

**The new CTA (the signature).** A solid ink slab — the app's review surface, not a colourful
marketing box. Its base carries a real `CTA_RIBBON` of `bg-heat-*` segments: green-dominant,
one `heat-red` critical notch, one `heat-orange`, and one honest **no-data gap** (`bg-transparent`).
A thin playhead (hairline + knob) sits at 61%. This is the flagship heatmap reduced to geometry,
and it makes the severity scale the only colour on the page — which is the product thesis
("colour is review meaning"). Green dominates so it reads as data, not a rainbow.

**Structural changes.** None. No contracts, schema, tokens, or endpoints touched. No new colours:
the ribbon uses the existing `--heat-*` tokens and the panel uses `foreground`/`background`, so
it is theme-correct (light: ink slab + paper pill; dark: paper slab + ink pill). `web/DESIGN.md`
§1 landing exception updated (it previously said "gradient CTA panel"). Component file header
comments in both files updated.

**Verified.** `bun run lint` clean; `bun run build` clean; both changed files are oxfmt-clean
(the 8 files `format:check` flags are pre-existing drift, left untouched). Confirmed Tailwind
emitted `.bg-heat-{green,yellow,orange,red}` and `.bg-signal` into the build CSS, and the ribbon
is present in the client chunks. Static export keeps `/` as before.

**Deliberately left alone.** The per-feature-card accent text colours (`emerald`/`amber`/`rose`/
`indigo`/`fuchsia`/`sky` hover + the amber cue number) are discrete, intentional per-card accents
— not the tri-color gradient. The dotted-grid radial and the thumbnail's black scrim are patterns,
not the AI gradient.

**Not done / next step.** No screenshot was taken (no browser tool in this environment) — worth a
human eyeball on `bun dev` at both widths and in light/dark. Landing dark mode is still broken
independently of this change: the vignette cards are hardcoded `bg-white/75` and
`border-black/[...]`, so the page only really works in light mode. That is a separate,
pre-existing issue and a good next task.

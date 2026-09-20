/*
 * Light, restrained atmosphere for the landing hero: a clean base, soft amber
 * and muted-violet haze at the edges, translucent glass panels with simple
 * rounded corners pushed to the periphery, a few minimal floating circles, and
 * a whisper of film grain. Decoration stays away from the centre so the hero
 * remains the focus. Motion is gated behind prefers-reduced-motion.
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

      {/* translucent glass panels, simple rounded corners, at the periphery */}
      <div className="absolute -left-24 top-[22%] h-64 w-72 rounded-[2rem] border border-black/[0.04] bg-white/40 backdrop-blur-2xl motion-safe:animate-[float_14s_ease-in-out_infinite]" />
      <div className="absolute -right-28 top-[16%] h-56 w-64 rounded-[1.75rem] border border-black/[0.04] bg-white/35 backdrop-blur-2xl motion-safe:animate-[drift_17s_ease-in-out_infinite]" />
      <div className="absolute -bottom-24 right-[6%] h-64 w-80 rounded-[2.25rem] border border-black/[0.03] bg-white/30 backdrop-blur-2xl motion-safe:animate-[float_18s_ease-in-out_infinite]" />

      {/* a few extremely minimal floating circles */}
      <div className="absolute left-[10%] top-[18%] size-2.5 rounded-full bg-foreground/10 motion-safe:animate-[float_12s_ease-in-out_infinite]" />
      <div className="absolute right-[12%] top-[40%] size-2 rounded-full bg-foreground/[0.08] motion-safe:animate-[drift_15s_ease-in-out_infinite]" />
      <div className="absolute bottom-[18%] left-[16%] size-3 rounded-full bg-foreground/[0.07] motion-safe:animate-[float_16s_ease-in-out_infinite]" />
      <div className="absolute bottom-[28%] right-[20%] size-2 rounded-full bg-foreground/[0.08] motion-safe:animate-[drift_13s_ease-in-out_infinite]" />

      {/* faint film grain */}
      <div className="grain absolute inset-0 opacity-[0.02]" />
    </div>
  );
}

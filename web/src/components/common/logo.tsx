import { cn } from "@/lib/utils";

/*
 * The mark is three stacked tracks — the timeline + heatmap language of the
 * product reduced to its simplest form. Monochrome on purpose: colour belongs
 * to review meaning, not to branding.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "flex size-8 shrink-0 items-center justify-center rounded-lg bg-foreground text-background",
        className,
      )}
    >
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        fill="currentColor"
        className="size-4"
      >
        <rect x="3" y="5" width="18" height="2.5" rx="1.25" />
        <rect x="3" y="10.75" width="11" height="2.5" rx="1.25" />
        <rect x="3" y="16.5" width="15" height="2.5" rx="1.25" />
      </svg>
    </span>
  );
}

export function Logo({
  className,
  compact = false,
}: {
  className?: string;
  compact?: boolean;
}) {
  return (
    <span className={cn("flex items-center gap-2.5", className)}>
      <LogoMark />
      {!compact ? (
        <span className="flex flex-col leading-none">
          <span className="font-heading text-sm font-semibold tracking-tight">
            Creator Helper Studio
          </span>
          <span className="mt-1 text-[0.65rem] font-medium uppercase tracking-[0.18em] text-muted-foreground">
            Habeas Codus
          </span>
        </span>
      ) : null}
    </span>
  );
}

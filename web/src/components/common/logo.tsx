import Image from "next/image";
import Link from "next/link";

import { cn } from "@/lib/utils";

/*
 * Brand mark cropped tight from the supplied transparent `logo.png`
 * (see `public/logo.png`), so it sits directly on any background with no
 * plate. The logo is never redrawn.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <Image
      src="/logo.png"
      alt=""
      aria-hidden="true"
      width={194}
      height={145}
      className={cn("h-8 w-auto shrink-0", className)}
    />
  );
}

export function Logo({
  className,
  compact = false,
  href,
}: {
  className?: string;
  compact?: boolean;
  href?: string;
}) {
  const content = (
    <span className={cn("flex items-center gap-2.5", className)}>
      <LogoMark />
      {!compact ? (
        <span className="flex flex-col leading-none">
          <span className="font-serif text-base font-semibold tracking-tight">
            Resonance
          </span>
          <span className="mt-1 text-[0.6rem] font-medium uppercase tracking-[0.18em] text-muted-foreground">
            Creator Helper Studio
          </span>
        </span>
      ) : null}
    </span>
  );

  if (!href) return content;

  return (
    <Link
      href={href}
      aria-label="Go to dashboard"
      className="inline-flex items-center rounded-lg transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
    >
      {content}
    </Link>
  );
}

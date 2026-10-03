"use client";

import type { ReactNode } from "react";

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

/**
 * Wraps a disabled control so its reason is still reachable.
 *
 * A disabled `<button>` does not receive pointer events (the base Button uses
 * `disabled:pointer-events-none`), so the tooltip cannot live on the button itself. The
 * tooltip trigger is a plain inline-flex span around it, which does receive hover and focus.
 * When `reason` is empty the child is rendered untouched, so this is a no-op outside
 * read-only mode and adds no wrapper for the common case.
 */
export function DisabledReason({
  reason,
  className,
  children,
}: {
  reason?: string | null;
  /** Extra classes for the wrapper, e.g. `w-full` when the child is full-width. */
  className?: string;
  children: ReactNode;
}) {
  if (!reason) return <>{children}</>;
  return (
    <Tooltip>
      <TooltipTrigger
        render={<span className={className ? `inline-flex ${className}` : "inline-flex"} />}
      >
        {children}
      </TooltipTrigger>
      <TooltipContent>{reason}</TooltipContent>
    </Tooltip>
  );
}

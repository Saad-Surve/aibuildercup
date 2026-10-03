"use client";

import { SquareLock02Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";

/**
 * Persistent reminder that the session is the read-only demo. Renders nothing for normal
 * accounts, so it costs the real experience a single boolean check.
 */
export function ReadOnlyBanner() {
  const readOnly = useReadOnly();
  if (!readOnly) return null;
  return (
    <div className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1 border-b border-transparent bg-signal/10 px-4 py-2 text-center text-xs text-muted-foreground shadow-[inset_0_-1px_0_0_var(--color-border)]">
      <Icon icon={SquareLock02Icon} className="size-3.5 text-signal" />
      <span>
        <span className="font-medium text-foreground">Read-only demo.</span>{" "}
        {READ_ONLY_REASON} Everything is browsable — nothing is saved.
      </span>
    </div>
  );
}

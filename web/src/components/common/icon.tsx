import { HugeiconsIcon, type IconSvgElement } from "@hugeicons/react";

import { cn } from "@/lib/utils";

/*
 * One icon family for the whole app: Hugeicons. This wrapper standardises the
 * size and stroke weight so icons stay visually consistent everywhere.
 */
export function Icon({
  icon,
  className,
  strokeWidth = 1.75,
}: {
  icon: IconSvgElement;
  className?: string;
  strokeWidth?: number;
}) {
  return (
    <HugeiconsIcon
      icon={icon}
      strokeWidth={strokeWidth}
      className={cn("size-4 shrink-0", className)}
    />
  );
}

import { Avatar as HumationAvatar } from "@humation/react";
import { humation1 } from "@humation/assets-humation-1";

import { cn } from "@/lib/utils";
import type { AvatarState } from "@/lib/types";

/*
 * The user's Humation avatar (deterministic SVG, rendered locally — no
 * network, no stored images). Replaces the Google profile photo everywhere.
 *
 * NOTE: this often renders inside a `Button`, whose styles force every
 * descendant `<svg>` without a `size-*` class to `size-4`. The Humation
 * `<svg>` carries no such class by default, which used to shrink it to 16px
 * inside the 32px header clip and leave a ring of empty space. The
 * `size-auto` class below only opts out of that selector (inline width/height
 * still win); the wrapper centers and clips the art.
 */
export function UserAvatar({
  state,
  size = 32,
  title,
  className,
}: {
  state: AvatarState;
  size?: number;
  title?: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-background leading-none",
        className,
      )}
      style={{ width: size, height: size }}
    >
      <HumationAvatar
        assets={humation1}
        seed={state.seed ?? undefined}
        selections={state.selections}
        colors={state.colors}
        background="transparent"
        size={size}
        title={title}
        className="size-auto block"
        style={{ width: size, height: size }}
      />
    </span>
  );
}

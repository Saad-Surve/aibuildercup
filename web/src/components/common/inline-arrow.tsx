import { ArrowRight01Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";

/*
 * A right arrow sized and optically aligned to sit inside a line of text
 * ("Settings" icon "Connections"). Using the icon family keeps the glyph identical
 * across platforms instead of relying on a Unicode arrow's font fallback.
 */
export function InlineArrow() {
  return (
    <Icon icon={ArrowRight01Icon} className="inline size-3 align-[-0.15em]" />
  );
}

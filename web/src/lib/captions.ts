import type { CaptionStyle } from "@/lib/types";

/** Mirrors the backend's `clean` preset so the dialog has a style before presets load. */
export const DEFAULT_CAPTION_STYLE: CaptionStyle = {
  preset: "clean",
  fontFamily: "Montserrat",
  fontSize: 54,
  bold: true,
  italic: false,
  uppercase: false,
  textColor: "#FFFFFF",
  outlineColor: "#000000",
  outlineWidth: 3,
  shadow: 2,
  background: "outline",
  backgroundColor: "#000000",
  backgroundOpacity: 60,
  position: "bottom",
  marginV: 72,
  maxCharsPerLine: 32,
  maxLines: 2,
  highlightEnabled: false,
  highlightColor: "#FFD400",
  speakerLabels: false,
};

export const CAPTION_FONT_OPTIONS = [
  { value: "Montserrat", label: "Montserrat" },
  { value: "Poppins", label: "Poppins" },
] as const;

export const CAPTION_POSITION_OPTIONS = [
  { value: "top", label: "Top" },
  { value: "middle", label: "Middle" },
  { value: "bottom", label: "Bottom" },
] as const;

export const CAPTION_BACKGROUND_OPTIONS = [
  { value: "outline", label: "Outline" },
  { value: "box", label: "Box" },
  { value: "none", label: "None" },
] as const;

const FONT_VARS: Record<string, string> = {
  Montserrat: "var(--font-montserrat)",
  Poppins: "var(--font-poppins)",
};

export function captionFontFamily(font: string): string {
  return `${FONT_VARS[font] ?? FONT_VARS.Montserrat}, system-ui, sans-serif`;
}

/** `#RRGGBB` + opacity (0-100) -> `rgba(...)` for the HTML preview. */
export function hexToRgba(hex: string, opacity: number): string {
  const value = hex.replace("#", "");
  const red = parseInt(value.slice(0, 2), 16);
  const green = parseInt(value.slice(2, 4), 16);
  const blue = parseInt(value.slice(4, 6), 16);
  return `rgba(${red}, ${green}, ${blue}, ${Math.max(0, Math.min(1, opacity / 100))})`;
}

/**
 * Inline styles approximating the burned caption for the HTML preview. The FFmpeg
 * render uses libass, so this is a close visual approximation, not a pixel match:
 * outline is faked with layered text-shadows and the box with a background.
 */
export function previewTextStyle(style: CaptionStyle): React.CSSProperties {
  const shadows: string[] = [];
  if (style.background === "outline" && style.outlineWidth > 0) {
    const w = style.outlineWidth;
    // Eight directions read as a rounded outline at caption scale.
    for (const [dx, dy] of [
      [-w, -w],
      [0, -w],
      [w, -w],
      [-w, 0],
      [w, 0],
      [-w, w],
      [0, w],
      [w, w],
    ]) {
      shadows.push(`${dx}px ${dy}px 0 ${style.outlineColor}`);
    }
  }
  if (style.shadow > 0) {
    shadows.push(
      `${style.shadow}px ${style.shadow}px ${style.shadow * 2}px rgba(0,0,0,0.65)`,
    );
  }
  return {
    fontFamily: captionFontFamily(style.fontFamily),
    fontWeight: style.bold ? 700 : 400,
    fontStyle: style.italic ? "italic" : "normal",
    textTransform: style.uppercase ? "uppercase" : "none",
    color: style.textColor,
    textShadow: shadows.length ? shadows.join(", ") : undefined,
    backgroundColor:
      style.background === "box"
        ? hexToRgba(style.backgroundColor, style.backgroundOpacity)
        : undefined,
    padding: style.background === "box" ? "0.15em 0.4em" : undefined,
    borderRadius: style.background === "box" ? "6px" : undefined,
    lineHeight: 1.25,
  };
}

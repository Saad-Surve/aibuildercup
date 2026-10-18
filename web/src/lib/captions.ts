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
  outlineWidth: 2,
  shadow: 2,
  background: "outline",
  backgroundColor: "#000000",
  backgroundOpacity: 60,
  position: "bottom",
  marginV: 92,
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

// Browser/system fallbacks for every non-Latin script in the dubbing catalog. The first face
// still controls Latin text; browsers select a later family only when that face lacks a glyph.
const CAPTION_SCRIPT_FALLBACKS = [
  '"Noto Sans CJK JP"',
  '"Noto Sans CJK KR"',
  '"Noto Sans CJK SC"',
  '"Noto Sans CJK TC"',
  '"Noto Sans CJK HK"',
  '"Noto Sans Devanagari"',
  '"Noto Sans Bengali"',
  '"Noto Sans Gurmukhi"',
  '"Noto Sans Gujarati"',
  '"Noto Sans Kannada"',
  '"Noto Sans Malayalam"',
  '"Noto Sans Tamil"',
  '"Noto Sans Telugu"',
  '"Noto Sans Thai"',
  '"Noto Sans Arabic"',
].join(", ");

export function captionFontFamily(font: string): string {
  return `${FONT_VARS[font] ?? FONT_VARS.Montserrat}, ${CAPTION_SCRIPT_FALLBACKS}, system-ui, sans-serif`;
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
 * the outline uses a real text stroke (layered text-shadows showed repeated
 * glyph copies at larger widths) and the box uses a background.
 */
export function previewTextStyle(style: CaptionStyle): React.CSSProperties {
  const outline = style.background === "outline" && style.outlineWidth > 0;
  return {
    fontFamily: captionFontFamily(style.fontFamily),
    fontWeight: style.bold ? 700 : 400,
    fontStyle: style.italic ? "italic" : "normal",
    textTransform: style.uppercase ? "uppercase" : "none",
    color: style.textColor,
    // `paint-order: stroke fill` draws the stroke behind the fill, so only the
    // outer half shows (libass outlines are also outside the glyph).
    WebkitTextStroke: outline
      ? `${style.outlineWidth * 2}px ${style.outlineColor}`
      : undefined,
    paintOrder: outline ? "stroke fill" : undefined,
    textShadow:
      style.shadow > 0
        ? `${style.shadow}px ${style.shadow}px ${style.shadow * 2}px rgba(0,0,0,0.65)`
        : undefined,
    backgroundColor:
      style.background === "box"
        ? hexToRgba(style.backgroundColor, style.backgroundOpacity)
        : undefined,
    padding: style.background === "box" ? "0.15em 0.4em" : undefined,
    borderRadius: style.background === "box" ? "6px" : undefined,
    lineHeight: 1.25,
  };
}

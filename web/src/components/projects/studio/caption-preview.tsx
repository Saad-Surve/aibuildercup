"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";

import { previewTextStyle } from "@/lib/captions";
import type { CaptionStyle } from "@/lib/types";

interface CaptionPreviewValue {
  /** The style currently being edited in the Burn Captions module, if open. */
  style: CaptionStyle | null;
  setStyle: (style: CaptionStyle) => void;
}

const CaptionPreviewContext = createContext<CaptionPreviewValue | null>(null);

/**
 * Lets the Burn Captions module drive a live caption overlay on the source
 * video without prop-drilling through the studio. When no provider is present
 * the overlay simply does not render.
 */
export function CaptionPreviewProvider({
  style,
  setStyle,
  children,
}: CaptionPreviewValue & { children: React.ReactNode }) {
  return (
    <CaptionPreviewContext.Provider value={{ style, setStyle }}>
      {children}
    </CaptionPreviewContext.Provider>
  );
}

export function useCaptionPreview(): CaptionPreviewValue | null {
  return useContext(CaptionPreviewContext);
}

/**
 * A faithful, non-interactive caption overlay. Sizes are authored against a
 * 1080-tall reference frame, so it scales itself by the real video height the
 * same way the backend does.
 */
export function CaptionOverlay({
  style,
  lines,
}: {
  style: CaptionStyle;
  lines: string[];
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(0.3);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      const height = entries[0]?.contentRect.height ?? 0;
      if (height > 0) setScale(height / 1080);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const textStyle = previewTextStyle(style);
  const fontSize = Math.max(6, Math.round(style.fontSize * scale));
  const margin = Math.round(style.marginV * scale);

  return (
    <div
      ref={containerRef}
      className="pointer-events-none absolute inset-x-0 top-0 bottom-9 z-10 flex flex-col items-center px-4"
      aria-hidden="true"
      style={{
        justifyContent:
          style.position === "top"
            ? "flex-start"
            : style.position === "middle"
              ? "center"
              : "flex-end",
        paddingTop: style.position === "top" ? margin : undefined,
        paddingBottom: style.position === "bottom" ? margin : undefined,
      }}
    >
      <div
        className="flex flex-col items-center gap-1 text-center"
        style={{ fontSize }}
      >
        {lines.map((line, lineIndex) => (
          <div key={`${line}-${lineIndex}`} style={textStyle}>
            {style.highlightEnabled
              ? renderKaraoke(line, lineIndex === 0, style)
              : line}
          </div>
        ))}
      </div>
    </div>
  );
}

/** First preview line mimics a half-sung karaoke cue. */
function renderKaraoke(line: string, active: boolean, style: CaptionStyle) {
  if (!active) return line;
  const words = line.split(" ");
  const sung = Math.ceil(words.length / 2);
  return words.map((word, index) => (
    <span
      key={`${word}-${index}`}
      style={{
        color: index < sung ? style.highlightColor : style.textColor,
      }}
    >
      {word}
      {index < words.length - 1 ? " " : ""}
    </span>
  ));
}

export const DEFAULT_CAPTION_LINES = [
  "This is how your captions",
  "will look on the video",
];

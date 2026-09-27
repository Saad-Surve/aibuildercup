import type { Transcript } from "@/lib/types";

/** Formats offered by the transcript card's Export menu. */
export type TranscriptExportFormat =
  | "srt"
  | "vtt"
  | "txt"
  | "md"
  | "csv"
  | "json";

export interface TranscriptExportFormatOption {
  value: TranscriptExportFormat;
  /** Menu label shown to the user. */
  label: string;
  /** File extension without the dot. */
  extension: string;
  /** MIME type used for the download blob. */
  mime: string;
}

export const TRANSCRIPT_EXPORT_FORMATS: TranscriptExportFormatOption[] = [
  {
    value: "srt",
    label: "SubRip (.srt)",
    extension: "srt",
    mime: "application/x-subrip",
  },
  { value: "vtt", label: "WebVTT (.vtt)", extension: "vtt", mime: "text/vtt" },
  {
    value: "txt",
    label: "Plain text (.txt)",
    extension: "txt",
    mime: "text/plain",
  },
  {
    value: "md",
    label: "Markdown (.md)",
    extension: "md",
    mime: "text/markdown",
  },
  { value: "csv", label: "CSV (.csv)", extension: "csv", mime: "text/csv" },
  {
    value: "json",
    label: "JSON (.json)",
    extension: "json",
    mime: "application/json",
  },
];

function pad(value: number, length = 2): string {
  return String(Math.floor(value)).padStart(length, "0");
}

/** `HH:MM:SS` (used by the text-ish exports). */
function formatClock(ms: number): string {
  const safe = Math.max(0, ms);
  const hours = Math.floor(safe / 3_600_000);
  const minutes = Math.floor((safe % 3_600_000) / 60_000);
  const seconds = Math.floor((safe % 60_000) / 1000);
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
}

/** `HH:MM:SS,mmm` (SRT) or `HH:MM:SS.mmm` (WebVTT). */
function formatTimecode(ms: number, separator: "," | "."): string {
  const safe = Math.max(0, ms);
  const millis = Math.floor(safe % 1000);
  return `${formatClock(safe)}${separator}${pad(millis, 3)}`;
}

function speakerLabel(speaker?: number | null): string {
  return speaker == null ? "" : `Speaker ${speaker}`;
}

function toSrt(transcript: Transcript): string {
  return transcript.segments
    .map((segment, index) => {
      const speaker = speakerLabel(segment.speaker);
      const text = speaker ? `${speaker}: ${segment.text}` : segment.text;
      const start = formatTimecode(segment.startMs, ",");
      const end = formatTimecode(segment.endMs, ",");
      return `${index + 1}\n${start} --> ${end}\n${text}`;
    })
    .join("\n\n");
}

function toVtt(transcript: Transcript): string {
  const cues = transcript.segments
    .map((segment) => {
      const speaker = speakerLabel(segment.speaker);
      const text = speaker ? `<v ${speaker}>${segment.text}` : segment.text;
      const start = formatTimecode(segment.startMs, ".");
      const end = formatTimecode(segment.endMs, ".");
      return `${start} --> ${end}\n${text}`;
    })
    .join("\n\n");
  return `WEBVTT\n\n${cues}\n`;
}

function toTxt(transcript: Transcript): string {
  return transcript.segments
    .map((segment) => {
      const speaker = speakerLabel(segment.speaker);
      const prefix = speaker ? `${speaker}: ` : "";
      return `[${formatClock(segment.startMs)}] ${prefix}${segment.text}`;
    })
    .join("\n");
}

function toMarkdown(transcript: Transcript): string {
  const duration = formatClock(transcript.durationMs);
  const lines = transcript.segments.map((segment) => {
    const speaker = speakerLabel(segment.speaker);
    const prefix = speaker ? `**${speaker}:** ` : "";
    return `**[${formatClock(segment.startMs)}]** ${prefix}${segment.text}`;
  });
  return [
    "# Transcript",
    "",
    `- Language: ${transcript.language}`,
    `- Duration: ${duration}`,
    `- Segments: ${transcript.segments.length}`,
    "",
    "---",
    "",
    ...lines,
    "",
  ].join("\n");
}

function csvCell(value: string | number | null | undefined): string {
  const text = value == null ? "" : String(value);
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function toCsv(transcript: Transcript): string {
  const header = [
    "index",
    "start",
    "end",
    "startMs",
    "endMs",
    "speaker",
    "text",
  ].join(",");
  const rows = transcript.segments.map((segment, index) =>
    [
      index + 1,
      formatTimecode(segment.startMs, "."),
      formatTimecode(segment.endMs, "."),
      segment.startMs,
      segment.endMs,
      segment.speaker ?? "",
      segment.text,
    ]
      .map(csvCell)
      .join(","),
  );
  return [header, ...rows].join("\n");
}

/** Serialize a transcript into the requested export format. */
export function serializeTranscript(
  transcript: Transcript,
  format: TranscriptExportFormat,
): string {
  switch (format) {
    case "srt":
      return toSrt(transcript);
    case "vtt":
      return toVtt(transcript);
    case "txt":
      return toTxt(transcript);
    case "md":
      return toMarkdown(transcript);
    case "csv":
      return toCsv(transcript);
    case "json":
      return JSON.stringify(transcript, null, 2);
  }
}

/** Build a filesystem-safe base name from a project name and transcript version. */
export function transcriptFileBase(
  projectName: string | undefined,
  version: number | null,
  projectId: string,
): string {
  const source =
    projectName && projectName.trim()
      ? projectName
      : `transcript-${projectId.slice(0, 8)}`;
  const slug =
    source
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 60) || "transcript";
  return version != null ? `${slug}-v${version}` : slug;
}

/**
 * Serialize the transcript and trigger a browser download. Client-only:
 * reaches for `document`/`URL`, so it must only be called from an event handler.
 */
export function downloadTranscript(
  transcript: Transcript,
  format: TranscriptExportFormat,
  baseName: string,
): void {
  const option = TRANSCRIPT_EXPORT_FORMATS.find(
    (item) => item.value === format,
  );
  if (!option) return;
  const blob = new Blob([serializeTranscript(transcript, format)], {
    type: `${option.mime};charset=utf-8`,
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${baseName}.${option.extension}`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

import type { Draft, DraftBlock } from "@/lib/types";

function slugify(value: string, fallback: string): string {
  const source = value.trim() || fallback;
  return (
    source
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 60) || fallback
  );
}

export function activeText(block: DraftBlock): string {
  return (
    block.versions.find(
      (version) => version.versionId === block.activeVersionId,
    )?.text ??
    block.versions[0]?.text ??
    ""
  );
}

function blockPrefix(block: DraftBlock): string {
  if (block.type === "heading") return "## ";
  if (block.type === "scene") return "> ";
  return "";
}

/** Active versions only, as clean Markdown. */
export function draftToMarkdown(draft: Draft): string {
  const lines: string[] = [];
  if (draft.title.trim()) lines.push(`# ${draft.title.trim()}`, "");
  for (const block of draft.blocks) {
    lines.push(`${blockPrefix(block)}${activeText(block)}`, "");
  }
  return lines.join("\n").trim() + "\n";
}

/** Active versions only, as plain text. */
export function draftToText(draft: Draft): string {
  const lines: string[] = [];
  if (draft.title.trim()) lines.push(draft.title.trim(), "");
  for (const block of draft.blocks) {
    lines.push(activeText(block), "");
  }
  return lines.join("\n").trim() + "\n";
}

/** Every version of every block, so nothing is lost when the draft leaves the app. */
export function draftToMarkdownWithVersions(draft: Draft): string {
  const lines: string[] = [];
  if (draft.title.trim()) lines.push(`# ${draft.title.trim()}`, "");
  for (const [index, block] of draft.blocks.entries()) {
    lines.push(`<!-- block ${index + 1} · ${block.type} -->`);
    for (const version of block.versions) {
      const marker =
        version.versionId === block.activeVersionId ? " (active)" : "";
      const label = version.label ? ` — ${version.label}` : "";
      lines.push(
        `- **v${block.versions.indexOf(version) + 1}**${label}${marker}`,
      );
      lines.push(`  ${version.text.replace(/\n/g, "\n  ")}`);
    }
    lines.push("");
  }
  return lines.join("\n").trim() + "\n";
}

export type DraftExportFormat = "markdown" | "text" | "versions";

export const DRAFT_EXPORT_FORMATS: {
  value: DraftExportFormat;
  label: string;
  extension: string;
}[] = [
  { value: "markdown", label: "Markdown (.md)", extension: "md" },
  { value: "text", label: "Plain text (.txt)", extension: "txt" },
  {
    value: "versions",
    label: "All versions (.md)",
    extension: "md",
  },
];

export function downloadDraft(
  draft: Draft,
  format: DraftExportFormat,
  fallbackName: string,
): void {
  const content =
    format === "markdown"
      ? draftToMarkdown(draft)
      : format === "text"
        ? draftToText(draft)
        : draftToMarkdownWithVersions(draft);
  const extension =
    DRAFT_EXPORT_FORMATS.find((item) => item.value === format)?.extension ??
    "md";
  const base = slugify(draft.title, fallbackName);
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${base}.${extension}`;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

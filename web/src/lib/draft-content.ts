/**
 * Draft content helpers — Obsidian-style.
 *
 * Each block stores **Markdown**. The editor shows the rendered preview and
 * swaps in the raw Markdown only for the block you are editing, exactly like
 * Obsidian's live preview.
 *
 * Inline alternatives use a small syntax:
 *
 *   {{option 1 | option 2 | option 3}}
 *
 * The first option is the active one; switching moves the chosen option to the
 * front. Word-, sentence-, and paragraph-level versions all use the same shape.
 */

const VARIANT = /\{\{([^{}]*)\}\}/g;

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function variantOptions(inner: string): string[] {
  return inner
    .split("|")
    .map((part) => part.trim())
    .filter(Boolean);
}

/** Inline Markdown (bold, italic, code, inline variants) to HTML. */
function inline(markdown: string): string {
  let html = escapeHtml(markdown);
  html = html.replace(VARIANT, (_match, inner: string) => {
    const options = variantOptions(inner);
    if (options.length === 0) return "";
    const encoded = JSON.stringify(options).replace(/"/g, "&quot;");
    return `<span class="draft-variant" data-variant="${encoded}" data-active="0">${escapeHtml(
      options[0],
    )}</span>`;
  });
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/(^|[^*])\*([^*\n]+?)\*/g, "$1<em>$2</em>");
  html = html.replace(/`([^`]+?)`/g, "<code>$1</code>");
  return html;
}

/** Render a block's Markdown to safe HTML. */
export function markdownToHtml(markdown: string): string {
  if (!markdown) return "";
  const lines = markdown.replace(/\r\n/g, "\n").split("\n");
  const out: string[] = [];
  let listOpen = false;
  let paragraph: string[] = [];
  const flushParagraph = () => {
    if (paragraph.length) {
      out.push(`<p>${paragraph.join("<br>")}</p>`);
      paragraph = [];
    }
  };
  const closeList = () => {
    if (listOpen) {
      out.push("</ul>");
      listOpen = false;
    }
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      flushParagraph();
      closeList();
      const level = Math.min(6, heading[1].length);
      out.push(`<h${level}>${inline(heading[2])}</h${level}>`);
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      flushParagraph();
      if (!listOpen) {
        out.push("<ul>");
        listOpen = true;
      }
      out.push(`<li>${inline(line.replace(/^\s*[-*]\s+/, ""))}</li>`);
      continue;
    }
    const quote = line.match(/^>\s?(.*)$/);
    if (quote) {
      flushParagraph();
      closeList();
      out.push(`<blockquote>${inline(quote[1])}</blockquote>`);
      continue;
    }
    if (line.trim() === "") {
      flushParagraph();
      closeList();
      continue;
    }
    paragraph.push(inline(line));
  }
  flushParagraph();
  closeList();
  return out.join("");
}

/** Resolve inline variants to their active option, keeping Markdown intact. */
export function resolveVariants(markdown: string): string {
  return markdown.replace(
    VARIANT,
    (_match, inner: string) => variantOptions(inner)[0] ?? "",
  );
}

/** The plain text a block shows in summaries/exports (active option only). */
export function markdownToPlain(markdown: string): string {
  if (!markdown) return "";
  return markdown
    .replace(VARIANT, (_match, inner: string) => variantOptions(inner)[0] ?? "")
    .replace(/[#>*`]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export interface VariantData {
  options: string[];
  active: number;
}

export function parseVariant(span: Element): VariantData | null {
  const raw = span.getAttribute("data-variant");
  if (!raw) return null;
  try {
    const options = JSON.parse(raw) as unknown;
    if (!Array.isArray(options) || options.length === 0) return null;
    return { options: options.map((item) => String(item)), active: 0 };
  } catch {
    return null;
  }
}

/** Move the chosen option to the front so the Markdown encodes the active one. */
export function reorderVariant(
  markdown: string,
  options: string[],
  chosenIndex: number,
): string {
  if (options.length === 0) return markdown;
  const chosen =
    options[Math.max(0, Math.min(options.length - 1, chosenIndex))];
  const reordered = [chosen, ...options.filter((option) => option !== chosen)];
  const syntax = `{{${reordered.join(" | ")}}}`;
  let match: RegExpExecArray | null;
  const pattern = new RegExp(VARIANT.source, "g");
  while ((match = pattern.exec(markdown))) {
    const found = variantOptions(match[1]);
    if (
      found.length === options.length &&
      found.every((option) => options.includes(option))
    ) {
      return (
        markdown.slice(0, match.index) +
        syntax +
        markdown.slice(match.index + match[0].length)
      );
    }
  }
  return markdown;
}

/** Build the inline variant syntax from a selection plus suggestions. */
export function variantSyntax(options: string[]): string {
  return `{{${options.join(" | ")}}}`;
}

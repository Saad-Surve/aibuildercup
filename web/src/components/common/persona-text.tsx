import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/*
 * The persona is stored as Markdown. It is shown as readable formatted text —
 * never as an editable Markdown source; to change it the user edits the
 * onboarding answers and regenerates.
 *
 * This is a deliberately small renderer for the subset the persona generator
 * (and the model that writes it) actually emits: `#`-`######` headings, ordered
 * and unordered lists (including loose lists with blank lines between items,
 * and nested items), horizontal rules, and inline bold / italic / code / links.
 * Unknown syntax falls through as plain text rather than being swallowed. It is
 * not a full CommonMark implementation.
 */

type ListItem = { text: string; depth: number; marker?: number };
type Block =
  | { type: "heading"; level: 1 | 2 | 3; text: string }
  | { type: "list"; ordered: boolean; items: ListItem[] }
  | { type: "paragraph"; text: string }
  | { type: "rule" };

const HEADING = /^(#{1,6})\s+(.*)$/;
const RULE = /^-{3,}$|^\*{3,}$|^_{3,}$/;
// A whole line that is only bold text (with an optional trailing colon) is how
// models usually write a section header; treat it as one instead of a paragraph.
const BOLD_ONLY = /^\*\*([^*]+?)\*\*:?\s*$/;
const ORDERED = /^(\s*)(\d+)[.)]\s+(.*)$/;
const UNORDERED = /^(\s*)[*+-]\s+(.*)$/;
const LINK = /^\[([^\]]+)\]\(([^)]+)\)$/;
const INLINE =
  /(\[[^\]]+\]\([^)]+\)|(?<!\w)\*\*[^*]+\*\*(?!\w)|(?<!\w)__[^_]+__(?!\w)|`[^`]+`|(?<!\w)\*[^*]+\*(?!\w)|(?<!\w)_[^_]+_(?!\w))/g;

/** Only http(s) and mailto links are rendered; anything else stays plain text. */
function safeHref(url: string): string | null {
  const trimmed = url.trim();
  if (/^(https?:\/\/|mailto:)/i.test(trimmed)) return trimmed;
  if (trimmed.startsWith("/") || trimmed.startsWith("#")) return trimmed;
  return null;
}

function renderInline(text: string): ReactNode[] {
  return text.split(INLINE).map((part, index) => {
    if (!part) return null;

    const link = LINK.exec(part);
    if (link) {
      const href = safeHref(link[2]!);
      if (href) {
        return (
          <a
            key={index}
            href={href}
            target="_blank"
            rel="noreferrer"
            className="text-signal underline-offset-2 hover:underline"
          >
            {link[1]}
          </a>
        );
      }
      return <span key={index}>{part}</span>;
    }

    if (
      (part.startsWith("**") && part.endsWith("**")) ||
      (part.startsWith("__") && part.endsWith("__"))
    ) {
      return (
        <strong key={index} className="font-semibold text-foreground">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code
          key={index}
          className="rounded bg-muted px-1 py-0.5 text-[0.85em]"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    if (
      (part.startsWith("*") && part.endsWith("*")) ||
      (part.startsWith("_") && part.endsWith("_"))
    ) {
      return <em key={index}>{part.slice(1, -1)}</em>;
    }
    return <span key={index}>{part}</span>;
  });
}

function indentDepth(indent: string): number {
  return Math.floor(indent.replace(/\t/g, "  ").length / 2);
}

function parsePersona(content: string): Block[] {
  const blocks: Block[] = [];
  let list: { ordered: boolean; items: ListItem[] } | null = null;

  const flush = () => {
    if (list && list.items.length) blocks.push({ type: "list", ...list });
    list = null;
  };

  for (const raw of content.split("\n")) {
    const line = raw.trim();
    // Blank lines only separate blocks; they do not close a list, so a loose
    // list (blank line between items) stays one list instead of becoming one
    // list per item with the numbering restarting at 1 every time.
    if (!line) continue;

    const heading = HEADING.exec(line);
    if (heading) {
      flush();
      blocks.push({
        type: "heading",
        level: Math.min(3, heading[1]!.length) as 1 | 2 | 3,
        text: heading[2]!,
      });
      continue;
    }

    if (RULE.test(line)) {
      flush();
      blocks.push({ type: "rule" });
      continue;
    }

    const bold = BOLD_ONLY.exec(line);
    if (bold) {
      flush();
      blocks.push({ type: "heading", level: 2, text: bold[1]! });
      continue;
    }

    const ordered = ORDERED.exec(raw);
    if (ordered) {
      if (list && !list.ordered) flush();
      (list ??= { ordered: true, items: [] }).items.push({
        text: ordered[3]!,
        depth: indentDepth(ordered[1]!),
        marker: Number(ordered[2]),
      });
      continue;
    }

    const unordered = UNORDERED.exec(raw);
    if (unordered) {
      if (list && list.ordered) flush();
      (list ??= { ordered: false, items: [] }).items.push({
        text: unordered[2]!,
        depth: indentDepth(unordered[1]!),
      });
      continue;
    }

    flush();
    blocks.push({ type: "paragraph", text: line });
  }

  flush();
  return blocks;
}

export function PersonaText({ content }: { content: string }) {
  const blocks = parsePersona(content);

  return (
    <div className="space-y-4 text-sm">
      {blocks.map((block, index) => {
        if (block.type === "rule") {
          return (
            <hr key={index} className="border-border" aria-hidden="true" />
          );
        }

        if (block.type === "heading") {
          if (block.level === 1) {
            return (
              <h2
                key={index}
                className="font-heading text-lg font-semibold tracking-tight"
              >
                {renderInline(block.text)}
              </h2>
            );
          }
          if (block.level === 2) {
            return (
              <h3
                key={index}
                className="font-heading text-sm font-semibold tracking-tight"
              >
                {renderInline(block.text)}
              </h3>
            );
          }
          return (
            <h4
              key={index}
              className="font-heading text-xs font-semibold tracking-tight text-muted-foreground"
            >
              {renderInline(block.text)}
            </h4>
          );
        }

        if (block.type === "list") {
          return (
            <ul key={index} className="space-y-1.5">
              {block.items.map((item, itemIndex) => (
                <li
                  key={itemIndex}
                  className={cn("flex gap-2.5", item.depth > 0 && "pl-5")}
                >
                  <span
                    className={
                      block.ordered
                        ? "tabular shrink-0 text-muted-foreground/70"
                        : "mt-2 size-1 shrink-0 rounded-full bg-muted-foreground/60"
                    }
                  >
                    {block.ordered
                      ? `${item.marker ?? itemIndex + 1}.`
                      : ""}
                  </span>
                  <span className="text-muted-foreground">
                    {renderInline(item.text)}
                  </span>
                </li>
              ))}
            </ul>
          );
        }

        return (
          <p key={index} className="text-muted-foreground">
            {renderInline(block.text)}
          </p>
        );
      })}
    </div>
  );
}

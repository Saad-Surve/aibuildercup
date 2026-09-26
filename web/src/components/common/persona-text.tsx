import type { ReactNode } from "react";

/*
 * The persona is stored as Markdown. It is shown as readable formatted text —
 * never as an editable Markdown source; to change it the user edits the
 * onboarding answers and regenerates.
 *
 * This is a deliberately small renderer for the subset the persona generator
 * actually emits: `#`/`##`/`###` headings, ordered and unordered lists (with
 * bold `**term:**` labels), and inline bold / italic / code. Unknown syntax
 * falls through as plain text rather than being swallowed.
 */

type Block =
  | { type: "heading"; level: 1 | 2 | 3; text: string }
  | { type: "list"; ordered: boolean; items: string[] }
  | { type: "paragraph"; text: string };

const HEADING = /^(#{1,3})\s+(.*)$/;
const UNORDERED = /^\s*[*+-]\s+(.*)$/;
const ORDERED = /^\s*\d+[.)]\s+(.*)$/;
const INLINE = /(\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_|`[^`]+`)/g;

function renderInline(text: string): ReactNode[] {
  return text.split(INLINE).map((part, index) => {
    if (!part) return null;
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

function parsePersona(content: string): Block[] {
  const blocks: Block[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;

  const flush = () => {
    if (list && list.items.length) blocks.push({ type: "list", ...list });
    list = null;
  };

  for (const raw of content.split("\n")) {
    const line = raw.trim();
    if (!line) {
      flush();
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) {
      flush();
      blocks.push({
        type: "heading",
        level: heading[1]!.length as 1 | 2 | 3,
        text: heading[2]!,
      });
      continue;
    }

    const ordered = ORDERED.exec(raw);
    if (ordered) {
      if (list && !list.ordered) flush();
      (list ??= { ordered: true, items: [] }).items.push(ordered[1]!);
      continue;
    }

    const unordered = UNORDERED.exec(raw);
    if (unordered) {
      if (list && list.ordered) flush();
      (list ??= { ordered: false, items: [] }).items.push(unordered[1]!);
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
                <li key={itemIndex} className="flex gap-2.5">
                  <span
                    className={
                      block.ordered
                        ? "tabular shrink-0 text-muted-foreground/70"
                        : "mt-2 size-1 shrink-0 rounded-full bg-muted-foreground/60"
                    }
                  >
                    {block.ordered ? `${itemIndex + 1}.` : ""}
                  </span>
                  <span className="text-muted-foreground">
                    {renderInline(item)}
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

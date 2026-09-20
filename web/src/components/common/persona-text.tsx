/*
 * The persona is stored as Markdown, but it is shown as plain readable text —
 * never as an editable Markdown source. To change it, the user edits the
 * onboarding answers and regenerates. This renders the small subset of
 * Markdown the persona actually uses (headings, bullets, paragraphs).
 */

type Block =
  | { type: "heading"; level: 1 | 2; text: string }
  | { type: "list"; items: string[] }
  | { type: "paragraph"; text: string };

function clean(text: string): string {
  return text.replace(/\*\*/g, "").replace(/`/g, "").trim();
}

function parsePersona(content: string): Block[] {
  const blocks: Block[] = [];
  let list: string[] | null = null;

  const flush = () => {
    if (list && list.length) blocks.push({ type: "list", items: list });
    list = null;
  };

  for (const raw of content.split("\n")) {
    const line = raw.trim();

    if (!line) {
      flush();
      continue;
    }
    if (line.startsWith("## ")) {
      flush();
      blocks.push({ type: "heading", level: 2, text: clean(line.slice(3)) });
      continue;
    }
    if (line.startsWith("# ")) {
      flush();
      blocks.push({ type: "heading", level: 1, text: clean(line.slice(2)) });
      continue;
    }
    if (line.startsWith("- ") || line.startsWith("* ")) {
      (list ??= []).push(clean(line.slice(2)));
      continue;
    }
    flush();
    blocks.push({ type: "paragraph", text: clean(line) });
  }

  flush();
  return blocks;
}

export function PersonaText({ content }: { content: string }) {
  const blocks = parsePersona(content);

  return (
    <div className="space-y-4">
      {blocks.map((block, index) => {
        if (block.type === "heading" && block.level === 1) {
          return (
            <h2
              key={index}
              className="font-heading text-lg font-semibold tracking-tight"
            >
              {block.text}
            </h2>
          );
        }
        if (block.type === "heading") {
          return (
            <h3
              key={index}
              className="font-heading text-sm font-semibold tracking-tight"
            >
              {block.text}
            </h3>
          );
        }
        if (block.type === "list") {
          return (
            <ul key={index} className="space-y-1.5">
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex} className="flex gap-2.5">
                  <span className="mt-2 size-1 shrink-0 rounded-full bg-muted-foreground/60" />
                  <span className="text-muted-foreground">{item}</span>
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={index} className="text-muted-foreground">
            {block.text}
          </p>
        );
      })}
    </div>
  );
}

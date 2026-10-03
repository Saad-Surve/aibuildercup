/**
 * Draft content helpers — Obsidian-style.
 *
 * Each block stores **Markdown**. The editor shows the rendered preview and
 * swaps in the raw Markdown only for the block you are editing, exactly like
 * Obsidian's live preview.
 *
 * Inline alternatives use a small syntax:
 *
 *   {{ original | ~*another option | @my option }}
 *
 * Each option may carry markers at the very start (in any order):
 *
 *   `*`  the active option (exactly one; defaults to the first when absent)
 *   `~`  AI-generated alternative
 *   `@`  user-written alternative
 *   —    no marker means the original
 *
 * The original is never removed: it stays in the list as the unmarked option, so
 * the document is self-describing and survives save/load with no sidecar. Word-,
 * sentence-, and paragraph-level alternatives all use the same shape. Legacy
 * documents that predate the markers (`{{a | b | c}}`) still parse: the first
 * option is active and original, the rest are user alternatives.
 */

export type AltOrigin = "original" | "user" | "ai";

export interface AltOption {
  text: string;
  origin: AltOrigin;
}

export interface ParsedVariant {
  options: AltOption[];
  activeIndex: number;
}

const VARIANT = /\{\{([^{}]*)\}\}/g;
const MARKER_RUN = /^[*@~]+/;

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Escape a value destined for an HTML attribute (JSON payloads). */
function escapeAttr(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function markersOf(option: string): string {
  return option.match(MARKER_RUN)?.[0] ?? "";
}

/** Parse the inside of a `{{…}}` into options plus the active index. */
export function parseVariantInner(inner: string): ParsedVariant {
  const raw = inner
    .split("|")
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
  const hasMarkers = raw.some((part) => markersOf(part).length > 0);

  let originalSeen = false;
  const options: AltOption[] = raw.map((part) => {
    const markers = markersOf(part);
    const text = part.slice(markers.length).trim();
    if (markers.includes("~")) return { text, origin: "ai" };
    if (markers.includes("@")) return { text, origin: "user" };
    if (!originalSeen) {
      originalSeen = true;
      return { text, origin: "original" };
    }
    // Legacy docs have no markers at all, and a hand-written `*`-only option
    // leaves no origin: only the first unmarked option is the original.
    return { text, origin: hasMarkers || raw.length > 1 ? "user" : "original" };
  });

  const marked = raw.findIndex((part) => markersOf(part).includes("*"));
  const activeIndex = marked >= 0 ? marked : 0;
  return { options, activeIndex };
}

function serializeOption(option: AltOption, active: boolean): string {
  const marker =
    (active ? "*" : "") +
    (option.origin === "ai" ? "~" : option.origin === "user" ? "@" : "");
  return `${marker}${option.text}`;
}

/** Serialize options back into the inline `{{…}}` syntax. */
export function serializeVariant(
  options: AltOption[],
  activeIndex: number,
): string {
  const safeActive =
    options.length === 0 ? 0 : Math.max(0, Math.min(options.length - 1, activeIndex));
  return `{{${options
    .map((option, index) => serializeOption(option, index === safeActive))
    .join(" | ")}}}`;
}

/** Build the inline syntax for a fresh span (original active, alternatives after). */
export function variantSyntax(
  original: string,
  alternatives: { text: string; origin: AltOrigin }[] = [],
): string {
  return serializeVariant(
    [{ text: original, origin: "original" }, ...alternatives],
    0,
  );
}

interface VariantMatch {
  start: number;
  end: number;
  inner: string;
  index: number;
}

/** Every `{{…}}` span in a block, in document order, with its offsets. */
export function variantSpans(markdown: string): VariantMatch[] {
  const spans: VariantMatch[] = [];
  const pattern = new RegExp(VARIANT.source, "g");
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(markdown))) {
    spans.push({
      start: match.index,
      end: match.index + match[0].length,
      inner: match[1],
      index: spans.length,
    });
  }
  return spans;
}

/** The variant containing a caret/character offset, if any. */
export function variantAtOffset(
  markdown: string,
  offset: number,
): VariantMatch | null {
  return (
    variantSpans(markdown).find(
      (span) => offset >= span.start && offset <= span.end,
    ) ?? null
  );
}

const VOWEL_EXCEPTIONS: Record<string, boolean> = {
  // A silent h takes "an", a leading vowel that sounds like a consonant takes "a".
  hour: true,
  honest: true,
  honour: true,
  honor: true,
  heir: true,
  uni: false,
  use: false,
  user: false,
  usual: false,
  european: false,
  one: false,
  once: false,
  ubiq: false,
};

/** Whether a word starts with a vowel *sound* (a small, practical heuristic). */
export function startsWithVowelSound(word: string): boolean {
  const clean = word.trim().toLowerCase().replace(/^["'\u201c\u2018([{]/, "");
  if (!clean) return false;
  for (const [prefix, vowel] of Object.entries(VOWEL_EXCEPTIONS)) {
    if (clean.startsWith(prefix)) return vowel;
  }
  return /^[aeiou]/.test(clean);
}

/**
 * Keep the article in front of an alternative group grammatical. When a version
 * starting with a vowel sound is active, the neighbouring "a" becomes "an" (and
 * back again for consonants). Only touches the article directly before a group.
 */
export function reconcileArticles(markdown: string): string {
  const spans = variantSpans(markdown);
  let result = markdown;
  // Walk right to left so earlier offsets stay valid as we edit.
  for (let index = spans.length - 1; index >= 0; index -= 1) {
    const span = spans[index];
    const { options, activeIndex } = parseVariantInner(span.inner);
    const active = options[activeIndex] ?? options[0];
    const firstWord = (active?.text ?? "").split(/\s+/)[0] ?? "";
    if (!firstWord) continue;
    const wanted = startsWithVowelSound(firstWord) ? "an" : "a";
    const before = result.slice(0, span.start);
    const match = before.match(/\b(a|an)(\s*)$/i);
    if (!match || match[1].toLowerCase() === wanted) continue;
    const article =
      match[1][0] === match[1][0].toUpperCase()
        ? wanted[0].toUpperCase() + wanted.slice(1)
        : wanted;
    result = before.slice(0, match.index) + article + match[2] + result.slice(span.start);
  }
  return result;
}

function replaceVariantAt(
  markdown: string,
  variantIndex: number,
  update: (parsed: ParsedVariant) => ParsedVariant,
): string {
  let index = 0;
  return markdown.replace(VARIANT, (match, inner: string) => {
    if (index++ !== variantIndex) return match;
    const next = update(parseVariantInner(inner));
    return serializeVariant(next.options, next.activeIndex);
  });
}

/** Make one option the active version (the original stays in the list). */
export function setActiveOption(
  markdown: string,
  variantIndex: number,
  optionIndex: number,
): string {
  return reconcileArticles(
    replaceVariantAt(markdown, variantIndex, ({ options }) => ({
      options,
      activeIndex:
        options.length === 0
          ? 0
          : Math.max(0, Math.min(options.length - 1, optionIndex)),
    })),
  );
}

/** Append an option. Returns the index it landed at. */
export function addVariantOption(
  markdown: string,
  variantIndex: number,
  option: AltOption,
): string {
  return replaceVariantAt(markdown, variantIndex, ({ options, activeIndex }) => ({
    options: [...options, option],
    activeIndex,
  }));
}

export function updateVariantOption(
  markdown: string,
  variantIndex: number,
  optionIndex: number,
  text: string,
): string {
  return replaceVariantAt(markdown, variantIndex, ({ options, activeIndex }) => ({
    options: options.map((option, index) =>
      index === optionIndex ? { ...option, text } : option,
    ),
    activeIndex,
  }));
}

export function deleteVariantOption(
  markdown: string,
  variantIndex: number,
  optionIndex: number,
): string {
  const next = replaceVariantAt(
    markdown,
    variantIndex,
    ({ options, activeIndex }) => {
      if (options.length <= 1) return { options, activeIndex };
      const remaining = options.filter((_, index) => index !== optionIndex);
      let nextActive = activeIndex;
      if (optionIndex < activeIndex) nextActive -= 1;
      else if (optionIndex === activeIndex) nextActive = 0;
      return {
        options: remaining,
        activeIndex: Math.max(0, Math.min(remaining.length - 1, nextActive)),
      };
    },
  );
  return unwrapSingletonVariants(next);
}

/** Drop the `{{…}}` wrapper once a span has nothing left to choose between. */
export function unwrapSingletonVariants(markdown: string): string {
  return markdown.replace(VARIANT, (match, inner: string) => {
    const { options, activeIndex } = parseVariantInner(inner);
    if (options.length > 1) return match;
    return options[activeIndex]?.text ?? options[0]?.text ?? "";
  });
}

export function moveVariantOption(
  markdown: string,
  variantIndex: number,
  from: number,
  to: number,
): string {
  return replaceVariantAt(markdown, variantIndex, ({ options, activeIndex }) => {
    if (to < 0 || to >= options.length || from === to) {
      return { options, activeIndex };
    }
    const next = [...options];
    const [moved] = next.splice(from, 1);
    next.splice(to, 0, moved);
    let nextActive = activeIndex;
    if (activeIndex === from) nextActive = to;
    else if (from < activeIndex && to >= activeIndex) nextActive -= 1;
    else if (from > activeIndex && to <= activeIndex) nextActive += 1;
    return { options: next, activeIndex: nextActive };
  });
}

function dotsHtml(total: number, activeIndex: number): string {
  const count = Math.max(1, Math.min(3, total));
  let html = "";
  for (let index = 0; index < count; index += 1) {
    const on = index <= Math.min(activeIndex, count - 1);
    html += `<i class="${on ? "is-on" : ""}"></i>`;
  }
  return html;
}

interface InlineCounter {
  value: number;
}

/** Bold/italic/code over already-escaped text (never touches attributes). */
function formatInline(escaped: string): string {
  return escaped
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\n]+?)\*/g, "$1<em>$2</em>")
    .replace(/`([^`]+?)`/g, "<code>$1</code>");
}

/** The rendered inner HTML of a variant: active text plus its version dots. */
function variantInnerHtml(options: AltOption[], activeIndex: number): string {
  const active = options[activeIndex] ?? options[0];
  return (
    `${formatInline(escapeHtml(active?.text ?? ""))}` +
    `<span class="draft-alt-dots" aria-hidden="true" contenteditable="false">${dotsHtml(
      options.length,
      activeIndex,
    )}</span>`
  );
}

/** A block-level variant (a whole heading or paragraph is one alternative group). */
function variantBlockHtml(
  options: AltOption[],
  activeIndex: number,
  tag: string,
  className: string,
  counter: InlineCounter,
): string {
  const active = options[activeIndex] ?? options[0];
  const encoded = escapeAttr(JSON.stringify(options));
  const variantIndex = counter.value++;
  const changed = active?.origin !== "original";
  return (
    `<${tag} class="draft-variant draft-variant-block ${className}" ` +
    `data-variant="${encoded}" data-variant-index="${variantIndex}" ` +
    `data-active-index="${activeIndex}" data-changed="${changed}" ` +
    `title="Click for alternatives">` +
    `${variantInnerHtml(options, activeIndex)}` +
    `</${tag}>`
  );
}

/** An inline span for a freshly created variant (used when wrapping a selection). */
export function inlineVariantHtml(
  options: AltOption[],
  activeIndex: number,
): string {
  const active = options[activeIndex] ?? options[0];
  const encoded = escapeAttr(JSON.stringify(options));
  const changed = active?.origin !== "original";
  return (
    `<span class="draft-variant" data-variant="${encoded}" ` +
    `data-variant-index="-1" data-active-index="${activeIndex}" ` +
    `data-changed="${changed}" ` +
    `title="Click for alternatives">` +
    `${variantInnerHtml(options, activeIndex)}</span>`
  );
}

/** An entire line that is nothing but one alternative group. */
function wholeLineVariant(line: string): string | null {
  const match = line.match(/^\s*\{\{([^{}]*)\}\}\s*$/);
  return match ? match[1] : null;
}

/** Inline Markdown (bold, italic, code, inline variants) to HTML. */
function inline(markdown: string, counter: InlineCounter): string {
  let html = "";
  let last = 0;
  const pattern = new RegExp(VARIANT.source, "g");
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(markdown))) {
    html += formatInline(escapeHtml(markdown.slice(last, match.index)));
    const { options, activeIndex } = parseVariantInner(match[1]);
    if (options.length === 1) {
      html += formatInline(escapeHtml(options[0].text));
    } else if (options.length > 1) {
      const active = options[activeIndex] ?? options[0];
      // JSON is escaped for the attribute exactly once, so quotes round-trip.
      const encoded = escapeAttr(JSON.stringify(options));
      const variantIndex = counter.value++;
      const changed = active.origin !== "original";
      html +=
        `<span class="draft-variant" data-variant="${encoded}" ` +
        `data-variant-index="${variantIndex}" data-active-index="${activeIndex}" ` +
        `data-changed="${changed}" ` +
        `title="Click for alternatives">${formatInline(escapeHtml(active.text))}` +
        `<span class="draft-alt-dots" aria-hidden="true" contenteditable="false">${dotsHtml(
          options.length,
          activeIndex,
        )}</span></span>`;
    }
    last = match.index + match[0].length;
  }
  html += formatInline(escapeHtml(markdown.slice(last)));
  return html;
}

/** Render a block's Markdown to safe HTML. */
export function markdownToHtml(markdown: string): string {
  if (!markdown) return "";
  const counter: InlineCounter = { value: 0 };
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
  for (let index = 0; index < lines.length; index += 1) {
    const raw = lines[index];
    const line = raw.trimEnd();
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    const headingLevel = heading ? Math.min(6, heading[1].length) : 0;
    const body = heading ? heading[2] : line;
    // A group is paragraph/heading-level only when it is the whole block. A
    // variant that is merely one line of a multi-line paragraph stays inline so
    // the paragraph is not split.
    const aloneInBlock =
      headingLevel > 0 ||
      ((index === 0 || lines[index - 1].trim() === "") &&
        (index === lines.length - 1 || lines[index + 1].trim() === ""));
    const whole = aloneInBlock ? wholeLineVariant(body) : null;
    if (whole) {
      flushParagraph();
      closeList();
      const { options, activeIndex } = parseVariantInner(whole);
      if (options.length <= 1) {
        const text = formatInline(escapeHtml(options[0]?.text ?? ""));
        out.push(
          headingLevel ? `<h${headingLevel}>${text}</h${headingLevel}>` : `<p>${text}</p>`,
        );
      } else if (headingLevel) {
        out.push(
          variantBlockHtml(
            options,
            activeIndex,
            `h${headingLevel}`,
            "draft-variant-heading",
            counter,
          ),
        );
      } else {
        out.push(
          variantBlockHtml(
            options,
            activeIndex,
            "p",
            "draft-variant-paragraph",
            counter,
          ),
        );
      }
      continue;
    }
    if (heading) {
      flushParagraph();
      closeList();
      out.push(`<h${headingLevel}>${inline(heading[2], counter)}</h${headingLevel}>`);
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      flushParagraph();
      if (!listOpen) {
        out.push("<ul>");
        listOpen = true;
      }
      out.push(`<li>${inline(line.replace(/^\s*[-*]\s+/, ""), counter)}</li>`);
      continue;
    }
    const quote = line.match(/^>\s?(.*)$/);
    if (quote) {
      flushParagraph();
      closeList();
      out.push(`<blockquote>${inline(quote[1], counter)}</blockquote>`);
      continue;
    }
    if (line.trim() === "") {
      flushParagraph();
      closeList();
      continue;
    }
    paragraph.push(inline(line, counter));
  }
  flushParagraph();
  closeList();
  return out.join("");
}

function activeOptionText(inner: string): string {
  const { options, activeIndex } = parseVariantInner(inner);
  return options[activeIndex]?.text ?? options[0]?.text ?? "";
}

/** Resolve inline variants to their active option, keeping Markdown intact. */
export function resolveVariants(markdown: string): string {
  return markdown.replace(VARIANT, (_match, inner: string) =>
    activeOptionText(inner),
  );
}

/** The plain text a block shows in summaries/exports (active option only). */
export function markdownToPlain(markdown: string): string {
  if (!markdown) return "";
  return markdown
    .replace(VARIANT, (_match, inner: string) => activeOptionText(inner))
    .replace(/[#>*`]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export interface VariantData extends ParsedVariant {
  variantIndex: number;
}

/** Read a rendered variant span back into structured data. */
export function parseVariant(span: Element): VariantData | null {
  const raw = span.getAttribute("data-variant");
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed) || parsed.length === 0) return null;
    const options: AltOption[] = parsed.map((item) => {
      const value = item as Partial<AltOption>;
      const origin: AltOrigin =
        value.origin === "ai" || value.origin === "user"
          ? value.origin
          : "original";
      return { text: String(value.text ?? ""), origin };
    });
    const activeRaw = Number(span.getAttribute("data-active-index"));
    const activeIndex =
      Number.isFinite(activeRaw) && activeRaw >= 0 && activeRaw < options.length
        ? activeRaw
        : 0;
    const indexRaw = Number(span.getAttribute("data-variant-index"));
    return {
      options,
      activeIndex,
      variantIndex: Number.isFinite(indexRaw) ? indexRaw : 0,
    };
  } catch {
    return null;
  }
}

/**
 * @deprecated Kept for callers that still reorder by moving the chosen option to
 * the front. New code should use {@link setActiveOption}.
 */
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
    const found = parseVariantInner(match[1]).options;
    if (
      found.length === options.length &&
      found.every((option) => options.includes(option.text))
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

/** The sentence (or line) around a caret offset, used by the `??` shortcut. */
export function sentenceAtOffset(
  value: string,
  offset: number,
): { start: number; end: number; text: string } | null {
  if (!value) return null;
  const clamped = Math.max(0, Math.min(value.length, offset));
  const before = value.slice(0, clamped);
  const after = value.slice(clamped);
  const startBreak = Math.max(
    before.lastIndexOf(". "),
    before.lastIndexOf("! "),
    before.lastIndexOf("? "),
    before.lastIndexOf("\n"),
  );
  const start = startBreak === -1 ? 0 : startBreak + 1;
  const candidates = [". ", "! ", "? ", "\n"]
    .map((token) => after.indexOf(token))
    .filter((index) => index >= 0);
  const end =
    candidates.length === 0
      ? value.length
      : clamped + Math.min(...candidates) + 1;
  const text = value
    .slice(start, end)
    .replace(VARIANT, (_match, inner: string) => activeOptionText(inner))
    .trim();
  if (!text) return null;
  return { start, end, text };
}

/* ───────────────────────────────────────────────────────────────────────────
 * DOM → Markdown
 *
 * The live editor is a contenteditable surface, so the DOM is the source of
 * truth while typing. These helpers walk it back into the stored Markdown and
 * recognise the rendered variant elements (inline spans and whole-line blocks).
 * ─────────────────────────────────────────────────────────────────────────── */

function serializeDomNode(node: Node): string {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent ?? "";
  if (!(node instanceof HTMLElement)) return "";
  if (node.hasAttribute("data-variant")) {
    const data = parseVariant(node);
    if (data && data.options.length > 0) {
      const inner = serializeVariant(data.options, data.activeIndex);
      const heading = /^h([1-6])$/.exec(node.tagName.toLowerCase());
      return heading ? `${"#".repeat(Number(heading[1]))} ${inner}` : inner;
    }
  }
  const tag = node.tagName.toLowerCase();
  const children = () =>
    Array.from(node.childNodes).map(serializeDomNode).join("");
  switch (tag) {
    case "br":
      return "\n";
    case "strong":
    case "b":
      return `**${children()}**`;
    case "em":
    case "i":
      return `*${children()}*`;
    case "code":
      return `\`${node.textContent ?? ""}\``;
    case "h1":
    case "h2":
    case "h3":
    case "h4":
    case "h5":
    case "h6":
      return `${"#".repeat(Number(tag[1]))} ${children()}`;
    case "li":
      return `- ${children()}`;
    case "ul":
    case "ol":
      return Array.from(node.children).map(serializeDomNode).join("\n");
    case "blockquote":
      return `> ${children()}`;
    case "p":
    case "div":
      return children();
    default:
      return children();
  }
}

/** Serialize a contenteditable root back into stored Markdown. */
export function htmlToMarkdown(root: HTMLElement): string {
  const blocks: string[] = [];
  const push = (node: Node) => {
    // Some browsers wrap everything in a bare <div>; treat it as transparent.
    if (
      node instanceof HTMLElement &&
      node.tagName.toLowerCase() === "div" &&
      !node.hasAttribute("data-variant")
    ) {
      node.childNodes.forEach(push);
      return;
    }
    blocks.push(serializeDomNode(node).replace(/\u00a0/g, " "));
  };
  root.childNodes.forEach(push);
  return blocks
    .join("\n\n")
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/**
 * Fold any in-place edits back into the `data-variant` payload before
 * serializing. A manual edit to the original or an AI version forks a new
 * user version (so nothing is overwritten); an edit to an existing user
 * version updates it in place.
 */
export function syncVariantsFromDom(root: HTMLElement): void {
  root.querySelectorAll<HTMLElement>("[data-variant]").forEach((element) => {
    const data = parseVariant(element);
    if (!data || data.options.length === 0) return;
    const clone = element.cloneNode(true) as HTMLElement;
    clone.querySelector(".draft-alt-dots")?.remove();
    const text = (clone.textContent ?? "").replace(/\u00a0/g, " ").trim();
    const active = data.options[data.activeIndex];
    if (!active || active.text === text) return;

    let options: AltOption[];
    let activeIndex: number;
    if (active.origin === "user") {
      options = data.options.map((option, index) =>
        index === data.activeIndex ? { ...option, text } : option,
      );
      activeIndex = data.activeIndex;
    } else {
      options = [...data.options, { text, origin: "user" }];
      activeIndex = options.length - 1;
    }
    element.setAttribute("data-variant", JSON.stringify(options));
    element.setAttribute("data-active-index", String(activeIndex));
    element.setAttribute(
      "data-changed",
      String(options[activeIndex].origin !== "original"),
    );
  });
}

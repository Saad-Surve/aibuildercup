"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Loading03Icon,
  MagicWand01Icon,
  SparklesIcon,
} from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { AlternativesPanel } from "@/components/projects/draft/alternatives-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Drawer, DrawerContent } from "@/components/ui/drawer";
import { Input } from "@/components/ui/input";
import {
  addVariantOption,
  deleteVariantOption,
  htmlToMarkdown,
  inlineVariantHtml,
  markdownToHtml,
  markdownToPlain,
  moveVariantOption,
  parseVariantInner,
  setActiveOption,
  syncVariantsFromDom,
  updateVariantOption,
  variantSpans,
} from "@/lib/draft-content";
import type { AltOption } from "@/lib/draft-content";
import type { Draft, DraftBlock } from "@/lib/types";
import { cn } from "@/lib/utils";

const EDITOR_HEIGHT =
  "max-h-[min(78vh,44rem)] lg:h-[min(78vh,44rem)] lg:snap-start lg:snap-always lg:scroll-mt-20";

interface AltSelection {
  index: number;
}

/**
 * The draft as one free-flowing, Obsidian-style live document.
 *
 * There are no blocks in the surface: every paragraph, heading and phrase is
 * edited in place on a single contenteditable sheet. Any span that has
 * alternatives renders as a variant — a wavy underline and version dots for
 * headings and phrases, a vertical marker on the margin for whole paragraphs.
 * Click a variant (or just park the caret beside one) and press **Tab** to
 * cycle through its versions; the original is always kept. When a version
 * starting with a vowel becomes active, the neighbouring "a" becomes "an".
 *
 * Formatting is WYSIWYG, so the DOM is the source of truth while typing and is
 * serialized back to the stored Markdown. External changes (cycling, AI, the
 * writing partner) re-render from the stored Markdown.
 */
export function FreeFlowEditor({
  draft,
  onTitle,
  onEditMarkdown,
  onSuggest,
  onSelectText,
  onUseContext,
  readOnly = false,
}: {
  draft: Draft;
  onTitle: (title: string) => void;
  onEditMarkdown: (markdown: string) => void;
  onSuggest: (
    text: string,
    mode: "rewrite" | "alternatives",
  ) => Promise<string[]>;
  onSelectText: (text: string) => void;
  onUseContext: (text: string) => void;
  /** Render the document as static text; no caret, toolbar, or version cycling. */
  readOnly?: boolean;
}) {
  const [selection, setSelection] = useState<AltSelection | null>(null);
  const [suggesting, setSuggesting] = useState(false);
  const [toolbar, setToolbar] = useState<{ top: number; left: number } | null>(
    null,
  );

  const rootRef = useRef<HTMLDivElement>(null);
  // The Markdown the surface currently shows. Typing updates this so the render
  // effect below never yanks the caret out from under the user; external edits
  // change `docMarkdown` and force a re-render.
  const lastRendered = useRef<string | null>(null);

  const docMarkdown = useMemo(
    () => (draft.blocks.length ? draft.blocks.map(activeText).join("\n\n") : ""),
    [draft.blocks],
  );
  const alternativeCount = useMemo(
    () => variantSpans(docMarkdown).length,
    [docMarkdown],
  );
  const wordCount = useMemo(() => {
    const plain = markdownToPlain(docMarkdown);
    return plain ? plain.split(/\s+/).length : 0;
  }, [docMarkdown]);

  const selectedVariant = useMemo(() => {
    if (!selection) return null;
    const span = variantSpans(docMarkdown)[selection.index];
    return span ? parseVariantInner(span.inner) : null;
  }, [selection, docMarkdown]);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    if (lastRendered.current === docMarkdown) return;
    root.innerHTML = markdownToHtml(docMarkdown);
    lastRendered.current = docMarkdown;
  }, [docMarkdown]);

  // Keep the selected group highlighted after every re-render. `docMarkdown` is
  // intentional: the render effect above replaces the innerHTML, so the marker
  // must be re-applied whenever the document changes.
  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    root
      .querySelectorAll("[data-variant-selected]")
      .forEach((element) => element.removeAttribute("data-variant-selected"));
    if (!selection) return;
    const element = root.querySelector<HTMLElement>(
      `[data-variant-index="${selection.index}"]`,
    );
    element?.setAttribute("data-variant-selected", "true");
    // A cycle replaces the sheet's HTML; keep the document focused so the next
    // Tab is not swallowed by a focus hunt.
    if (element && document.activeElement === document.body) {
      root.focus({ preventScroll: true });
    }
    // oxlint-disable-next-line react/exhaustive-effect-dependencies
  }, [selection, docMarkdown]);

  const commit = useCallback(() => {
    const root = rootRef.current;
    if (!root) return;
    // In-place edits are written back into the variant payloads first, so a
    // manual change survives alongside the AI versions.
    syncVariantsFromDom(root);
    const markdown = htmlToMarkdown(root);
    lastRendered.current = markdown;
    onEditMarkdown(markdown);
  }, [onEditMarkdown]);

  const cycle = useCallback(
    (index: number, direction: 1 | -1) => {
      const span = variantSpans(docMarkdown)[index];
      if (!span) return;
      const parsed = parseVariantInner(span.inner);
      if (parsed.options.length < 2) return;
      const count = parsed.options.length;
      const next = (parsed.activeIndex + direction + count) % count;
      setSelection({ index });
      onEditMarkdown(setActiveOption(docMarkdown, index, next));
    },
    [docMarkdown, onEditMarkdown],
  );

  // Tab cycles the selected group wherever the focus happens to be.
  useEffect(() => {
    if (!selection) return;
    const index = selection.index;
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      // Never steal Tab from the alternatives panel's fields.
      if (target?.closest("input, textarea, select")) return;
      if (event.key === "Escape") {
        setSelection(null);
        return;
      }
      if (event.key === "Tab") {
        event.preventDefault();
        cycle(index, event.shiftKey ? -1 : 1);
      }
    }
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [selection, cycle]);

  // A small floating toolbar appears over a text selection.
  const refreshToolbar = useCallback(() => {
    const root = rootRef.current;
    if (!root) return;
    const current = window.getSelection();
    if (!current || current.rangeCount === 0 || current.isCollapsed) {
      setToolbar(null);
      return;
    }
    const range = current.getRangeAt(0);
    if (!root.contains(range.commonAncestorContainer)) {
      setToolbar(null);
      return;
    }
    const host =
      range.commonAncestorContainer.nodeType === Node.ELEMENT_NODE
        ? (range.commonAncestorContainer as Element)
        : range.commonAncestorContainer.parentElement;
    const touchesVariant =
      host?.closest("[data-variant]") ??
      endpointVariant(range.startContainer) ??
      endpointVariant(range.endContainer);
    if (touchesVariant) {
      setToolbar(null);
      return;
    }
    const text = range.toString().trim();
    if (text) onSelectText(text);
    const rect = range.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) {
      setToolbar(null);
      return;
    }
    setToolbar({ top: rect.top - 46, left: rect.left + rect.width / 2 });
  }, [onSelectText]);

  useEffect(() => {
    document.addEventListener("selectionchange", refreshToolbar);
    return () => document.removeEventListener("selectionchange", refreshToolbar);
  }, [refreshToolbar]);

  function format(command: string, value?: string) {
    document.execCommand(command, false, value);
    rootRef.current?.focus();
    commit();
  }

  // Convert a leading "# ", "## " or "### " into a heading as you type.
  function handleInput() {
    applyHeadingShortcut(rootRef.current);
    commit();
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "Tab" || selection) return;
    const index = variantIndexAtSelection(rootRef.current);
    if (index == null) return;
    event.preventDefault();
    cycle(index, event.shiftKey ? -1 : 1);
  }

  function handleClick(event: React.MouseEvent<HTMLDivElement>) {
    const variant = (event.target as Element).closest("[data-variant]");
    if (variant && rootRef.current?.contains(variant)) {
      setSelection({ index: readVariantIndex(variant) ?? 0 });
    } else {
      setSelection(null);
    }
  }

  function handlePaste(event: React.ClipboardEvent<HTMLDivElement>) {
    event.preventDefault();
    const text = event.clipboardData.getData("text/plain");
    document.execCommand("insertText", false, text);
    commit();
  }

  async function alternativesForSelection() {
    const current = window.getSelection();
    if (!current || current.rangeCount === 0) return;
    const range = current.getRangeAt(0).cloneRange();
    const text = range.toString().trim();
    if (!text) return;
    setSuggesting(true);
    try {
      const suggestions = await onSuggest(text, "alternatives");
      const fresh = suggestions
        .map((suggestion) => suggestion.trim())
        .filter(Boolean)
        .slice(0, 6);
      if (fresh.length === 0) return;
      const options: AltOption[] = [
        { text, origin: "original" },
        ...fresh.map((value) => ({ text: value, origin: "ai" as const })),
      ];
      current.removeAllRanges();
      current.addRange(range);
      document.execCommand("insertHTML", false, inlineVariantHtml(options, 0));
      // Leave a caret, not a selection, so wrapping a selection does not silently
      // become the chat context.
      window.getSelection()?.collapseToEnd();
      const root = rootRef.current;
      if (root) {
        // Deliberately leave `lastRendered` stale so the sheet re-renders and the
        // new group gets a real variant index for click/Tab tracking.
        onEditMarkdown(htmlToMarkdown(root));
      }
    } finally {
      setSuggesting(false);
      setToolbar(null);
    }
  }

  function mutateSelected(
    updater: (markdown: string, index: number) => string,
  ) {
    if (!selection) return;
    onEditMarkdown(updater(docMarkdown, selection.index));
  }

  async function suggestForSelectedVariant() {
    if (!selection || !selectedVariant) return;
    const original =
      selectedVariant.options.find((option) => option.origin === "original") ??
      selectedVariant.options[0];
    const existing = new Set(
      selectedVariant.options.map((option) => option.text.toLowerCase().trim()),
    );
    setSuggesting(true);
    try {
      const suggestions = await onSuggest(original.text, "alternatives");
      const fresh = suggestions
        .map((suggestion) => suggestion.trim())
        .filter(
          (suggestion) => suggestion && !existing.has(suggestion.toLowerCase()),
        )
        .slice(0, 6);
      if (fresh.length === 0) return;
      let markdown = docMarkdown;
      for (const text of fresh) {
        markdown = addVariantOption(markdown, selection.index, {
          text,
          origin: "ai",
        });
      }
      onEditMarkdown(markdown);
    } finally {
      setSuggesting(false);
    }
  }

  return (
    <>
      {readOnly ? (
        <Card className={cn(EDITOR_HEIGHT, "flex min-h-0 flex-col gap-0 py-0")}>
          <CardHeader className="shrink-0 gap-3 border-b py-(--card-spacing)">
            <div className="min-w-0 flex-1 space-y-2">
              <h2 className="font-heading text-xl font-semibold">
                {draft.title || "Untitled draft"}
              </h2>
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <Badge variant="secondary">
                  {draft.brief.format === "script"
                    ? "Video script"
                    : "Written content"}
                </Badge>
                <span className="tabular">{wordCount} words</span>
                <span aria-hidden>·</span>
                <span className="tabular">
                  {alternativeCount}{" "}
                  {alternativeCount === 1 ? "alternative" : "alternatives"}
                </span>
              </div>
            </div>
          </CardHeader>
          <div className="flex min-h-0 flex-1 flex-col">
            <CardContent className="scroll-fade-y min-h-0 flex-1 overflow-y-auto overscroll-y-contain px-(--card-spacing) py-(--card-spacing)">
              <div
                className="prose-draft mx-auto min-h-full w-full max-w-[70ch] px-1 py-2 text-sm leading-relaxed"
                dangerouslySetInnerHTML={{ __html: markdownToHtml(docMarkdown) }}
              />
            </CardContent>
          </div>
        </Card>
      ) : (
      <Card className={cn(EDITOR_HEIGHT, "flex min-h-0 flex-col gap-0 py-0")}>
        <CardHeader className="shrink-0 gap-3 border-b py-(--card-spacing)">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1 space-y-2">
              <Input
                aria-label="Draft title"
                value={draft.title}
                onChange={(event) => onTitle(event.target.value)}
                placeholder="Untitled draft"
                className="h-auto border-0 bg-transparent px-0 font-heading text-xl font-semibold shadow-none focus-visible:ring-0 dark:bg-transparent"
              />
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <Badge variant="secondary">
                  {draft.brief.format === "script"
                    ? "Video script"
                    : "Written content"}
                </Badge>
                <span className="tabular">{wordCount} words</span>
                <span aria-hidden>·</span>
                <span className="tabular">
                  {alternativeCount}{" "}
                  {alternativeCount === 1 ? "alternative" : "alternatives"}
                </span>
                <span aria-hidden>·</span>
                <span className="text-muted-foreground/80">
                  Click a phrase, then press Tab to swap versions
                </span>
              </div>
            </div>
          </div>
        </CardHeader>

        <div className="flex min-h-0 flex-1 flex-col">
          <CardContent
            className="scroll-fade-y min-h-0 flex-1 overflow-y-auto overscroll-y-contain px-(--card-spacing) py-(--card-spacing)"
            onClick={handleClick}
          >
            <div
              ref={rootRef}
              contentEditable
              suppressContentEditableWarning
              role="textbox"
              tabIndex={0}
              aria-multiline="true"
              aria-label="Draft document"
              data-placeholder="Start writing, or ask the writing partner for a first draft…"
              onInput={handleInput}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              className="prose-draft mx-auto min-h-full w-full max-w-[70ch] px-1 py-2 text-sm leading-relaxed outline-none"
            />
          </CardContent>
        </div>
      </Card>

      )}

      <Drawer
        open={Boolean(!readOnly && selection && selectedVariant)}
        modal={false}
        disablePointerDismissal
        onOpenChange={(open) => {
          if (!open) setSelection(null);
        }}
      >
        <DrawerContent aria-label="Alternatives" initialFocus={false}>
          {selectedVariant ? (
            <AlternativesPanel
              options={selectedVariant.options}
              activeIndex={selectedVariant.activeIndex}
              suggesting={suggesting}
              onSelect={(optionIndex) =>
                mutateSelected((markdown, index) =>
                  setActiveOption(markdown, index, optionIndex),
                )
              }
              onAdd={(text) =>
                mutateSelected((markdown, index) =>
                  addVariantOption(markdown, index, { text, origin: "user" }),
                )
              }
              onUpdate={(optionIndex, text) =>
                mutateSelected((markdown, index) =>
                  updateVariantOption(markdown, index, optionIndex, text),
                )
              }
              onDelete={(optionIndex) => {
                const willUnwrap = selectedVariant.options.length <= 2;
                mutateSelected((markdown, index) =>
                  deleteVariantOption(markdown, index, optionIndex),
                );
                if (willUnwrap) setSelection(null);
              }}
              onMove={(from, to) =>
                mutateSelected((markdown, index) =>
                  moveVariantOption(markdown, index, from, to),
                )
              }
              onSuggest={() => void suggestForSelectedVariant()}
              onClose={() => setSelection(null)}
            />
          ) : null}
        </DrawerContent>
      </Drawer>

      {toolbar && !readOnly ? (
        <div
          role="toolbar"
          aria-label="Formatting"
          className="fixed z-50 flex -translate-x-1/2 items-center gap-0.5 rounded-lg border bg-popover p-1 text-popover-foreground shadow-md"
          style={{ top: toolbar.top, left: toolbar.left }}
        >
          <Button
            type="button"
            size="icon-xs"
            variant="ghost"
            aria-label="Bold"
            title="Bold"
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => format("bold")}
          >
            <span className="text-sm font-bold">B</span>
          </Button>
          <Button
            type="button"
            size="icon-xs"
            variant="ghost"
            aria-label="Italic"
            title="Italic"
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => format("italic")}
          >
            <span className="text-sm italic">I</span>
          </Button>
          <Button
            type="button"
            size="xs"
            variant="ghost"
            aria-label="Heading"
            title="Heading"
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => format("formatBlock", "h2")}
          >
            H2
          </Button>
          <Button
            type="button"
            size="xs"
            variant="ghost"
            aria-label="Subheading"
            title="Subheading"
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => format("formatBlock", "h3")}
          >
            H3
          </Button>
          <span className="mx-0.5 h-4 w-px bg-border" aria-hidden />
          <Button
            type="button"
            size="xs"
            variant="ghost"
            disabled={suggesting}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => void alternativesForSelection()}
          >
            <Icon
              icon={suggesting ? Loading03Icon : SparklesIcon}
              className={suggesting ? "animate-spin" : undefined}
            />
            Alternatives
          </Button>
          <Button
            type="button"
            size="xs"
            variant="ghost"
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => {
              const current = window.getSelection();
              const text = current ? current.toString().trim() : "";
              if (text) onUseContext(text);
              setToolbar(null);
            }}
          >
            <Icon icon={MagicWand01Icon} />
            Ask AI
          </Button>
        </div>
      ) : null}
    </>
  );
}

/** Convert a leading "# ", "## " or "### " into a heading as you type. */
function applyHeadingShortcut(root: HTMLElement | null) {
  if (!root) return;
  const current = window.getSelection();
  if (!current || current.rangeCount === 0) return;
  const range = current.getRangeAt(0);
  const start = range.startContainer;
  const element =
    start.nodeType === Node.ELEMENT_NODE
      ? (start as Element)
      : start.parentElement;
  const block = element?.closest("p, div, h1, h2, h3, h4, h5, h6");
  if (!block || block === root || block.hasAttribute("data-variant")) return;
  const text = block.textContent ?? "";
  const match = text.match(/^(#{1,3})\s(.*)$/);
  if (!match || block.querySelector("[data-variant]")) return;
  const heading = document.createElement(`h${match[1].length}`);
  heading.textContent = match[2];
  block.replaceWith(heading);
  const next = document.createRange();
  next.selectNodeContents(heading);
  next.collapse(false);
  current.removeAllRanges();
  current.addRange(next);
}

function activeVersion(block: DraftBlock) {
  return (
    block.versions.find(
      (version) => version.versionId === block.activeVersionId,
    ) ?? block.versions[0]
  );
}

function activeText(block: DraftBlock): string {
  return activeVersion(block)?.text ?? "";
}

function readVariantIndex(element: Element): number | null {
  const value = Number(element.getAttribute("data-variant-index"));
  return Number.isFinite(value) && value >= 0 ? value : null;
}

/** The variant wrapping a selection endpoint, if any. */
function endpointVariant(node: Node): Element | null {
  const element =
    node.nodeType === Node.ELEMENT_NODE
      ? (node as Element)
      : node.parentElement;
  return element?.closest("[data-variant]") ?? null;
}

/**
 * The alternative group the caret is sitting in or directly beside. Variants are
 * atomic (not editable inside), so the caret lands next to one rather than in it.
 */
function variantIndexAtSelection(root: HTMLElement | null): number | null {
  if (!root) return null;
  const current = window.getSelection();
  if (!current || current.rangeCount === 0) return null;
  const range = current.getRangeAt(0);
  const start = range.startContainer;
  const offset = range.startOffset;

  const element =
    start.nodeType === Node.ELEMENT_NODE
      ? (start as Element)
      : start.parentElement;
  const enclosing = element?.closest("[data-variant]");
  if (enclosing && root.contains(enclosing)) return readVariantIndex(enclosing);

  const candidates: (Node | null)[] = [];
  if (start.nodeType === Node.ELEMENT_NODE) {
    const container = start as Element;
    candidates.push(container.childNodes[offset - 1] ?? null);
    candidates.push(container.childNodes[offset] ?? null);
  } else {
    if (offset === 0) candidates.push(start.previousSibling);
    if (offset === (start as Text).length) candidates.push(start.nextSibling);
  }
  for (const candidate of candidates) {
    if (!(candidate instanceof Element)) continue;
    const found = candidate.matches("[data-variant]")
      ? candidate
      : candidate.closest("[data-variant]");
    if (found && root.contains(found)) return readVariantIndex(found);
  }
  return null;
}

"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowDown01Icon,
  Delete02Icon,
  HistoryIcon,
  Loading03Icon,
  MagicWand01Icon,
  SparklesIcon,
  TextFontIcon,
} from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  markdownToHtml,
  markdownToPlain,
  parseVariant,
  reorderVariant,
  variantSyntax,
} from "@/lib/draft-content";
import type { Draft, DraftBlock } from "@/lib/types";
import { cn } from "@/lib/utils";

const EDITOR_HEIGHT =
  "max-h-[min(78vh,44rem)] lg:h-[min(78vh,44rem)] lg:max-h-none";

interface VariantState {
  x: number;
  y: number;
  blockId: string;
  options: string[];
}

/**
 * The draft document as an Obsidian-style live preview.
 *
 * Every block renders its Markdown; the block you are editing swaps to the raw
 * Markdown in a plain editor. Selecting text raises the writing partner:
 * Rewrite/Alternatives wrap the selection in an inline `{{…}}` variant (a new
 * version of that exact span), and "Ask AI" adds it to the chat context. Variant
 * spans render with a dotted underline and open a version picker on click.
 */
export function FreeFlowEditor({
  draft,
  busyBlockId,
  onTitle,
  onEditText,
  onSplitBlock,
  onMergeBlock,
  onRemoveBlock,
  onSetVersion,
  onSuggest,
  onUseContext,
}: {
  draft: Draft;
  busyBlockId: string | null;
  onTitle: (title: string) => void;
  onEditText: (blockId: string, markdown: string) => void;
  onSplitBlock: (blockId: string, before: string, after: string) => string;
  onMergeBlock: (blockId: string) => string | null;
  onRemoveBlock: (blockId: string) => void;
  onSetVersion: (blockId: string, versionId: string) => void;
  onSuggest: (
    blockId: string,
    text: string,
    mode: "rewrite" | "alternatives",
  ) => Promise<string[]>;
  onUseContext: (text: string) => void;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [variant, setVariant] = useState<VariantState | null>(null);
  const [suggesting, setSuggesting] = useState(false);

  function handleVariantClick(event: React.MouseEvent<HTMLElement>) {
    const span = (event.target as Element).closest<HTMLElement>(
      "[data-variant]",
    );
    if (!span) {
      setVariant(null);
      return;
    }
    const data = parseVariant(span);
    if (!data) return;
    const blockId =
      span.closest<HTMLElement>("[data-block-id]")?.dataset.blockId;
    if (!blockId) return;
    event.stopPropagation();
    const rect = span.getBoundingClientRect();
    setVariant({
      x: rect.left + rect.width / 2,
      y: rect.bottom + 6,
      blockId,
      options: data.options,
    });
  }

  function pickVariant(index: number) {
    if (!variant) return;
    const block = draft.blocks.find((item) => item.blockId === variant.blockId);
    const active = block ? activeVersion(block) : undefined;
    if (block && active) {
      onEditText(
        block.blockId,
        reorderVariant(active.text, variant.options, index),
      );
    }
    setVariant(null);
  }

  return (
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
              <span className="tabular">{draft.summary.wordCount} words</span>
              <span aria-hidden>·</span>
              <span>{draft.blocks.length} blocks</span>
              <span aria-hidden>·</span>
              <span className="tabular">
                {draft.summary.versionCount} versions
              </span>
            </div>
          </div>
        </div>
      </CardHeader>

      <CardContent
        className="scroll-fade-y min-h-0 flex-1 overflow-y-auto overscroll-y-contain px-(--card-spacing) py-(--card-spacing)"
        onClick={handleVariantClick}
      >
        <div className="mx-auto max-w-[70ch] space-y-0.5 pb-16">
          {draft.blocks.map((block) => (
            <BlockView
              key={block.blockId}
              block={block}
              editing={editingId === block.blockId}
              busy={busyBlockId === block.blockId}
              suggesting={suggesting}
              onStartEditing={() => {
                setVariant(null);
                setEditingId(block.blockId);
              }}
              onStopEditing={() => setEditingId(null)}
              onEditText={onEditText}
              onSplitBlock={(before, after) => {
                const id = onSplitBlock(block.blockId, before, after);
                setEditingId(id);
              }}
              onMergeBlock={() => {
                const id = onMergeBlock(block.blockId);
                if (id) setEditingId(id);
              }}
              onRemoveBlock={() => {
                setEditingId(null);
                onRemoveBlock(block.blockId);
              }}
              onSetVersion={onSetVersion}
              onSuggest={async (text, mode) => {
                setSuggesting(true);
                try {
                  return await onSuggest(block.blockId, text, mode);
                } finally {
                  setSuggesting(false);
                }
              }}
              onUseContext={onUseContext}
            />
          ))}
          <p className="px-1 pt-2 text-xs text-muted-foreground">
            Markdown supported. Press Enter for a new paragraph, # for a
            heading.
          </p>
        </div>
      </CardContent>

      {variant ? <VariantPopover state={variant} onPick={pickVariant} /> : null}
    </Card>
  );
}

function activeVersion(block: DraftBlock) {
  return (
    block.versions.find(
      (version) => version.versionId === block.activeVersionId,
    ) ?? block.versions[0]
  );
}

function VariantPopover({
  state,
  onPick,
}: {
  state: VariantState;
  onPick: (index: number) => void;
}) {
  return (
    <div
      className="fixed z-50 w-80 -translate-x-1/2 rounded-lg border bg-popover p-1 text-popover-foreground shadow-lg"
      style={{ left: state.x, top: state.y }}
      role="menu"
      aria-label="Alternatives"
    >
      <p className="px-2 py-1 text-xs text-muted-foreground">
        {state.options.length} versions of this span
      </p>
      {state.options.map((option, index) => (
        <button
          key={index}
          type="button"
          onClick={() => onPick(index)}
          className={cn(
            "block w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted",
            index === 0 && "bg-muted font-medium",
          )}
        >
          <span className="mr-1 text-xs text-muted-foreground tabular">
            v{index + 1}
          </span>
          {option}
        </button>
      ))}
    </div>
  );
}

function BlockView({
  block,
  editing,
  busy,
  suggesting,
  onStartEditing,
  onStopEditing,
  onEditText,
  onSplitBlock,
  onMergeBlock,
  onRemoveBlock,
  onSetVersion,
  onSuggest,
  onUseContext,
}: {
  block: DraftBlock;
  editing: boolean;
  busy: boolean;
  suggesting: boolean;
  onStartEditing: () => void;
  onStopEditing: () => void;
  onEditText: (blockId: string, markdown: string) => void;
  onSplitBlock: (before: string, after: string) => void;
  onMergeBlock: () => void;
  onRemoveBlock: () => void;
  onSetVersion: (blockId: string, versionId: string) => void;
  onSuggest: (
    text: string,
    mode: "rewrite" | "alternatives",
  ) => Promise<string[]>;
  onUseContext: (text: string) => void;
}) {
  const active = activeVersion(block);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!editing) return;
    const element = textareaRef.current;
    if (!element) return;
    element.focus();
    element.setSelectionRange(element.value.length, element.value.length);
  }, [editing]);

  if (!active) return null;
  const activeIndex = block.versions.findIndex(
    (version) => version.versionId === active.versionId,
  );

  function replaceSelection(replacement: string, select?: [number, number]) {
    const element = textareaRef.current;
    if (!element) return;
    const start = element.selectionStart;
    const end = element.selectionEnd;
    const next =
      element.value.slice(0, start) + replacement + element.value.slice(end);
    onEditText(block.blockId, next);
    requestAnimationFrame(() => {
      element.focus();
      if (select) {
        element.setSelectionRange(start + select[0], start + select[1]);
      } else {
        const caret = start + replacement.length;
        element.setSelectionRange(caret, caret);
      }
    });
  }

  function selectedText(): string {
    const element = textareaRef.current;
    if (!element) return "";
    return element.value.slice(element.selectionStart, element.selectionEnd);
  }

  function wrapSelection(marker: string) {
    const selected = selectedText();
    if (!selected) return;
    replaceSelection(`${marker}${selected}${marker}`, [
      marker.length,
      marker.length + selected.length,
    ]);
  }

  function toggleHeading() {
    const element = textareaRef.current;
    if (!element) return;
    const value = element.value;
    const lineStart = value.lastIndexOf("\n", element.selectionStart - 1) + 1;
    const lineEnd = value.indexOf("\n", element.selectionStart);
    const end = lineEnd === -1 ? value.length : lineEnd;
    const line = value.slice(lineStart, end);
    const isHeading = /^#{1,3}\s/.test(line);
    const nextLine = isHeading ? line.replace(/^#{1,3}\s/, "") : `## ${line}`;
    onEditText(
      block.blockId,
      value.slice(0, lineStart) + nextLine + value.slice(end),
    );
    requestAnimationFrame(() => {
      element.focus();
      element.setSelectionRange(
        lineStart + nextLine.length,
        lineStart + nextLine.length,
      );
    });
  }

  async function runSuggest(mode: "rewrite" | "alternatives") {
    const selected = selectedText();
    if (!selected) return;
    const suggestions = await onSuggest(selected, mode);
    if (suggestions.length === 0) return;
    const options =
      mode === "rewrite"
        ? [suggestions[0], selected]
        : [selected, ...suggestions];
    replaceSelection(variantSyntax(options));
  }

  return (
    <div className="group/block relative" data-block-id={block.blockId}>
      {editing ? (
        <div className="rounded-lg border border-signal/40 bg-background p-1.5 shadow-sm">
          <div className="mb-1 flex flex-wrap items-center gap-0.5 border-b pb-1">
            <Button
              type="button"
              size="icon-xs"
              variant="ghost"
              aria-label="Bold"
              title="Bold"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => wrapSelection("**")}
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
              onClick={() => wrapSelection("*")}
            >
              <span className="text-sm italic">I</span>
            </Button>
            <Button
              type="button"
              size="icon-xs"
              variant="ghost"
              aria-label="Heading"
              title="Heading"
              onMouseDown={(event) => event.preventDefault()}
              onClick={toggleHeading}
            >
              <Icon icon={TextFontIcon} />
            </Button>
            <span className="mx-0.5 h-4 w-px bg-border" aria-hidden />
            <Button
              type="button"
              size="xs"
              variant="ghost"
              onMouseDown={(event) => event.preventDefault()}
              disabled={suggesting}
              onClick={() => void runSuggest("rewrite")}
            >
              <Icon
                icon={suggesting ? Loading03Icon : MagicWand01Icon}
                className={suggesting ? "animate-spin" : undefined}
              />
              Rewrite
            </Button>
            <Button
              type="button"
              size="xs"
              variant="ghost"
              onMouseDown={(event) => event.preventDefault()}
              disabled={suggesting}
              onClick={() => void runSuggest("alternatives")}
            >
              <Icon icon={SparklesIcon} />
              Alternatives
            </Button>
            <Button
              type="button"
              size="xs"
              variant="ghost"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => onUseContext(selectedText())}
            >
              Ask AI
            </Button>
          </div>
          <Textarea
            ref={textareaRef}
            value={active.text}
            onChange={(event) => onEditText(block.blockId, event.target.value)}
            onKeyDown={(event) => {
              const element = event.currentTarget;
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                onSplitBlock(
                  element.value.slice(0, element.selectionStart),
                  element.value.slice(element.selectionStart),
                );
              } else if (
                event.key === "Backspace" &&
                element.selectionStart === 0 &&
                element.selectionEnd === 0
              ) {
                event.preventDefault();
                onMergeBlock();
              } else if (event.key === "Escape") {
                onStopEditing();
              }
            }}
            onBlur={onStopEditing}
            rows={1}
            aria-label="Edit block"
            className="field-sizing-content min-h-7 resize-none border-0 bg-transparent px-1 py-0.5 text-sm leading-relaxed shadow-none focus-visible:ring-0 dark:bg-transparent"
          />
        </div>
      ) : (
        <div
          role="button"
          tabIndex={0}
          aria-label="Edit block"
          onClick={(event) => {
            // Clicking an inline variant opens its versions, not the editor.
            if ((event.target as Element).closest("[data-variant]")) return;
            onStartEditing();
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              onStartEditing();
            }
          }}
          className={cn(
            "prose-draft min-h-7 cursor-text rounded-md px-1 py-1 text-sm leading-relaxed outline-none hover:bg-muted/30 focus-visible:ring-3 focus-visible:ring-ring/50",
            busy && "opacity-60",
          )}
          dangerouslySetInnerHTML={{ __html: markdownToHtml(active.text) }}
        />
      )}

      {!editing ? (
        <div className="absolute -top-1 right-0 flex items-center gap-0.5 opacity-0 transition-opacity group-hover/block:opacity-100 focus-within:opacity-100">
          {busy ? (
            <span className="text-xs text-signal">Rewriting…</span>
          ) : null}
          <Button
            type="button"
            size="icon-xs"
            variant="ghost"
            aria-label="Delete block"
            title="Delete block"
            onClick={onRemoveBlock}
          >
            <Icon icon={Delete02Icon} />
          </Button>
          {block.versions.length > 1 ? (
            <DropdownMenu>
              <DropdownMenuTrigger
                render={<Button type="button" size="xs" variant="ghost" />}
              >
                <Icon icon={HistoryIcon} className="size-3.5" />v
                {activeIndex + 1}
                <Icon icon={ArrowDown01Icon} className="size-3" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-72">
                <DropdownMenuRadioGroup
                  value={active.versionId}
                  onValueChange={(value) =>
                    onSetVersion(block.blockId, String(value))
                  }
                >
                  {block.versions.map((version, index) => (
                    <DropdownMenuRadioItem
                      key={version.versionId}
                      value={version.versionId}
                      className="items-start"
                    >
                      <div className="min-w-0 space-y-0.5 whitespace-normal">
                        <span className="text-xs text-muted-foreground">
                          v{index + 1}
                          {version.label ? ` · ${version.label}` : ""}
                          {version.origin === "user" ? " · yours" : ""}
                        </span>
                        <span className="line-clamp-2 block text-xs">
                          {markdownToPlain(version.text)}
                        </span>
                      </div>
                    </DropdownMenuRadioItem>
                  ))}
                </DropdownMenuRadioGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

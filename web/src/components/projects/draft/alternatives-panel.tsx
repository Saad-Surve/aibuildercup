"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowDown01Icon,
  ArrowUp01Icon,
  Cancel01Icon,
  CheckmarkCircle02Icon,
  Delete02Icon,
  Loading03Icon,
  MagicWand01Icon,
  PencilEdit02Icon,
  PlusSignIcon,
} from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { AltOption } from "@/lib/draft-content";
import { cn } from "@/lib/utils";

const ORIGIN_LABEL: Record<AltOption["origin"], string> = {
  original: "Original",
  user: "You",
  ai: "AI",
};

/**
 * Alternatives for the selected span.
 *
 * Rendered inside the right-hand drawer. The original is pinned first and
 * read-only; every other version can be edited, reordered, or deleted. Cycling
 * with Tab is the primary interaction, so this doubles as a map of where you
 * are.
 */
export function AlternativesPanel({
  options,
  activeIndex,
  suggesting,
  onSelect,
  onAdd,
  onUpdate,
  onDelete,
  onMove,
  onSuggest,
  onClose,
}: {
  options: AltOption[];
  activeIndex: number;
  suggesting: boolean;
  onSelect: (optionIndex: number) => void;
  onAdd: (text: string) => void;
  onUpdate: (optionIndex: number, text: string) => void;
  onDelete: (optionIndex: number) => void;
  onMove: (from: number, to: number) => void;
  onSuggest: () => void;
  onClose: () => void;
}) {
  const [draft, setDraft] = useState("");
  const [editing, setEditing] = useState<number | null>(null);

  const originalIndex = options.findIndex(
    (option) => option.origin === "original",
  );
  const pinned = originalIndex >= 0 ? originalIndex : 0;
  const alternativeIndices = options
    .map((_, index) => index)
    .filter((index) => index !== pinned);

  function moveAlternative(position: number, direction: -1 | 1) {
    const target = position + direction;
    if (target < 0 || target >= alternativeIndices.length) return;
    onMove(alternativeIndices[position], alternativeIndices[target]);
  }

  function submitDraft() {
    const text = draft.trim();
    if (!text) return;
    onAdd(text);
    setDraft("");
  }

  return (
    <aside
      className="flex h-full min-h-0 w-full flex-col"
      aria-label="Alternatives"
    >
      <div className="flex items-center gap-1 border-b px-3 py-2">
        <span className="font-heading text-sm font-medium">Alternatives</span>
        <Badge variant="secondary" className="tabular">
          {options.length}
        </Badge>
        <Button
          type="button"
          size="icon-xs"
          variant="ghost"
          className="ml-auto"
          aria-label="Close alternatives"
          title="Close"
          onClick={onClose}
        >
          <Icon icon={Cancel01Icon} />
        </Button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
        <p className="pb-2 text-xs text-muted-foreground">
          Press Tab (or Shift+Tab) to cycle the version in place.
        </p>

        <OptionRow
          option={options[pinned]}
          active={pinned === activeIndex}
          pinned
          onSelect={() => onSelect(pinned)}
          onUpdate={() => undefined}
          onDelete={() => undefined}
          onMove={() => undefined}
          editing={false}
          onStartEdit={() => undefined}
          onCloseEdit={() => undefined}
          hideControls
        />

        <div className="space-y-1 pt-1">
          {alternativeIndices.map((optionIndex, position) => (
            <OptionRow
              key={`${optionIndex}-${options[optionIndex].origin}`}
              option={options[optionIndex]}
              active={optionIndex === activeIndex}
              pinned={false}
              onSelect={() => onSelect(optionIndex)}
              onUpdate={(text) => onUpdate(optionIndex, text)}
              onDelete={() => onDelete(optionIndex)}
              onMove={(direction) => moveAlternative(position, direction)}
              editing={editing === optionIndex}
              onStartEdit={() => setEditing(optionIndex)}
              onCloseEdit={() =>
                setEditing((current) =>
                  current === optionIndex ? null : current,
                )
              }
              canMoveUp={position > 0}
              canMoveDown={position < alternativeIndices.length - 1}
            />
          ))}
        </div>

        <div className="flex items-center gap-1 pt-2">
          <Input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                submitDraft();
              }
            }}
            placeholder="Add your own version"
            aria-label="Add an alternative"
            className="h-7 text-xs"
          />
          <Button
            type="button"
            size="icon-xs"
            variant="secondary"
            aria-label="Add alternative"
            title="Add alternative"
            disabled={!draft.trim()}
            onClick={submitDraft}
          >
            <Icon icon={PlusSignIcon} />
          </Button>
        </div>
      </div>

      <div className="border-t px-3 py-2">
        <Button
          type="button"
          size="sm"
          variant="secondary"
          className="w-full"
          disabled={suggesting}
          onClick={onSuggest}
        >
          <Icon
            icon={suggesting ? Loading03Icon : MagicWand01Icon}
            className={suggesting ? "animate-spin" : undefined}
          />
          {suggesting ? "Thinking…" : "AI suggestions"}
        </Button>
      </div>
    </aside>
  );
}

function OptionRow({
  option,
  active,
  pinned,
  editing,
  hideControls = false,
  canMoveUp = false,
  canMoveDown = false,
  onSelect,
  onUpdate,
  onDelete,
  onMove,
  onStartEdit,
  onCloseEdit,
}: {
  option: AltOption;
  active: boolean;
  pinned: boolean;
  editing: boolean;
  hideControls?: boolean;
  canMoveUp?: boolean;
  canMoveDown?: boolean;
  onSelect: () => void;
  onUpdate: (text: string) => void;
  onDelete: () => void;
  onMove: (direction: -1 | 1) => void;
  onStartEdit: () => void;
  onCloseEdit: () => void;
}) {
  const editRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (editing) editRef.current?.focus();
  }, [editing]);

  function commit() {
    const element = editRef.current;
    if (!element) return;
    const text = element.value.trim();
    if (text && text !== option.text) onUpdate(text);
    else if (!text) onDelete();
    onCloseEdit();
  }

  return (
    <div
      className={cn(
        "group/alt rounded-md border px-2 py-1.5 transition-colors",
        active
          ? "border-signal/50 bg-signal/5"
          : "border-transparent hover:border-border hover:bg-muted/40",
      )}
    >
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={onSelect}
          className="flex min-w-0 flex-1 items-center gap-1.5 text-left"
          aria-label={`Use ${ORIGIN_LABEL[option.origin]} version`}
        >
          {active ? (
            <Icon icon={CheckmarkCircle02Icon} className="size-3.5 shrink-0 text-signal" />
          ) : (
            <span aria-hidden className="size-3.5 shrink-0" />
          )}
          <Badge
            variant="outline"
            className={cn(
              "shrink-0 text-[10px]",
              option.origin === "ai" &&
                "border-signal/40 bg-signal/10 text-signal",
            )}
          >
            {ORIGIN_LABEL[option.origin]}
          </Badge>
          <span className="min-w-0 flex-1 text-xs whitespace-normal">
            {option.text}
          </span>
        </button>
        {!pinned && !hideControls ? (
          <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover/alt:opacity-100 focus-within:opacity-100">
            <Button
              type="button"
              size="icon-xs"
              variant="ghost"
              aria-label="Move up"
              disabled={!canMoveUp}
              onClick={() => onMove(-1)}
            >
              <Icon icon={ArrowUp01Icon} />
            </Button>
            <Button
              type="button"
              size="icon-xs"
              variant="ghost"
              aria-label="Move down"
              disabled={!canMoveDown}
              onClick={() => onMove(1)}
            >
              <Icon icon={ArrowDown01Icon} />
            </Button>
            <Button
              type="button"
              size="icon-xs"
              variant="ghost"
              aria-label={editing ? "Done editing" : "Edit alternative"}
              onClick={() => (editing ? commit() : onStartEdit())}
            >
              <Icon icon={editing ? CheckmarkCircle02Icon : PencilEdit02Icon} />
            </Button>
            <Button
              type="button"
              size="icon-xs"
              variant="ghost"
              aria-label="Delete alternative"
              onClick={onDelete}
            >
              <Icon icon={Delete02Icon} />
            </Button>
          </div>
        ) : null}
      </div>
      {!pinned ? (
        editing ? (
          <Textarea
            ref={editRef}
            key={option.text}
            defaultValue={option.text}
            onBlur={commit}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                commit();
              }
            }}
            rows={2}
            aria-label="Alternative text"
            className="mt-1.5 field-sizing-content min-h-7 resize-none text-xs"
          />
        ) : null
      ) : null}
    </div>
  );
}

"use client";

import { useState } from "react";
import {
  ArrowDown01Icon,
  Delete02Icon,
  Download01Icon,
  FileExportIcon,
  Heading01Icon,
  MagicWand01Icon,
  PlusSignIcon,
  SparklesIcon,
  TextAlignLeftIcon,
  VideoReplayIcon,
} from "@hugeicons/core-free-icons";
import { toast } from "sonner";

import { Icon } from "@/components/common/icon";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  downloadDraft,
  DRAFT_EXPORT_FORMATS,
  type DraftExportFormat,
} from "@/lib/draft-export";
import type { Draft, DraftBlock, DraftBlockType } from "@/lib/types";

const BLOCK_ICON: Record<DraftBlockType, typeof Heading01Icon> = {
  heading: Heading01Icon,
  paragraph: TextAlignLeftIcon,
  scene: VideoReplayIcon,
};

const BLOCK_LABEL: Record<DraftBlockType, string> = {
  heading: "Heading",
  paragraph: "Paragraph",
  scene: "Scene",
};

export function DraftDocument({
  draft,
  busyBlockId,
  onTitle,
  onEditText,
  onSetVersion,
  onAddBlock,
  onRemoveBlock,
  onRewrite,
  onAlternatives,
  onVaryPhrase,
}: {
  draft: Draft;
  busyBlockId: string | null;
  onTitle: (title: string) => void;
  onEditText: (blockId: string, text: string) => void;
  onSetVersion: (blockId: string, versionId: string) => void;
  onAddBlock: (type: DraftBlockType) => void;
  onRemoveBlock: (blockId: string) => void;
  onRewrite: (blockId: string) => void;
  onAlternatives: (blockId: string) => void;
  onVaryPhrase: (blockId: string, phrase: string) => void;
}) {
  const [selection, setSelection] = useState<{
    blockId: string;
    phrase: string;
  } | null>(null);
  function handleExport(format: DraftExportFormat) {
    downloadDraft(draft, format, "draft");
    const label = DRAFT_EXPORT_FORMATS.find((item) => item.value === format);
    toast.success(`Exported ${label?.label ?? format}`);
  }

  return (
    <Card className="gap-0 py-0">
      <CardHeader className="gap-3 border-b py-(--card-spacing)">
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
          <DropdownMenu>
            <DropdownMenuTrigger
              render={<Button type="button" size="sm" variant="outline" />}
            >
              <Icon icon={FileExportIcon} />
              Export
              <Icon icon={ArrowDown01Icon} className="text-muted-foreground" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              {DRAFT_EXPORT_FORMATS.map((option) => (
                <DropdownMenuItem
                  key={option.value}
                  onClick={() => handleExport(option.value)}
                >
                  <Icon icon={Download01Icon} />
                  {option.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <CardDescription>
          Every edit forks a version. Switch between them per block — nothing is
          overwritten.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-1 px-0 py-(--card-spacing)">
        {draft.blocks.map((block) => (
          <DraftBlockRow
            key={block.blockId}
            block={block}
            busy={busyBlockId === block.blockId}
            selectedPhrase={
              selection?.blockId === block.blockId ? selection.phrase : null
            }
            onSelectPhrase={(phrase) =>
              setSelection(phrase ? { blockId: block.blockId, phrase } : null)
            }
            onVaryPhrase={(phrase) => {
              setSelection(null);
              onVaryPhrase(block.blockId, phrase);
            }}
            onEditText={onEditText}
            onSetVersion={onSetVersion}
            onRemove={onRemoveBlock}
            onRewrite={onRewrite}
            onAlternatives={onAlternatives}
          />
        ))}

        <div className="flex flex-wrap items-center gap-2 px-(--card-spacing) pt-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => onAddBlock("paragraph")}
          >
            <Icon icon={PlusSignIcon} />
            Add paragraph
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => onAddBlock("heading")}
          >
            <Icon icon={Heading01Icon} />
            Heading
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => onAddBlock("scene")}
          >
            <Icon icon={VideoReplayIcon} />
            Scene
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function DraftBlockRow({
  block,
  busy,
  selectedPhrase,
  onSelectPhrase,
  onVaryPhrase,
  onEditText,
  onSetVersion,
  onRemove,
  onRewrite,
  onAlternatives,
}: {
  block: DraftBlock;
  busy: boolean;
  selectedPhrase: string | null;
  onSelectPhrase: (phrase: string | null) => void;
  onVaryPhrase: (phrase: string) => void;
  onEditText: (blockId: string, text: string) => void;
  onSetVersion: (blockId: string, versionId: string) => void;
  onRemove: (blockId: string) => void;
  onRewrite: (blockId: string) => void;
  onAlternatives: (blockId: string) => void;
}) {
  const active =
    block.versions.find(
      (version) => version.versionId === block.activeVersionId,
    ) ?? block.versions[0];
  const activeIndex = block.versions.findIndex(
    (version) => version.versionId === active?.versionId,
  );

  return (
    <div className="group/block px-(--card-spacing) py-2 transition-colors hover:bg-muted/40">
      <div className="flex items-center gap-2">
        <span className="flex items-center gap-1 text-xs text-muted-foreground/70">
          <Icon icon={BLOCK_ICON[block.type]} className="size-3.5" />
          {BLOCK_LABEL[block.type]}
        </span>

        <DropdownMenu>
          <DropdownMenuTrigger
            render={<Button type="button" size="xs" variant="ghost" />}
          >
            v{activeIndex + 1}
            {active?.label ? ` · ${active.label}` : ""}
            <Icon icon={ArrowDown01Icon} className="size-3" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-72">
            <DropdownMenuRadioGroup
              value={active?.versionId}
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
                      {version.text}
                    </span>
                  </div>
                </DropdownMenuRadioItem>
              ))}
            </DropdownMenuRadioGroup>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => onRewrite(block.blockId)}>
              <Icon icon={MagicWand01Icon} />
              Rewrite this
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onAlternatives(block.blockId)}>
              <Icon icon={SparklesIcon} />
              Three alternatives
            </DropdownMenuItem>
            {block.versions.length > 1 ? (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  variant="destructive"
                  onClick={() => onRemove(block.blockId)}
                >
                  <Icon icon={Delete02Icon} />
                  Delete block
                </DropdownMenuItem>
              </>
            ) : null}
          </DropdownMenuContent>
        </DropdownMenu>

        {selectedPhrase ? (
          <Button
            type="button"
            size="xs"
            variant="secondary"
            className="ml-auto max-w-[16rem]"
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => onVaryPhrase(selectedPhrase)}
          >
            <Icon icon={SparklesIcon} />
            <span className="truncate">Vary “{selectedPhrase}”</span>
          </Button>
        ) : busy ? (
          <span className="ml-auto text-xs text-signal">Rewriting…</span>
        ) : (
          <div className="ml-auto flex items-center gap-0.5 opacity-0 transition-opacity group-hover/block:opacity-100 focus-within:opacity-100">
            <Button
              type="button"
              size="icon-xs"
              variant="ghost"
              aria-label="Rewrite this block"
              onClick={() => onRewrite(block.blockId)}
            >
              <Icon icon={MagicWand01Icon} />
            </Button>
            <Button
              type="button"
              size="icon-xs"
              variant="ghost"
              aria-label="Show alternatives"
              onClick={() => onAlternatives(block.blockId)}
            >
              <Icon icon={SparklesIcon} />
            </Button>
            <Button
              type="button"
              size="icon-xs"
              variant="ghost"
              aria-label="Delete block"
              onClick={() => onRemove(block.blockId)}
            >
              <Icon icon={Delete02Icon} />
            </Button>
          </div>
        )}
      </div>

      <Textarea
        value={active?.text ?? ""}
        onChange={(event) => {
          onSelectPhrase(null);
          onEditText(block.blockId, event.target.value);
        }}
        onSelect={(event) => {
          const target = event.currentTarget;
          const phrase = target.value
            .slice(target.selectionStart, target.selectionEnd)
            .trim();
          onSelectPhrase(phrase.length > 0 ? phrase : null);
        }}
        placeholder={
          block.type === "heading" ? "Section title" : "Start writing…"
        }
        className={`mt-1 field-sizing-content min-h-8 resize-none border-0 bg-transparent px-0 py-0 shadow-none focus-visible:ring-0 dark:bg-transparent ${
          block.type === "heading"
            ? "font-heading text-base font-medium"
            : "text-sm leading-relaxed"
        }`}
      />
    </div>
  );
}

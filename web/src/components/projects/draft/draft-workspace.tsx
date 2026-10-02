"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PencilEdit02Icon, SparklesIcon } from "@hugeicons/core-free-icons";
import { toast } from "sonner";

import { Icon } from "@/components/common/icon";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { DraftBriefDialog } from "@/components/projects/draft/draft-brief-dialog";
import { DraftChat } from "@/components/projects/draft/draft-chat";
import { FreeFlowEditor } from "@/components/projects/draft/free-flow-editor";
import { ApiError } from "@/lib/api-client";
import {
  assistDraft,
  generateDraft,
  getDraft,
  saveDraft,
  suggestDraft,
} from "@/lib/drafts";
import type { Draft, DraftBlock, DraftBrief } from "@/lib/types";
import { WORKSPACE_PANE_STACK_SPACER } from "@/lib/workspace";

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID().replace(/-/g, "").slice(0, 12);
  }
  return Math.random().toString(36).slice(2, 14);
}

function describe(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}

function activeBlockText(block: DraftBlock): string {
  return (
    block.versions.find(
      (version) => version.versionId === block.activeVersionId,
    )?.text ??
    block.versions[0]?.text ??
    ""
  );
}

/**
 * Update a block's active version, forking an assistant version into a user
 * version on first edit so the model's wording is kept as a sibling.
 */
function forkBlockHtml(block: DraftBlock, html: string): DraftBlock {
  const active = block.versions.find(
    (version) => version.versionId === block.activeVersionId,
  );
  if (active?.origin === "user") {
    return {
      ...block,
      versions: block.versions.map((version) =>
        version.versionId === active.versionId
          ? { ...version, text: html }
          : version,
      ),
    };
  }
  const version = {
    versionId: newId(),
    text: html,
    label: "My edit",
    origin: "user" as const,
    createdAt: new Date().toISOString(),
  };
  return {
    ...block,
    versions: [...block.versions, version],
    activeVersionId: version.versionId,
  };
}

function makeBlock(
  html: string,
  type: DraftBlock["type"] = "paragraph",
): DraftBlock {
  const version = {
    versionId: newId(),
    text: html,
    label: "My edit",
    origin: "user" as const,
    createdAt: new Date().toISOString(),
  };
  return {
    blockId: newId(),
    type,
    versions: [version],
    activeVersionId: version.versionId,
  };
}

/**
 * The draft studio: a free-flowing rich document on the left, a writing partner
 * on the right. The React Query cache is the single source of truth — edits
 * write to it optimistically and a debounced save persists them, while assistant
 * replies replace it wholesale. Every block keeps its own version history and
 * inline alternatives live inside the text, so nothing is ever lost.
 */
export function DraftWorkspace({
  project,
}: {
  project: import("@/lib/types").Project;
}) {
  const projectId = project.projectId;
  const queryClient = useQueryClient();
  const [briefOpen, setBriefOpen] = useState(false);
  const [busyBlockId, setBusyBlockId] = useState<string | null>(null);
  const [contextText, setContextText] = useState("");
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const autoRan = useRef(false);

  const draftQuery = useQuery({
    queryKey: ["draft", projectId],
    queryFn: () => getDraft(projectId),
    retry: false,
  });
  const draft = draftQuery.data;

  const { mutate: saveBlock, mutateAsync: saveBlockAsync } = useMutation({
    mutationFn: (input: { title?: string; blocks: DraftBlock[] }) =>
      saveDraft(projectId, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (error) =>
      toast.error(describe(error, "Could not save the draft.")),
  });
  const saveRef = useRef(saveBlock);
  useEffect(() => {
    saveRef.current = saveBlock;
  }, [saveBlock]);

  const generateMutation = useMutation({
    mutationFn: (brief: Partial<DraftBrief> | undefined) =>
      generateDraft(projectId, brief),
    onSuccess: (next) => {
      queryClient.setQueryData(["draft", projectId], next);
      setBriefOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (error) =>
      toast.error(describe(error, "Could not generate the draft.")),
  });

  const assistMutation = useMutation({
    mutationFn: (input: {
      message: string;
      blockId?: string | null;
      mode?: string;
    }) => assistDraft(projectId, input),
    onSuccess: (next) => {
      queryClient.setQueryData(["draft", projectId], next);
      setBusyBlockId(null);
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (error) => {
      setBusyBlockId(null);
      toast.error(describe(error, "The writing partner could not respond."));
    },
  });

  const scheduleSave = useCallback(() => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      const current = queryClient.getQueryData<Draft>(["draft", projectId]);
      if (!current) return;
      saveRef.current({ title: current.title, blocks: current.blocks });
    }, 900);
  }, [projectId, queryClient]);

  const mutateDraft = useCallback(
    (updater: (draft: Draft) => Draft) => {
      queryClient.setQueryData<Draft>(["draft", projectId], (previous) =>
        previous ? updater(previous) : previous,
      );
      scheduleSave();
    },
    [projectId, queryClient, scheduleSave],
  );

  const flushSave = useCallback(async () => {
    if (saveTimer.current) {
      clearTimeout(saveTimer.current);
      saveTimer.current = null;
    }
    const current = queryClient.getQueryData<Draft>(["draft", projectId]);
    if (!current) return;
    await saveBlockAsync({
      title: current.title,
      blocks: current.blocks,
    });
  }, [projectId, queryClient, saveBlockAsync]);

  // Generate the first draft automatically when a project opens empty with a
  // brief already captured at creation.
  const runGenerate = generateMutation.mutate;
  useEffect(() => {
    if (autoRan.current || !draft) return;
    if (draft.status !== "empty" || draft.blocks.length > 0) {
      autoRan.current = true;
      return;
    }
    if (!draft.brief.topic.trim()) return;
    autoRan.current = true;
    runGenerate(undefined);
  }, [draft, runGenerate]);

  function editBlockText(blockId: string, markdown: string) {
    mutateDraft((current) => ({
      ...current,
      blocks: current.blocks.map((block) =>
        block.blockId === blockId ? forkBlockHtml(block, markdown) : block,
      ),
    }));
  }

  function splitBlock(blockId: string, before: string, after: string): string {
    const newBlock = makeBlock(after);
    mutateDraft((current) => {
      const index = current.blocks.findIndex(
        (block) => block.blockId === blockId,
      );
      if (index < 0) return current;
      const blocks = [...current.blocks];
      blocks.splice(
        index,
        1,
        forkBlockHtml(current.blocks[index], before),
        newBlock,
      );
      return { ...current, blocks };
    });
    void flushSave();
    return newBlock.blockId;
  }

  function mergeBlock(blockId: string): string | null {
    const cached = queryClient.getQueryData<Draft>(["draft", projectId]);
    const index =
      cached?.blocks.findIndex((block) => block.blockId === blockId) ?? -1;
    if (!cached || index <= 0) return null;
    const previousId = cached.blocks[index - 1].blockId;
    mutateDraft((current) => {
      const at = current.blocks.findIndex((block) => block.blockId === blockId);
      if (at <= 0) return current;
      const previous = current.blocks[at - 1];
      const blocks = [...current.blocks];
      blocks.splice(
        at - 1,
        2,
        forkBlockHtml(
          previous,
          activeBlockText(previous) + activeBlockText(current.blocks[at]),
        ),
      );
      return { ...current, blocks };
    });
    void flushSave();
    return previousId;
  }

  function setActiveVersion(blockId: string, versionId: string) {
    mutateDraft((current) => ({
      ...current,
      blocks: current.blocks.map((block) =>
        block.blockId === blockId
          ? { ...block, activeVersionId: versionId }
          : block,
      ),
    }));
    void flushSave();
  }

  function removeBlock(blockId: string) {
    mutateDraft((current) => ({
      ...current,
      blocks: current.blocks.filter((block) => block.blockId !== blockId),
    }));
    void flushSave();
  }

  async function suggest(
    blockId: string,
    text: string,
    mode: "rewrite" | "alternatives",
  ): Promise<string[]> {
    const block = draft?.blocks.find((item) => item.blockId === blockId);
    const context = block ? activeBlockText(block) : "";
    try {
      const result = await suggestDraft(projectId, {
        text,
        context,
        mode,
        count: mode === "alternatives" ? 3 : 1,
      });
      if (result.suggestions.length === 0) {
        toast.error("The writing partner had no suggestions. Try again.");
      }
      return result.suggestions;
    } catch (error) {
      toast.error(describe(error, "Could not reach the writing partner."));
      return [];
    }
  }

  async function runAssist(input: {
    message: string;
    blockId?: string | null;
    mode?: string;
    busy?: string | null;
  }) {
    setBusyBlockId(input.busy ?? null);
    // Show the creator's message immediately; the server echoes it back with the
    // reply and replaces this optimistic copy.
    queryClient.setQueryData<Draft>(["draft", projectId], (previous) =>
      previous
        ? {
            ...previous,
            messages: [
              ...previous.messages,
              {
                messageId: `local-${newId()}`,
                role: "user" as const,
                content: input.message,
                createdAt: new Date().toISOString(),
              },
            ],
          }
        : previous,
    );
    await flushSave();
    assistMutation.mutate({
      message: input.message,
      blockId: input.blockId ?? null,
      mode: input.mode ?? "chat",
    });
  }

  function regenerate(brief: DraftBrief) {
    void (async () => {
      await flushSave();
      generateMutation.mutate(brief);
    })();
  }

  if (draftQuery.isLoading) {
    return (
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Skeleton className="h-[70vh] w-full" />
        <Skeleton className="h-[70vh] w-full" />
      </div>
    );
  }

  if (!draft) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Draft unavailable</CardTitle>
          <CardDescription>
            {draftQuery.error
              ? describe(draftQuery.error, "Could not load the draft.")
              : "Could not load the draft."}
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const generating =
    generateMutation.isPending || draft.status === "generating";
  const empty = draft.blocks.length === 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <Icon icon={SparklesIcon} className="size-4 text-signal" />
          {draft.brief.topic || "No brief yet"}
        </span>
        {draft.brief.audience ? <span>· {draft.brief.audience}</span> : null}
        {draft.brief.tone ? <span>· {draft.brief.tone}</span> : null}
        <Button
          type="button"
          size="xs"
          variant="ghost"
          className="ml-auto"
          onClick={() => setBriefOpen(true)}
        >
          <Icon icon={PencilEdit02Icon} />
          Edit brief
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] lg:items-start">
        {generating ? (
          <Card className="lg:snap-start lg:snap-always lg:scroll-mt-20">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Icon
                  icon={SparklesIcon}
                  className="animate-pulse text-signal"
                />
                Writing your first draft…
              </CardTitle>
              <CardDescription>
                Building the structure, hook, and body from your brief.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-4 w-2/3" />
            </CardContent>
          </Card>
        ) : empty ? (
          <Card className="lg:snap-start lg:snap-always lg:scroll-mt-20">
            <CardHeader>
              <CardTitle>Start your draft</CardTitle>
              <CardDescription>
                Give the writing partner a brief and it will write the first
                version for you to edit.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button type="button" onClick={() => setBriefOpen(true)}>
                <Icon icon={SparklesIcon} />
                Write a brief
              </Button>
            </CardContent>
          </Card>
        ) : (
          <FreeFlowEditor
            draft={draft}
            busyBlockId={busyBlockId}
            onTitle={(title) =>
              mutateDraft((current) => ({ ...current, title }))
            }
            onEditText={editBlockText}
            onSplitBlock={splitBlock}
            onMergeBlock={mergeBlock}
            onRemoveBlock={removeBlock}
            onSetVersion={setActiveVersion}
            onSuggest={suggest}
            onUseContext={(text) => {
              setContextText(text);
              toast.success("Added to the chat context");
            }}
          />
        )}
        <DraftChat
          messages={draft.messages}
          pending={assistMutation.isPending}
          contextText={contextText}
          onClearContext={() => setContextText("")}
          hasContent={!empty}
          onSend={(message) => {
            const trimmed = contextText.trim();
            const full = trimmed
              ? `Context selected from the draft: "${trimmed}"\n\nRequest: ${message}`
              : message;
            setContextText("");
            void runAssist({ message: full });
          }}
        />
      </div>
      <div aria-hidden className={WORKSPACE_PANE_STACK_SPACER} />

      <DraftBriefDialog
        key={briefOpen ? "open" : "closed"}
        open={briefOpen}
        onOpenChange={setBriefOpen}
        initial={draft.brief}
        pending={generating}
        onSubmit={regenerate}
        title={empty ? "Write a brief" : "Edit brief & regenerate"}
      />
    </div>
  );
}

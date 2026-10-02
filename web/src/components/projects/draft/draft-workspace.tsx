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
import { DraftDocument } from "@/components/projects/draft/draft-document";
import { ApiError } from "@/lib/api-client";
import { assistDraft, generateDraft, getDraft, saveDraft } from "@/lib/drafts";
import type {
  Draft,
  DraftBlock,
  DraftBlockType,
  DraftBrief,
} from "@/lib/types";

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

/**
 * The draft studio: a versioned document on the left, a writing partner on the
 * right. The React Query cache is the single source of truth — edits write to
 * it optimistically and a debounced save persists them, while assistant replies
 * replace it wholesale. Every block keeps its own version history, so nothing
 * the creator or the model wrote is ever lost.
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

  function editBlockText(blockId: string, text: string) {
    mutateDraft((current) => ({
      ...current,
      blocks: current.blocks.map((block) => {
        if (block.blockId !== blockId) return block;
        const active = block.versions.find(
          (version) => version.versionId === block.activeVersionId,
        );
        if (active?.origin === "user") {
          return {
            ...block,
            versions: block.versions.map((version) =>
              version.versionId === active.versionId
                ? { ...version, text }
                : version,
            ),
          };
        }
        // The first keystroke on an assistant version forks it into a user
        // version, so the model's wording is preserved as a sibling.
        const version = {
          versionId: newId(),
          text,
          label: "My edit",
          origin: "user" as const,
          createdAt: new Date().toISOString(),
        };
        return {
          ...block,
          versions: [...block.versions, version],
          activeVersionId: version.versionId,
        };
      }),
    }));
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

  function addBlock(type: DraftBlockType) {
    const version = {
      versionId: newId(),
      text: "",
      label: "My edit",
      origin: "user" as const,
      createdAt: new Date().toISOString(),
    };
    const block: DraftBlock = {
      blockId: newId(),
      type,
      versions: [version],
      activeVersionId: version.versionId,
    };
    mutateDraft((current) => ({
      ...current,
      blocks: [...current.blocks, block],
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

  async function runAssist(input: {
    message: string;
    blockId?: string | null;
    mode?: string;
    busy?: string | null;
  }) {
    setBusyBlockId(input.busy ?? null);
    await flushSave();
    assistMutation.mutate({
      message: input.message,
      blockId: input.blockId ?? null,
      mode: input.mode ?? "chat",
    });
  }

  function rewriteBlock(blockId: string) {
    void runAssist({
      message: "Rewrite this block to be sharper and more specific.",
      blockId,
      mode: "rewrite",
      busy: blockId,
    });
  }

  function alternativesFor(blockId: string) {
    void runAssist({
      message: "Give me three distinct alternatives for this block.",
      blockId,
      mode: "alternatives",
      busy: blockId,
    });
  }

  function varyPhrase(blockId: string, phrase: string) {
    void runAssist({
      message: `Rewrite this block, keeping everything else identical, but replace the phrase "${phrase}" with a sharper, more specific alternative.`,
      blockId,
      mode: "rewrite",
      busy: blockId,
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

      {generating ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Icon icon={SparklesIcon} className="animate-pulse text-signal" />
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
        <Card>
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
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] lg:items-start">
          <DraftDocument
            draft={draft}
            busyBlockId={busyBlockId}
            onTitle={(title) =>
              mutateDraft((current) => ({ ...current, title }))
            }
            onEditText={editBlockText}
            onSetVersion={setActiveVersion}
            onAddBlock={addBlock}
            onRemoveBlock={removeBlock}
            onRewrite={rewriteBlock}
            onAlternatives={alternativesFor}
            onVaryPhrase={varyPhrase}
          />
          <DraftChat
            messages={draft.messages}
            pending={assistMutation.isPending}
            onSend={(message) => void runAssist({ message })}
          />
        </div>
      )}

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

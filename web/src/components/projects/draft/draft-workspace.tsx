"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Alert02Icon,
  ArrowRight01Icon,
  FileVideoIcon,
  PencilEdit02Icon,
  SparklesIcon,
} from "@hugeicons/core-free-icons";
import { toast } from "sonner";

import { Icon } from "@/components/common/icon";
import { DisabledReason } from "@/components/common/disabled-reason";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { CrosspostCard } from "@/components/projects/draft/crosspost-card";
import { DraftBriefDialog } from "@/components/projects/draft/draft-brief-dialog";
import { DraftChat } from "@/components/projects/draft/draft-chat";
import { DraftContextPanel } from "@/components/projects/draft/draft-context-panel";
import { DraftGroundingPanel } from "@/components/projects/draft/draft-grounding-panel";
import { FreeFlowEditor } from "@/components/projects/draft/free-flow-editor";
import { ApiError } from "@/lib/api-client";
import {
  assistDraft,
  generateDraft,
  getDraft,
  saveDraft,
  suggestDraft,
} from "@/lib/drafts";
import { markdownToPlain } from "@/lib/draft-content";
import { createProject, listProjects } from "@/lib/projects";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";
import { workspaceHref } from "@/lib/studio";
import type { Draft, DraftBlock, DraftBrief } from "@/lib/types";
import {
  DRAFT_PANE_STACK_SPACER,
  WORKSPACE_SNAP_TARGET,
} from "@/lib/workspace";

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

/** The block a chat selection came from, so an assistant rewrite edits it in place. */
function findBlockForSelection(
  blocks: DraftBlock[],
  selection: string,
): DraftBlock | null {
  const needle = selection.replace(/\s+/g, " ").trim().toLowerCase();
  if (!needle) return null;
  for (const block of blocks) {
    const text = markdownToPlain(activeBlockText(block))
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
    if (!text) continue;
    if (text.includes(needle) || needle.includes(text)) return block;
  }
  return null;
}

/**
 * Rebuild the stored blocks from the single editable document. Blank lines are
 * paragraph breaks; an unchanged chunk keeps its history (and assistant
 * versions) so a normal edit does not throw previous wording away.
 */
function blocksFromMarkdown(
  markdown: string,
  previous: DraftBlock[],
): DraftBlock[] {
  const chunks = markdown
    .split(/\n{2,}/)
    .map((chunk) => chunk.replace(/\s+$/, ""))
    .filter((chunk) => chunk.trim().length > 0);
  return chunks.map((text, index) => {
    const prev = previous[index];
    const type: DraftBlock["type"] = /^#{1,6}\s/.test(text)
      ? "heading"
      : "paragraph";
    if (prev && prev.type === type && activeBlockText(prev) === text) {
      return prev;
    }
    const version = {
      versionId: newId(),
      text,
      label: "My edit",
      origin: "user" as const,
      createdAt: new Date().toISOString(),
    };
    return {
      blockId: prev?.blockId ?? newId(),
      type,
      versions: [version],
      activeVersionId: version.versionId,
    };
  });
}

/**
 * The draft studio: a free-flowing document on the left, a writing partner on
 * the right. The React Query cache is the single source of truth — edits write
 * to it optimistically and a debounced save persists them, while assistant
 * replies replace it wholesale. Alternative groups live inline in the text, so
 * nothing is ever lost. (The first paragraph keeps the docstring honest.)
 */
export function DraftWorkspace({
  project,
}: {
  project: import("@/lib/types").Project;
}) {
  const projectId = project.projectId;
  const queryClient = useQueryClient();
  const readOnly = useReadOnly();
  const router = useRouter();
  const [briefOpen, setBriefOpen] = useState(false);
  const [contextText, setContextText] = useState("");
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const autoRan = useRef(false);

  const draftQuery = useQuery({
    queryKey: ["draft", projectId],
    queryFn: () => getDraft(projectId),
    retry: false,
  });
  const draft = draftQuery.data;

  // Videos made from this draft (newest first) — once one exists the action
  // becomes "Go to video" instead of offering another conversion.
  const videosQuery = useQuery({
    queryKey: ["projects"],
    queryFn: listProjects,
    staleTime: 30_000,
  });
  const firstVideo = (videosQuery.data?.items ?? []).find(
    (item) => item.kind === "video" && item.sourceDraftId === projectId,
  );

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
      void queryClient.invalidateQueries({
        queryKey: ["draft-context", projectId],
      });
      if (next.status === "failed") {
        toast.error(next.error ?? "The draft could not be generated.");
      }
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
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (error) => {
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

  // Ctrl/Cmd+S (with or without Shift) saves the draft in place instead of
  // opening the browser's save-page dialog. Scoped to this workspace, so it
  // only applies while a draft is open.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (!event.ctrlKey && !event.metaKey) return;
      if (event.key.toLowerCase() !== "s") return;
      event.preventDefault();
      if (readOnly) return;
      void (async () => {
        try {
          await flushSave();
          toast.success("Draft saved");
        } catch {
          // The save mutation already toasts the failure.
        }
      })();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [flushSave, readOnly]);

  // Generate the first draft automatically when a project opens empty with a
  // brief already captured at creation.
  const runGenerate = generateMutation.mutate;
  useEffect(() => {
    if (readOnly) return;
    if (autoRan.current || !draft) return;
    if (draft.status !== "empty" || draft.blocks.length > 0) {
      autoRan.current = true;
      return;
    }
    if (!draft.brief.topic.trim()) return;
    autoRan.current = true;
    runGenerate(undefined);
  }, [draft, runGenerate, readOnly]);

  function editDoc(markdown: string) {
    mutateDraft((current) => ({
      ...current,
      blocks: blocksFromMarkdown(markdown, current.blocks),
    }));
  }

  async function suggest(
    text: string,
    mode: "rewrite" | "alternatives",
  ): Promise<string[]> {
    const context = draft
      ? draft.blocks.map((block) => activeBlockText(block)).join("\n\n")
      : "";
    try {
      const result = await suggestDraft(projectId, {
        text,
        context,
        mode,
        count: mode === "alternatives" ? 4 : 1,
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
  }) {
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

  const sendToVideoMutation = useMutation({
    mutationFn: async () => {
      // Persist any in-flight keystrokes first so the new project is fresh.
      await flushSave();
      const fresh =
        queryClient.getQueryData<Draft>(["draft", projectId]) ?? draft;
      const hasContent = (fresh?.blocks.length ?? 0) > 0;
      if (!hasContent) {
        throw new Error(
          "Write the draft first — there is nothing to send yet.",
        );
      }
      const platforms = (fresh?.brief.platform ?? "")
        .split(",")
        .map((part) => part.trim())
        .filter(Boolean);
      return createProject({
        name: fresh?.title.trim() || project.name,
        primaryLanguage: fresh?.brief.language || project.primaryLanguage,
        targetPlatforms: platforms,
        kind: "video",
        sourceDraftId: projectId,
      });
    },
    onSuccess: (video) => {
      toast.success("Video project created from this draft");
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      router.push(workspaceHref(video.projectId));
    },
    onError: (error) =>
      toast.error(describe(error, "Could not create the video project.")),
  });

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
  const videoChoices = (videosQuery.data?.items ?? []).filter(
    (item) => item.kind === "video",
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-sm text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <Icon icon={SparklesIcon} className="size-4 text-signal" />
          {draft.brief.topic || "No brief yet"}
        </span>
        {draft.brief.audience ? <span>· {draft.brief.audience}</span> : null}
        {draft.brief.tone ? <span>· {draft.brief.tone}</span> : null}
        <span className="ml-auto inline-flex items-center gap-1">
          {videosQuery.isLoading ? null : firstVideo ? (
            <Link
              href={workspaceHref(firstVideo.projectId)}
              className="inline-flex h-6 items-center gap-1 rounded-[min(var(--radius-md),10px)] border border-border bg-background px-2 text-xs font-medium transition-colors hover:bg-muted hover:text-foreground"
            >
              <Icon icon={ArrowRight01Icon} className="size-3" />
              Go to video
            </Link>
          ) : (
            <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
              <Button
                type="button"
                size="xs"
                variant="outline"
                onClick={() => sendToVideoMutation.mutate()}
                disabled={
                  readOnly ||
                  sendToVideoMutation.isPending ||
                  generating ||
                  empty
                }
                title={
                  empty
                    ? "Write the draft first"
                    : "Create a video project from this draft"
                }
              >
                <Icon icon={FileVideoIcon} />
                {sendToVideoMutation.isPending
                  ? "Converting…"
                  : "Convert to video"}
              </Button>
            </DisabledReason>
          )}
          <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
            <Button
              type="button"
              size="xs"
              variant="ghost"
              onClick={() => setBriefOpen(true)}
              disabled={readOnly}
            >
              <Icon icon={PencilEdit02Icon} />
              Edit brief
            </Button>
          </DisabledReason>
          <CrosspostCard projectId={projectId} />
        </span>
      </div>

      {draft.status === "failed" && !generating ? (
        <Alert variant="destructive">
          <Icon icon={Alert02Icon} />
          <AlertTitle>
            {empty
              ? "The draft was not generated"
              : "The last generation failed. Your existing draft is unchanged"}
          </AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span>
              {draft.error ?? "The writing partner did not respond. Try again."}
            </span>
            <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
              <Button
                type="button"
                size="xs"
                variant="outline"
                onClick={() => setBriefOpen(true)}
                disabled={readOnly}
              >
                Edit brief &amp; retry
              </Button>
            </DisabledReason>
          </AlertDescription>
        </Alert>
      ) : null}

      {draft.videoContext && !generating ? (
        <p className="text-xs text-muted-foreground">
          Drew on {draft.videoContext.projectName || "a video"}
          {draft.videoContext.source === "linked"
            ? " (made from this draft)"
            : ""}
          {": "}
          {draft.videoContext.findingCount} review finding
          {draft.videoContext.findingCount === 1 ? "" : "s"},{" "}
          {draft.videoContext.peakCount} audience interest moment
          {draft.videoContext.peakCount === 1 ? "" : "s"}
          {draft.videoContext.usedPersona ? ", your persona" : ""}.
        </p>
      ) : null}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] lg:items-start">
        {generating ? (
          <Card className={WORKSPACE_SNAP_TARGET}>
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
          <Card className={WORKSPACE_SNAP_TARGET}>
            <CardHeader>
              <CardTitle>Start your draft</CardTitle>
              <CardDescription>
                Give the writing partner a brief and it will write the first
                version for you to edit.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
                <Button
                  type="button"
                  onClick={() => setBriefOpen(true)}
                  disabled={readOnly}
                >
                  <Icon icon={SparklesIcon} />
                  Write a brief
                </Button>
              </DisabledReason>
            </CardContent>
          </Card>
        ) : (
          <FreeFlowEditor
            draft={draft}
            readOnly={readOnly}
            onTitle={(title) =>
              mutateDraft((current) => ({ ...current, title }))
            }
            onEditMarkdown={editDoc}
            onSuggest={suggest}
            onSelectText={setContextText}
            onUseContext={(text) => {
              setContextText(text);
              toast.success("Added to chat");
            }}
          />
        )}
        <DraftChat
          messages={draft.messages}
          pending={assistMutation.isPending}
          contextText={contextText}
          readOnly={readOnly}
          onClearContext={() => setContextText("")}
          hasContent={!empty}
          onSend={(message) => {
            const trimmed = contextText.trim();
            const quoted = trimmed ? `> ${trimmed.replace(/\n/g, "\n> ")}` : "";
            const full = quoted ? `${quoted}\n\n${message}` : message;
            const target = trimmed
              ? findBlockForSelection(draft.blocks, trimmed)
              : null;
            setContextText("");
            void runAssist({
              message: full,
              blockId: target?.blockId ?? null,
            });
          }}
        />
      </div>

      <DraftContextPanel projectId={projectId} enabled={!empty} />

      <DraftGroundingPanel grounding={draft.grounding ?? null} />

      <div aria-hidden className={DRAFT_PANE_STACK_SPACER} />

      <DraftBriefDialog
        key={briefOpen ? "open" : "closed"}
        open={briefOpen}
        onOpenChange={setBriefOpen}
        initial={draft.brief}
        pending={generating}
        onSubmit={regenerate}
        videos={videoChoices}
        title={empty ? "Write a brief" : "Edit brief & regenerate"}
      />
    </div>
  );
}

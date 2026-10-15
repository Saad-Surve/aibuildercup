"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckmarkCircle02Icon,
  Delete02Icon,
  Download01Icon,
  ImageAdd01Icon,
  Loading03Icon,
  MagicWand01Icon,
  PencilEdit02Icon,
  Refresh01Icon,
  SparklesIcon,
} from "@hugeicons/core-free-icons";
import { toast } from "sonner";

import { Icon } from "@/components/common/icon";
import { DisabledReason } from "@/components/common/disabled-reason";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api-client";
import {
  applyThumbnail,
  deleteThumbnail,
  downloadThumbnailsZip,
  generateThumbnails,
  getJob,
  listThumbnails,
  regenerateThumbnails,
  reviseThumbnail,
} from "@/lib/projects";
import type { ThumbnailAspect, ThumbnailConcept } from "@/lib/types";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";
import { cn } from "@/lib/utils";

const ASPECTS: { value: ThumbnailAspect; label: string; hint: string }[] = [
  { value: "16:9", label: "16:9", hint: "YouTube / landscape" },
  { value: "9:16", label: "9:16", hint: "Shorts / portrait" },
  { value: "1:1", label: "1:1", hint: "Feed / square" },
];

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}

function formatTimestamp(ms: number | null): string {
  if (ms === null || ms === undefined) return "—";
  const total = Math.max(0, Math.round(ms / 1000));
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function scoreTone(score: number): string {
  if (score >= 4) return "border-sev-good/40 bg-sev-good/10 text-sev-good";
  if (score === 3) return "border-sev-low/40 bg-sev-low/10 text-sev-low";
  if (score > 0) return "border-sev-high/40 bg-sev-high/10 text-sev-high";
  return "border-border bg-muted text-muted-foreground";
}

/** Small 1-5 score chip with a short label. */
function Score({ label, value }: { label: string; value: number }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[11px]",
        scoreTone(value),
      )}
      title={`${label}: ${value}/5`}
    >
      <span className="font-medium">{label}</span>
      <span className="tabular">{value > 0 ? value : "–"}</span>
    </span>
  );
}

function ConceptCard({
  concept,
  projectId,
  busy,
  selected,
  onToggleSelect,
  onRevise,
  onApply,
  onDelete,
}: {
  concept: ThumbnailConcept;
  projectId: string;
  busy: boolean;
  selected: boolean;
  onToggleSelect: (thumbnailId: string) => void;
  onRevise: (thumbnailId: string, instruction: string) => void;
  onApply: (thumbnailId: string) => void;
  onDelete: (thumbnailId: string) => void;
}) {
  const readOnly = useReadOnly();
  const [editing, setEditing] = useState(false);
  const [instruction, setInstruction] = useState("");
  const active = useMemo(() => {
    const version = concept.versions.find(
      (item) => item.versionId === concept.activeVersionId,
    );
    return version ?? concept.versions[concept.versions.length - 1] ?? null;
  }, [concept.versions, concept.activeVersionId]);

  const working =
    concept.status === "queued" || concept.status === "generating" || busy;
  const critique = active?.critique ?? null;

  function submitRevise() {
    const text = instruction.trim();
    if (!text) return;
    onRevise(concept.thumbnailId, text);
    setInstruction("");
    setEditing(false);
  }

  return (
    <div className="flex flex-col overflow-hidden rounded-xl border bg-card">
      <div className="relative aspect-video w-full bg-muted">
        {concept.previewUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={concept.previewUrl}
            alt={concept.headline || "Thumbnail concept"}
            className={
              concept.aspect === "16:9"
                ? "h-full w-full object-cover"
                : "h-full w-full object-contain"
            }
          />
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center gap-2 text-muted-foreground">
            {working ? (
              <Icon icon={Loading03Icon} className="size-6 animate-spin" />
            ) : (
              <Icon icon={ImageAdd01Icon} className="size-6" />
            )}
            <span className="text-xs">
              {concept.status === "failed"
                ? "Generation failed"
                : working
                  ? "Rendering…"
                  : "No image"}
            </span>
          </div>
        )}
        <div className="absolute top-2 left-2">
          <Checkbox
            checked={selected}
            onCheckedChange={() => onToggleSelect(concept.thumbnailId)}
            aria-label="Select concept"
            className="border-white/70 bg-background/80 shadow-sm backdrop-blur-sm"
          />
        </div>
        <div className="absolute top-2 right-2 flex flex-wrap justify-end gap-1">
          {concept.isApplied ? (
            <Badge className="gap-1">
              <Icon icon={CheckmarkCircle02Icon} className="size-3" />
              Applied
            </Badge>
          ) : null}
          {active && active.version > 1 ? (
            <Badge variant="secondary">v{active.version}</Badge>
          ) : null}
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-3 p-3">
        <div className="space-y-1">
          <p className="font-heading text-sm leading-tight font-semibold">
            {concept.headline || "Planning…"}
          </p>
          {concept.sourceTimestampMs !== null ? (
            <p className="text-[11px] text-muted-foreground">
              Built from the moment at{" "}
              {formatTimestamp(concept.sourceTimestampMs)}
            </p>
          ) : null}
        </div>

        {concept.rationale ? (
          <p className="text-xs text-muted-foreground">{concept.rationale}</p>
        ) : null}

        {critique ? (
          <div className="space-y-2">
            <div className="flex flex-wrap gap-1.5">
              <Score label="Legible" value={critique.legibility} />
              <Score label="Honest" value={critique.promise} />
              <Score label="Fit" value={critique.platformFit} />
            </div>
            {critique.summary ? (
              <p className="text-xs text-muted-foreground italic">
                {critique.summary}
              </p>
            ) : null}
          </div>
        ) : null}

        {concept.error?.message ? (
          <p className="text-xs text-destructive">{concept.error.message}</p>
        ) : null}

        {editing ? (
          <div className="space-y-2">
            <Textarea
              rows={2}
              value={instruction}
              placeholder="e.g. bigger headline, warmer light, put me on the left"
              onChange={(event) => setInstruction(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                  submitRevise();
                }
              }}
            />
            <div className="flex items-center gap-2">
              <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
                <Button
                  size="sm"
                  onClick={submitRevise}
                  disabled={working || !instruction.trim() || readOnly}
                >
                  Apply edit
                </Button>
              </DisabledReason>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setEditing(false);
                  setInstruction("");
                }}
              >
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <div className="mt-auto flex items-center gap-1.5 pt-1">
            <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
              <Button
                size="sm"
                variant="outline"
                disabled={working || !active || readOnly}
                onClick={() => setEditing(true)}
              >
                <Icon icon={PencilEdit02Icon} />
                Edit
              </Button>
            </DisabledReason>
            <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
              <Button
                size="sm"
                variant={concept.isApplied ? "secondary" : "default"}
                disabled={
                  working || concept.isApplied || !concept.headline || readOnly
                }
                onClick={() => onApply(concept.thumbnailId)}
              >
                <Icon icon={CheckmarkCircle02Icon} />
                {concept.isApplied ? "Applied" : "Use"}
              </Button>
            </DisabledReason>
            <div className="ml-auto flex items-center gap-0.5">
              <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label="More like this"
                  title="More like this"
                  disabled={working || readOnly}
                  onClick={() =>
                    onRevise(
                      concept.thumbnailId,
                      "Create a fresh alternative in the same direction and tone, but with a different composition.",
                    )
                  }
                >
                  <Icon icon={Refresh01Icon} />
                </Button>
              </DisabledReason>
              {concept.previewUrl ? (
                <Button
                  size="icon"
                  variant="ghost"
                  nativeButton={false}
                  aria-label="Download thumbnail"
                  render={
                    <a
                      href={concept.previewUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label="Download thumbnail"
                      download={`${projectId}-${concept.thumbnailId.slice(0, 6)}.png`}
                    />
                  }
                >
                  <Icon icon={Download01Icon} />
                </Button>
              ) : null}
              <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label="Delete concept"
                  disabled={busy || readOnly}
                  onClick={() => onDelete(concept.thumbnailId)}
                >
                  <Icon icon={Delete02Icon} />
                </Button>
              </DisabledReason>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * The thumbnail studio: generate grounded concepts from the video, judge each one honestly,
 * iterate conversationally, and apply the winner to the project's packaging.
 */
export function ThumbnailPanel({
  projectId,
  projectName,
}: {
  projectId: string;
  projectName: string;
}) {
  const queryClient = useQueryClient();
  const readOnly = useReadOnly();
  const [aspect, setAspect] = useState<ThumbnailAspect>("16:9");
  const [count, setCount] = useState("4");
  const [brief, setBrief] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [downloading, setDownloading] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const notifiedJob = useRef<string | null>(null);

  const conceptsQuery = useQuery({
    queryKey: ["thumbnails", projectId],
    queryFn: () => listThumbnails(projectId),
    // Keep refreshing while concepts are in flight; stop once none are.
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some(
        (item) => item.status === "queued" || item.status === "generating",
      )
        ? 3000
        : false;
    },
    retry: false,
  });

  const concepts = useMemo(
    () => conceptsQuery.data?.items ?? [],
    [conceptsQuery.data],
  );
  const inFlight = concepts.find(
    (item) => item.status === "queued" || item.status === "generating",
  );
  const jobId = activeJobId ?? inFlight?.jobId ?? null;

  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "succeeded" ||
        status === "failed" ||
        status === "cancelled"
        ? false
        : 2000;
    },
    refetchIntervalInBackground: false,
    retry: false,
  });

  const jobStatus = jobQuery.data?.status;
  const jobTerminal =
    jobStatus === "succeeded" ||
    jobStatus === "failed" ||
    jobStatus === "cancelled";

  useEffect(() => {
    if (!jobId || !jobStatus || !jobTerminal) return;
    if (notifiedJob.current === jobId) return;
    notifiedJob.current = jobId;
    if (jobStatus === "succeeded") {
      toast.success("Thumbnail concepts ready");
    } else if (jobStatus === "failed") {
      const message =
        (jobQuery.data?.error?.message as string | undefined) ??
        "Thumbnail generation failed.";
      toast.error(message);
    }
    void queryClient.invalidateQueries({ queryKey: ["thumbnails", projectId] });
  }, [jobId, jobStatus, jobTerminal, jobQuery.data, projectId, queryClient]);

  const generateMutation = useMutation({
    mutationFn: () =>
      generateThumbnails(projectId, {
        aspect,
        count: Number(count),
        brief: brief.trim(),
        useRealFrames: true,
      }),
    onSuccess: (result) => {
      setActiveJobId(result.jobId);
      void queryClient.invalidateQueries({
        queryKey: ["thumbnails", projectId],
      });
      toast.success("Planning thumbnail concepts…");
    },
    onError: (caught) =>
      toast.error(errorMessage(caught, "Could not start generation.")),
  });

  const reviseMutation = useMutation({
    mutationFn: (input: { thumbnailId: string; instruction: string }) =>
      reviseThumbnail(projectId, input.thumbnailId, input.instruction),
    onSuccess: (result) => {
      setActiveJobId(result.jobId);
      void queryClient.invalidateQueries({
        queryKey: ["thumbnails", projectId],
      });
      toast.success("Applying your edit…");
    },
    onError: (caught) =>
      toast.error(errorMessage(caught, "Could not apply the edit.")),
  });

  const applyMutation = useMutation({
    mutationFn: (thumbnailId: string) => applyThumbnail(projectId, thumbnailId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["thumbnails", projectId],
      });
      void queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success("Applied to the project's thumbnail concept");
    },
    onError: (caught) =>
      toast.error(errorMessage(caught, "Could not apply the concept.")),
  });

  const deleteMutation = useMutation({
    mutationFn: (thumbnailId: string) =>
      deleteThumbnail(projectId, thumbnailId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["thumbnails", projectId],
      });
      toast.success("Concept deleted");
    },
    onError: (caught) =>
      toast.error(errorMessage(caught, "Could not delete the concept.")),
  });

  const regenerateMutation = useMutation({
    mutationFn: (thumbnailIds: string[]) =>
      regenerateThumbnails(projectId, thumbnailIds),
    onSuccess: (result) => {
      setActiveJobId(result.jobId);
      setSelected(new Set());
      void queryClient.invalidateQueries({
        queryKey: ["thumbnails", projectId],
      });
      toast.success("Re-rendering selected concepts…");
    },
    onError: (caught) =>
      toast.error(errorMessage(caught, "Could not redo the concepts.")),
  });

  const bulkDeleteMutation = useMutation({
    mutationFn: (thumbnailIds: string[]) =>
      Promise.all(
        thumbnailIds.map((thumbnailId) =>
          deleteThumbnail(projectId, thumbnailId),
        ),
      ),
    onSuccess: () => {
      setSelected(new Set());
      void queryClient.invalidateQueries({
        queryKey: ["thumbnails", projectId],
      });
      toast.success("Deleted selected concepts");
    },
    onError: (caught) =>
      toast.error(errorMessage(caught, "Could not delete the concepts.")),
  });

  const selectedIds = concepts
    .filter((concept) => selected.has(concept.thumbnailId))
    .map((concept) => concept.thumbnailId);
  const allSelected =
    concepts.length > 0 && selectedIds.length === concepts.length;
  const bulkBusy =
    regenerateMutation.isPending || bulkDeleteMutation.isPending || downloading;

  function toggleSelect(thumbnailId: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(thumbnailId)) next.delete(thumbnailId);
      else next.add(thumbnailId);
      return next;
    });
  }

  function toggleAll(checked: boolean) {
    setSelected(
      checked
        ? new Set(concepts.map((concept) => concept.thumbnailId))
        : new Set(),
    );
  }

  async function downloadSelected() {
    if (selectedIds.length === 0) return;
    setDownloading(true);
    try {
      const blob = await downloadThumbnailsZip(projectId, selectedIds);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "thumbnails.zip";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      toast.success("Download started");
    } catch (caught) {
      toast.error(errorMessage(caught, "Could not download the thumbnails."));
    } finally {
      setDownloading(false);
    }
  }

  const generating =
    generateMutation.isPending ||
    Boolean(inFlight) ||
    (jobId !== null && !jobTerminal);
  const percent = jobQuery.data?.progress.percent ?? 0;
  const jobMessage = jobQuery.data?.progress.message ?? "Queued";

  return (
    <div className="space-y-5">
      <div className="space-y-4 rounded-xl border bg-muted/30 p-4">
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
          <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-muted-foreground">
                Aspect
              </span>
              <div className="flex gap-1">
                {ASPECTS.map((option) => (
                  <Button
                    key={option.value}
                    type="button"
                    size="sm"
                    variant={aspect === option.value ? "default" : "outline"}
                    title={option.hint}
                    onClick={() => setAspect(option.value)}
                  >
                    {option.label}
                  </Button>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-muted-foreground">
                Concepts
              </span>
              <Select
                value={count}
                onValueChange={(value) => setCount(value ?? "4")}
              >
                <SelectTrigger size="sm" className="w-[4.5rem]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {["2", "3", "4"].map((value) => (
                    <SelectItem key={value} value={value}>
                      {value}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
            <Button
              type="button"
              onClick={() => generateMutation.mutate()}
              disabled={generating || readOnly}
            >
              <Icon
                icon={generating ? Loading03Icon : MagicWand01Icon}
                className={generating ? "animate-spin" : undefined}
              />
              {generating ? "Generating…" : "Generate concepts"}
            </Button>
          </DisabledReason>
        </div>

        <div className="space-y-1.5">
          <span className="text-xs font-medium text-muted-foreground">
            Direction (optional)
          </span>
          <Textarea
            rows={2}
            value={brief}
            placeholder="Tone, must-include, must-avoid. e.g. warm and personal, no shock faces."
            onChange={(event) => setBrief(event.target.value)}
          />
        </div>
      </div>

      {generating ? (
        <div className="space-y-2 rounded-lg border bg-muted/40 p-3">
          <div className="flex items-center gap-2 text-sm">
            <Icon icon={Loading03Icon} className="animate-spin text-signal" />
            <span>{jobMessage}</span>
            <span className="ml-auto tabular text-muted-foreground">
              {percent}%
            </span>
          </div>
          <Progress value={percent} />
          <p className="text-xs text-muted-foreground">
            The planner is reading {projectName}&apos;s transcript and review
            findings, pulling real frames of you, then rendering each concept.
          </p>
        </div>
      ) : null}

      {concepts.length > 0 ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
              <Checkbox
                checked={allSelected}
                onCheckedChange={(value) => toggleAll(Boolean(value))}
                aria-label="Select all concepts"
              />
              Select all
            </label>
            {selectedIds.length > 0 ? (
              <div className="ml-auto flex flex-wrap items-center gap-1.5">
                <span className="mr-1 text-xs text-muted-foreground">
                  {selectedIds.length} selected
                </span>
                <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={bulkBusy || readOnly}
                    onClick={() => regenerateMutation.mutate(selectedIds)}
                  >
                    <Icon icon={Refresh01Icon} />
                    Redo
                  </Button>
                </DisabledReason>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={bulkBusy}
                  onClick={() => void downloadSelected()}
                >
                  <Icon icon={Download01Icon} />
                  Download
                </Button>
                <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
                  <Button
                    size="sm"
                    variant="destructive"
                    disabled={bulkBusy || readOnly}
                    onClick={() => bulkDeleteMutation.mutate(selectedIds)}
                  >
                    <Icon icon={Delete02Icon} />
                    Delete
                  </Button>
                </DisabledReason>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setSelected(new Set())}
                >
                  Clear
                </Button>
              </div>
            ) : null}
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {concepts.map((concept) => (
              <ConceptCard
                key={concept.thumbnailId}
                concept={concept}
                projectId={projectId}
                busy={bulkBusy || deleteMutation.isPending}
                selected={selected.has(concept.thumbnailId)}
                onToggleSelect={toggleSelect}
                onRevise={(thumbnailId, instruction) =>
                  reviseMutation.mutate({ thumbnailId, instruction })
                }
                onApply={(thumbnailId) => applyMutation.mutate(thumbnailId)}
                onDelete={(thumbnailId) => deleteMutation.mutate(thumbnailId)}
              />
            ))}
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed p-10 text-center">
          <Icon icon={SparklesIcon} className="size-6 text-muted-foreground" />
          <p className="text-sm font-medium">No thumbnail concepts yet</p>
          <p className="max-w-md text-xs text-muted-foreground">
            Generate options grounded in the video: each concept cites the
            moment it came from, keeps your real face, and is scored on
            legibility, honesty, and platform fit.
          </p>
        </div>
      )}
    </div>
  );
}

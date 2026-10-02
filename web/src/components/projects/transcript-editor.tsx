"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Add01Icon,
  ArrowLeft01Icon,
  Cancel01Icon,
  ClosedCaptionIcon,
  Delete02Icon,
  FloppyDiskIcon,
  PlayIcon,
  Refresh01Icon,
  Search01Icon,
  UserEdit01Icon,
} from "@hugeicons/core-free-icons";
import { toast } from "sonner";

import { Icon } from "@/components/common/icon";
import { PageHeader } from "@/components/common/page-header";
import { SourceVideoPlayer } from "@/components/projects/source-video-player";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useProjectTranscript } from "@/hooks/use-project-transcript";
import { ApiError } from "@/lib/api-client";
import {
  formatTimestamp,
  getProject,
  listAssets,
  pickSourceAsset,
  updateTranscript,
} from "@/lib/projects";
import type { TranscriptSegment } from "@/lib/types";

function describe(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Could not save the transcript.";
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function newSegmentId(): string {
  return `seg-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Loading placeholder for the editor. Mirrors the real page: a back-link line
 * and title, then the video + controls row above the transcript pane, which
 * fills the rest of the viewport on large screens.
 */
export function TranscriptEditorSkeleton() {
  return (
    <div className="flex w-full flex-col">
      <div className="space-y-6 pb-6">
        <Skeleton className="h-5 w-32" />
        <Skeleton className="h-7 w-72" />
      </div>

      <div className="flex flex-col gap-6 lg:h-[calc(100dvh-6.5rem)]">
        <div className="shrink-0 grid gap-4 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] lg:items-stretch">
          <Skeleton className="aspect-video w-full rounded-xl" />
          <Skeleton className="min-h-40 w-full rounded-lg" />
        </div>
        <Skeleton className="min-h-64 flex-1 rounded-lg" />
      </div>
    </div>
  );
}

/** Parse `mm:ss`, `hh:mm:ss`, or a bare seconds value into milliseconds. */
function parseTimestamp(value: string): number | null {
  const text = value.trim();
  if (!text) return null;
  const parts = text.split(":");
  let hours = "0";
  let minutes = "0";
  let seconds = text;
  if (parts.length === 3) {
    [hours, minutes, seconds] = parts as [string, string, string];
  } else if (parts.length === 2) {
    [minutes, seconds] = parts as [string, string];
  }
  const hoursValue = Number(hours);
  const minutesValue = Number(minutes);
  const secondsValue = Number(seconds.replace(",", "."));
  if (![hoursValue, minutesValue, secondsValue].every(Number.isFinite)) {
    return null;
  }
  return Math.max(
    0,
    Math.round(((hoursValue * 60 + minutesValue) * 60 + secondsValue) * 1000),
  );
}

/** Clamp a requested start time into `[0, maxMs]` (an unknown max means no cap). */
function clampStart(ms: number, maxMs: number | null): number {
  const lower = Math.max(0, ms);
  return maxMs != null ? Math.min(lower, maxMs) : lower;
}

/** Keep an end time at or after the start and no later than the media end. */
function clampEnd(ms: number, startMs: number, maxMs: number | null): number {
  const upper = maxMs != null ? Math.min(Math.max(startMs, ms), maxMs) : ms;
  return Math.max(startMs, upper);
}

/**
 * Compact `mm:ss` field that commits a parsed value on blur or Enter. The call
 * site keys it by the incoming value so an external change (discard, a new
 * version) resets the field without an effect. Values past `maxMs` are rejected.
 */
function TimestampInput({
  valueMs,
  maxMs,
  onCommit,
}: {
  valueMs: number;
  maxMs: number | null;
  onCommit: (ms: number) => void;
}) {
  const [text, setText] = useState(() => formatTimestamp(valueMs));

  function commit() {
    const parsed = parseTimestamp(text);
    if (parsed == null) {
      setText(formatTimestamp(valueMs));
      toast.error("Enter a time like 1:23.");
      return;
    }
    if (maxMs != null && parsed > maxMs) {
      setText(formatTimestamp(valueMs));
      toast.error(
        `That time is past the end of the video (${formatTimestamp(maxMs)}).`,
      );
      return;
    }
    onCommit(parsed);
    setText(formatTimestamp(parsed));
  }

  return (
    <Input
      value={text}
      onChange={(event) => setText(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.currentTarget.blur();
        } else if (event.key === "Escape") {
          setText(formatTimestamp(valueMs));
          event.currentTarget.blur();
        }
      }}
      inputMode="numeric"
      title="Edit start time (mm:ss)"
      className="tabular h-8 w-14 shrink-0 px-1 text-center text-xs"
    />
  );
}

/*
 * Transcript studio. A small source-video player sits top-left, the edit
 * toolbar (find/replace, rename speaker, save/discard) fills the top-right, and
 * the editable segments run full width underneath.
 *
 * Editing is local until Save: `draft` is null while clean and holds the whole
 * segment array once anything changes. Discard drops it and re-reads the
 * server's version. Save posts a new version, so the machine transcript is never
 * lost and stays selectable in the transcript card's version picker.
 */
export function TranscriptEditor({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<TranscriptSegment[] | null>(null);
  const [labelsDraft, setLabelsDraft] = useState<Record<string, string> | null>(
    null,
  );
  const [find, setFind] = useState("");
  const [replace, setReplace] = useState("");
  const [renameFrom, setRenameFrom] = useState("1");
  const [renameTo, setRenameTo] = useState("1");
  const [renameName, setRenameName] = useState("");
  const [renameOpen, setRenameOpen] = useState(false);
  const [videoDurationMs, setVideoDurationMs] = useState<number | null>(null);

  const projectQuery = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId),
  });
  const assetsQuery = useQuery({
    queryKey: ["assets", projectId],
    queryFn: () => listAssets(projectId),
  });
  const transcriptQuery = useProjectTranscript(projectId, { shouldPoll: true });

  const transcript = transcriptQuery.data;
  const segments = draft ?? transcript?.segments ?? [];
  const speakerLabels = labelsDraft ?? transcript?.speakerLabels ?? {};
  const dirty = draft !== null || labelsDraft !== null;
  const sourceAsset = pickSourceAsset(
    assetsQuery.data?.items,
    projectQuery.data?.sourceAssetId,
  );
  // Prefer the real player duration; fall back to the transcript's own length.
  const maxDurationMs = videoDurationMs ?? transcript?.durationMs ?? null;

  const detectedSpeakers = Array.from(
    new Set(
      segments
        .map((segment) => segment.speaker)
        .filter((speaker): speaker is number => speaker != null),
    ),
  ).toSorted((a, b) => a - b);

  const needle = find.trim();
  const matchCount = needle
    ? segments.filter((segment) =>
        segment.text.toLowerCase().includes(needle.toLowerCase()),
      ).length
    : 0;

  function applyToDraft(
    updater: (current: TranscriptSegment[]) => TranscriptSegment[],
  ) {
    setDraft((previous) => updater(previous ?? transcript?.segments ?? []));
  }

  function applyToLabels(
    updater: (current: Record<string, string>) => Record<string, string>,
  ) {
    setLabelsDraft((previous) =>
      updater(previous ?? transcript?.speakerLabels ?? {}),
    );
  }

  function updateSegment(segmentId: string, patch: Partial<TranscriptSegment>) {
    applyToDraft((current) =>
      current.map((segment) =>
        segment.segmentId === segmentId ? { ...segment, ...patch } : segment,
      ),
    );
  }

  function deleteSegment(segmentId: string) {
    applyToDraft((current) =>
      current.filter((segment) => segment.segmentId !== segmentId),
    );
  }

  function addSegment() {
    applyToDraft((current) => {
      const last = current[current.length - 1];
      const startMs = clampStart(last ? last.endMs : 0, maxDurationMs);
      const endMs = clampEnd(startMs + 2000, startMs, maxDurationMs);
      return [
        ...current,
        {
          segmentId: newSegmentId(),
          index: current.length,
          startMs,
          endMs,
          text: "",
          speaker: last?.speaker ?? null,
        },
      ];
    });
  }

  /** Insert a blank segment directly below an existing one. */
  function insertSegmentAfter(segmentId: string) {
    applyToDraft((current) => {
      const index = current.findIndex(
        (segment) => segment.segmentId === segmentId,
      );
      if (index === -1) return current;
      const previous = current[index]!;
      const next = current[index + 1];
      const startMs = clampStart(previous.endMs, maxDurationMs);
      const endMs = clampEnd(
        next ? Math.max(startMs, next.startMs) : startMs + 2000,
        startMs,
        maxDurationMs,
      );
      const copy = [...current];
      copy.splice(index + 1, 0, {
        segmentId: newSegmentId(),
        index: index + 1,
        startMs,
        endMs,
        text: "",
        speaker: previous.speaker ?? null,
      });
      return copy.map((segment, position) => ({
        ...segment,
        index: position,
      }));
    });
  }

  function replaceAll() {
    if (!needle) return;
    const pattern = new RegExp(escapeRegExp(needle), "gi");
    applyToDraft((current) =>
      current.map((segment) => ({
        ...segment,
        text: segment.text.replace(pattern, replace),
      })),
    );
  }

  /** Replace the needle in one segment only (the row-level "Replace"). */
  function replaceOne(segmentId: string) {
    if (!needle) return;
    const pattern = new RegExp(escapeRegExp(needle), "gi");
    applyToDraft((current) =>
      current.map((segment) =>
        segment.segmentId === segmentId
          ? { ...segment, text: segment.text.replace(pattern, replace) }
          : segment,
      ),
    );
  }

  function renameSpeaker() {
    const from = Number(renameFrom);
    const to = Number(renameTo);
    if (!Number.isFinite(from) || !Number.isFinite(to)) return;
    const name = renameName.trim();
    if (from !== to) {
      applyToDraft((current) =>
        current.map((segment) =>
          segment.speaker === from ? { ...segment, speaker: to } : segment,
        ),
      );
      // Moving one speaker's lines onto another must move its name too, or the
      // label would point at an index no segment uses any more.
      applyToLabels((current) => {
        const next = { ...current };
        if (next[String(from)] && !next[String(to)]) {
          next[String(to)] = next[String(from)]!;
        }
        delete next[String(from)];
        if (name) next[String(to)] = name;
        return next;
      });
    } else if (name) {
      applyToLabels((current) => ({ ...current, [String(to)]: name }));
    }
    setRenameName("");
    setRenameOpen(false);
  }

  const save = useMutation({
    mutationFn: () => {
      if (!segments.some((segment) => segment.text.trim())) {
        throw new Error("Nothing to save — every row is empty.");
      }
      return updateTranscript(projectId, {
        language: transcript?.language,
        speakerLabels,
        segments: segments.map((segment, index) => ({
          ...segment,
          index,
        })),
      });
    },
    onSuccess: (saved) => {
      queryClient.setQueryData(["transcript", projectId, "active"], saved);
      void queryClient.invalidateQueries({
        queryKey: ["transcript-versions", projectId],
      });
      setDraft(null);
      setLabelsDraft(null);
      toast.success("Transcript saved as a new version");
    },
    onError: (error) => toast.error(describe(error)),
  });

  function seekTo(startMs: number) {
    window.dispatchEvent(
      new CustomEvent("creator-studio:seek", {
        detail: { projectId, seconds: startMs / 1000 },
      }),
    );
  }

  const backLink = (
    <Link
      href={`/projects/view?projectId=${projectId}`}
      className="shrink-0 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
    >
      <Icon icon={ArrowLeft01Icon} />
      Back to project
    </Link>
  );

  if (transcriptQuery.isLoading || projectQuery.isLoading) {
    return <TranscriptEditorSkeleton />;
  }

  if (!transcript) {
    return (
      <div className="w-full space-y-4">
        {backLink}
        <PageHeader title="Transcript not ready" />
        <p className="text-sm text-muted-foreground">
          There is no transcript to edit yet. Finish transcription first, then
          come back.
        </p>
      </div>
    );
  }

  return (
    <div className="flex w-full flex-col">
      {/*
       * First snap stop: the back link and the title. Keeping the back link in
       * a stop means page scrolling can always rest with it on screen instead
       * of skipping straight past it.
       */}
      <div className="space-y-6 pb-6 lg:snap-start lg:snap-always lg:scroll-mt-20">
        {backLink}

        <PageHeader
          className="shrink-0"
          title={
            <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
              Edit transcript
              {projectQuery.data ? (
                <>
                  <span className="h-4 w-px bg-border" aria-hidden="true" />
                  <span className="text-sm font-normal text-muted-foreground">
                    {projectQuery.data.name}
                  </span>
                </>
              ) : null}
            </span>
          }
        />
      </div>

      {/*
       * Second snap stop: the video + controls row. The section is exactly one
       * viewport tall minus the shell header and the same gap the row snaps
       * with, so the row leaves an even gap above and below it once snapped
       * and the transcript below fills everything in between.
       */}
      <div className="flex flex-col gap-6 lg:h-[calc(100dvh-6.5rem)]">
        {/* Row 1: small player on the left, edit toolbar filling the rest. */}
        <div className="shrink-0 grid gap-4 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)] lg:items-stretch lg:snap-start lg:snap-always lg:scroll-mt-20">
          <div className="overflow-hidden rounded-lg shadow-sm ring-1 ring-foreground/10">
            {sourceAsset ? (
              <SourceVideoPlayer
                projectId={projectId}
                asset={sourceAsset}
                onDuration={setVideoDurationMs}
              />
            ) : (
              <div className="flex aspect-video w-full items-center justify-center bg-muted text-center text-xs text-muted-foreground ring-1 ring-foreground/10">
                Video is not available in this browser.
              </div>
            )}
          </div>

          <Card className="flex flex-col">
            <CardContent className="flex flex-1 flex-col gap-4">
              <div className="flex flex-wrap items-end gap-2">
                <div className="w-44 space-y-1.5">
                  <label
                    htmlFor="transcript-find"
                    className="text-xs font-medium text-muted-foreground"
                  >
                    Find
                  </label>
                  <div className="relative">
                    <Icon
                      icon={Search01Icon}
                      className="pointer-events-none absolute top-1/2 left-2 -translate-y-1/2 text-muted-foreground"
                    />
                    <Input
                      id="transcript-find"
                      value={find}
                      onChange={(event) => setFind(event.target.value)}
                      placeholder="Search text"
                      className="pl-7"
                    />
                  </div>
                </div>
                <div className="w-44 space-y-1.5">
                  <label
                    htmlFor="transcript-replace"
                    className="text-xs font-medium text-muted-foreground"
                  >
                    Replace with
                  </label>
                  <Input
                    id="transcript-replace"
                    value={replace}
                    onChange={(event) => setReplace(event.target.value)}
                    placeholder="Replacement"
                  />
                </div>
                <Button
                  type="button"
                  variant="outline"
                  onClick={replaceAll}
                  disabled={!needle}
                >
                  <Icon icon={Refresh01Icon} />
                  Replace all
                </Button>
                <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
                  <DialogTrigger
                    render={<Button type="button" variant="outline" />}
                  >
                    <Icon icon={UserEdit01Icon} />
                    Rename speaker
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Rename speaker</DialogTitle>
                      <DialogDescription>
                        Move every line by one speaker onto another — useful
                        when diarization splits one voice in two — and
                        optionally give the speaker a name.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="grid grid-cols-2 gap-3">
                      <Field>
                        <FieldLabel>From speaker</FieldLabel>
                        <Input
                          value={renameFrom}
                          onChange={(event) =>
                            setRenameFrom(
                              event.target.value.replace(/[^0-9]/g, ""),
                            )
                          }
                          inputMode="numeric"
                          placeholder="1"
                        />
                      </Field>
                      <Field>
                        <FieldLabel>To speaker</FieldLabel>
                        <Input
                          value={renameTo}
                          onChange={(event) =>
                            setRenameTo(
                              event.target.value.replace(/[^0-9]/g, ""),
                            )
                          }
                          inputMode="numeric"
                          placeholder="1"
                        />
                      </Field>
                      <Field className="col-span-2">
                        <FieldLabel>Name</FieldLabel>
                        <Input
                          value={renameName}
                          onChange={(event) =>
                            setRenameName(event.target.value)
                          }
                          placeholder="Host"
                        />
                      </Field>
                    </div>
                    <DialogFooter>
                      <DialogClose
                        render={
                          <Button type="button" variant="outline" size="sm" />
                        }
                      >
                        Cancel
                      </DialogClose>
                      <Button type="button" size="sm" onClick={renameSpeaker}>
                        Apply
                      </Button>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </div>

              <div className="mt-auto flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-muted-foreground">
                  {needle
                    ? `${matchCount} ${matchCount === 1 ? "segment" : "segments"} match “${needle}”`
                    : dirty
                      ? "Unsaved changes"
                      : "No changes"}
                </p>
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setDraft(null);
                      setLabelsDraft(null);
                    }}
                    disabled={!dirty || save.isPending}
                  >
                    <Icon icon={Cancel01Icon} />
                    Discard
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    onClick={() => save.mutate()}
                    disabled={!dirty || save.isPending}
                  >
                    <Icon icon={FloppyDiskIcon} />
                    {save.isPending ? "Saving…" : "Save"}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Lower pane: the editable transcript itself. Fixed height so it scrolls
          internally, and a snap stop so page scrolling snaps its top under the
          header (mirrors the project workspace panes). */}
        <Card className="flex min-h-0 flex-1 flex-col max-h-[min(70vh,36rem)] lg:max-h-none">
          <CardHeader className="shrink-0">
            <div className="flex flex-wrap items-center gap-2">
              <Icon
                icon={ClosedCaptionIcon}
                className="text-muted-foreground"
              />
              <CardTitle>Transcript</CardTitle>
              <span className="h-4 w-px bg-border" aria-hidden="true" />
              <span className="text-sm text-muted-foreground">
                {segments.length}{" "}
                {segments.length === 1 ? "segment" : "segments"}
                {" · "}
                {transcript.language}
              </span>
            </div>
          </CardHeader>
          <CardContent className="scroll-fade-y min-h-0 flex-1 overflow-y-auto overscroll-y-contain py-3">
            <ol className="space-y-0.5">
              {segments.map((segment) => {
                const matches =
                  needle.length > 0 &&
                  segment.text.toLowerCase().includes(needle.toLowerCase());
                return (
                  <li
                    key={segment.segmentId}
                    className={`relative flex items-start gap-1.5 rounded-lg px-1.5 py-1 transition-colors ${
                      matches
                        ? "bg-signal/5 ring-1 ring-signal/30"
                        : "hover:bg-muted"
                    }`}
                  >
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="shrink-0 text-muted-foreground"
                      onClick={() => seekTo(segment.startMs)}
                      title="Seek to this segment"
                    >
                      <Icon icon={PlayIcon} />
                      <span className="sr-only">Seek to this segment</span>
                    </Button>
                    <TimestampInput
                      key={`${segment.segmentId}-${segment.startMs}`}
                      valueMs={segment.startMs}
                      maxMs={maxDurationMs}
                      onCommit={(startMs) =>
                        updateSegment(segment.segmentId, {
                          startMs,
                          endMs: clampEnd(
                            segment.endMs,
                            startMs,
                            maxDurationMs,
                          ),
                        })
                      }
                    />
                    {detectedSpeakers.length > 0 ? (
                      <Select
                        value={
                          segment.speaker != null
                            ? String(segment.speaker)
                            : "none"
                        }
                        onValueChange={(value) =>
                          updateSegment(segment.segmentId, {
                            speaker:
                              value === "none" || value == null
                                ? null
                                : Number(value),
                          })
                        }
                      >
                        <SelectTrigger className="min-w-14 max-w-24 shrink-0">
                          <SelectValue>
                            {(value) =>
                              value === "none"
                                ? "—"
                                : (speakerLabels[String(value)] ?? `S${value}`)
                            }
                          </SelectValue>
                        </SelectTrigger>
                        <SelectContent className="min-w-0">
                          <SelectItem value="none">—</SelectItem>
                          {detectedSpeakers.map((speaker) => (
                            <SelectItem key={speaker} value={String(speaker)}>
                              {speakerLabels[String(speaker)] ?? `S${speaker}`}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    ) : null}
                    <Textarea
                      value={segment.text}
                      onChange={(event) =>
                        updateSegment(segment.segmentId, {
                          text: event.target.value,
                        })
                      }
                      rows={1}
                      className="min-h-8 resize-none py-1 text-sm"
                    />
                    {matches ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="shrink-0 text-muted-foreground"
                        onClick={() => replaceOne(segment.segmentId)}
                        title="Replace in this segment"
                      >
                        <Icon icon={Refresh01Icon} />
                        <span className="sr-only">Replace in this segment</span>
                      </Button>
                    ) : null}
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="shrink-0 text-muted-foreground"
                      onClick={() => insertSegmentAfter(segment.segmentId)}
                      title="Insert segment below"
                    >
                      <Icon icon={Add01Icon} />
                      <span className="sr-only">Insert segment below</span>
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="shrink-0 text-muted-foreground"
                      onClick={() => deleteSegment(segment.segmentId)}
                      title="Delete segment"
                    >
                      <Icon icon={Delete02Icon} />
                      <span className="sr-only">Delete segment</span>
                    </Button>
                  </li>
                );
              })}
            </ol>
            <div className="flex justify-center pt-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={addSegment}
              >
                <Icon icon={Add01Icon} />
                Add segment
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

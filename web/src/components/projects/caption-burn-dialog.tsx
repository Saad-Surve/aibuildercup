"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ClosedCaptionIcon,
  Delete02Icon,
  FileVideoIcon,
  Loading03Icon,
  SparklesIcon,
} from "@hugeicons/core-free-icons";
import { toast } from "sonner";

import { Icon } from "@/components/common/icon";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ApiError } from "@/lib/api-client";
import {
  CAPTION_BACKGROUND_OPTIONS,
  CAPTION_FONT_OPTIONS,
  CAPTION_POSITION_OPTIONS,
  DEFAULT_CAPTION_STYLE,
  previewTextStyle,
} from "@/lib/captions";
import {
  createCaptionRender,
  deleteCaptionRender,
  formatBytes,
  getJob,
  listCaptionPresets,
  listCaptionRenders,
} from "@/lib/projects";
import type { CaptionRender, CaptionStyle } from "@/lib/types";

const SAMPLE_LINES = ["This is how your captions", "will look on the video"];

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}

function slugify(value: string | undefined, fallback: string): string {
  const source = value?.trim() || fallback;
  return (
    source
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 60) || "captions"
  );
}

function statusVariant(status: CaptionRender["status"]) {
  if (status === "ready") return "default" as const;
  if (status === "failed") return "destructive" as const;
  return "secondary" as const;
}

/** Static approximation of the burned caption, styled with the chosen options. */
function StylePreview({ style }: { style: CaptionStyle }) {
  const containerRef = useRef<HTMLDivElement>(null);
  // The backend authors sizes against a 1080-tall reference frame, so the preview scales
  // its own height over 1080 too. That keeps the px values in the controls faithful and
  // the caption at the true distance from the edge.
  const [scale, setScale] = useState(0.3);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      const height = entries[0]?.contentRect.height ?? 0;
      if (height > 0) setScale(height / 1080);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const textStyle = previewTextStyle(style);
  const fontSize = Math.max(6, Math.round(style.fontSize * scale));
  const margin = Math.round(style.marginV * scale);
  const justify =
    style.position === "top"
      ? "justify-start"
      : style.position === "middle"
        ? "justify-center"
        : "justify-end";

  return (
    <div
      ref={containerRef}
      className="relative aspect-video w-full overflow-hidden rounded-xl border bg-gradient-to-br from-slate-800 via-slate-900 to-black"
    >
      {/* Column direction so justify-* moves along the vertical axis (top/middle/bottom). */}
      <div
        className={`absolute inset-0 flex flex-col items-center ${justify} px-4`}
        style={{
          paddingTop: style.position === "top" ? margin : undefined,
          paddingBottom: style.position === "bottom" ? margin : undefined,
        }}
      >
        <div className="space-y-1 text-center" style={{ fontSize }}>
          {SAMPLE_LINES.map((line, lineIndex) => (
            <div key={line} style={textStyle}>
              {style.highlightEnabled
                ? renderKaraoke(line, lineIndex === 0, style)
                : line}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/** First preview line mimics a half-sung karaoke cue. */
function renderKaraoke(line: string, active: boolean, style: CaptionStyle) {
  if (!active) return line;
  const words = line.split(" ");
  const sung = Math.ceil(words.length / 2);
  return words.map((word, index) => (
    <span
      key={`${word}-${index}`}
      style={{ color: index < sung ? style.highlightColor : style.textColor }}
    >
      {word}
      {index < words.length - 1 ? " " : ""}
    </span>
  ));
}

function RangeControl({
  label,
  value,
  min,
  max,
  step = 1,
  suffix,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  suffix?: string;
  onChange: (value: number) => void;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <Label className="text-xs text-muted-foreground">{label}</Label>
        <span className="tabular text-xs text-muted-foreground">
          {value}
          {suffix}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-muted accent-primary"
      />
    </div>
  );
}

function ColorControl({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-2">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      <div className="flex items-center gap-2">
        <Input
          value={value}
          onChange={(event) => onChange(event.target.value.toUpperCase())}
          className="h-8 w-24 font-mono text-xs uppercase"
          maxLength={7}
        />
        <input
          type="color"
          value={value}
          onChange={(event) => onChange(event.target.value.toUpperCase())}
          className="size-8 cursor-pointer rounded-md border bg-transparent"
          aria-label={label}
        />
      </div>
    </div>
  );
}

function ToggleControl({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-2">
      <span className="text-xs text-muted-foreground">{label}</span>
      <Checkbox
        checked={checked}
        onCheckedChange={(value) => onChange(Boolean(value))}
      />
    </label>
  );
}

export function CaptionBurnPanel({
  projectId,
  projectName,
  transcriptVersion,
  enabled = true,
  onClose,
}: {
  projectId: string;
  projectName?: string;
  transcriptVersion?: number | null;
  /** Whether the panel's queries should run (false while a dialog is closed). */
  enabled?: boolean;
  /** Renders a Close button when provided (dialog mode). */
  onClose?: () => void;
}) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<CaptionStyle | null>(null);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const notifiedJob = useRef<string | null>(null);

  const presetsQuery = useQuery({
    queryKey: ["caption-presets"],
    queryFn: listCaptionPresets,
    enabled,
    staleTime: Infinity,
    retry: false,
  });

  const rendersQuery = useQuery({
    queryKey: ["caption-renders", projectId],
    queryFn: () => listCaptionRenders(projectId),
    enabled,
    // Keep refreshing while a render is in flight; stop once none are.
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some(
        (item) => item.status === "queued" || item.status === "rendering",
      )
        ? 3000
        : false;
    },
    retry: false,
  });

  const renders = useMemo(
    () => rendersQuery.data?.items ?? [],
    [rendersQuery.data],
  );
  const activeRender = renders.find(
    (item) => item.status === "queued" || item.status === "rendering",
  );
  const jobId = activeJobId ?? activeRender?.jobId ?? null;

  const jobQuery = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId as string),
    enabled: enabled && Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "succeeded" ||
        status === "failed" ||
        status === "cancelled"
        ? false
        : 2000;
    },
    retry: false,
  });

  // `selected === null` follows the first preset, so presets configure the preview
  // without an effect; any edit or preset click pins the style.
  const presets = presetsQuery.data?.items ?? [];
  const style = selected ?? presets[0]?.style ?? DEFAULT_CAPTION_STYLE;
  const presetId = style.preset;

  const jobStatus = jobQuery.data?.status;
  const jobTerminal =
    jobStatus === "succeeded" ||
    jobStatus === "failed" ||
    jobStatus === "cancelled";

  // Announce the outcome once per job. No state here: the renders list refreshes on
  // its own interval and a terminal status stops the job polling.
  useEffect(() => {
    if (!jobId || !jobStatus || !jobTerminal) return;
    if (notifiedJob.current === jobId) return;
    notifiedJob.current = jobId;
    if (jobStatus === "succeeded") {
      toast.success("Captioned video ready");
    } else if (jobStatus === "failed") {
      const message =
        (jobQuery.data?.error?.message as string | undefined) ??
        "The render failed.";
      toast.error(message);
    }
  }, [jobId, jobStatus, jobTerminal, jobQuery.data]);

  const createMutation = useMutation({
    mutationFn: () =>
      createCaptionRender(projectId, {
        style,
        transcriptVersion: transcriptVersion ?? null,
        fileName: projectName ?? null,
      }),
    onSuccess: (result) => {
      setError(null);
      setActiveJobId(result.jobId);
      void queryClient.invalidateQueries({
        queryKey: ["caption-renders", projectId],
      });
      toast.success("Rendering captions…");
    },
    onError: (caught) =>
      setError(errorMessage(caught, "Could not start the render.")),
  });

  const deleteMutation = useMutation({
    mutationFn: (captionRenderId: string) =>
      deleteCaptionRender(projectId, captionRenderId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["caption-renders", projectId],
      });
      toast.success("Render deleted");
    },
    onError: (caught) =>
      toast.error(errorMessage(caught, "Could not delete the render.")),
  });

  function applyPreset(id: string) {
    const preset = presets.find((item) => item.id === id);
    if (preset) setSelected(preset.style);
  }

  function update(patch: Partial<CaptionStyle>) {
    setSelected({ ...style, ...patch });
  }
  const isRendering =
    createMutation.isPending ||
    Boolean(activeRender) ||
    Boolean(activeJobId && !jobTerminal);
  const percent = jobQuery.data?.progress.percent ?? 0;
  const jobMessage = jobQuery.data?.progress.message ?? "Queued";

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 gap-5 md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className="space-y-4">
          <StylePreview style={style} />

          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">Preset</Label>
            <div className="flex flex-wrap gap-1.5">
              {presets.map((preset) => (
                <Button
                  key={preset.id}
                  type="button"
                  size="sm"
                  variant={preset.id === presetId ? "default" : "outline"}
                  onClick={() => applyPreset(preset.id)}
                >
                  {preset.label}
                </Button>
              ))}
              {presetsQuery.isLoading ? (
                <span className="text-xs text-muted-foreground">Loading…</span>
              ) : null}
            </div>
            <p className="text-xs text-muted-foreground">
              {presets.find((item) => item.id === presetId)?.description ??
                "Pick a starting look, then fine-tune it."}
            </p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Font</Label>
              <Select
                value={style.fontFamily}
                onValueChange={(value) =>
                  update({ fontFamily: value as CaptionStyle["fontFamily"] })
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CAPTION_FONT_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Position</Label>
              <Select
                value={style.position}
                onValueChange={(value) =>
                  update({ position: value as CaptionStyle["position"] })
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CAPTION_POSITION_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <RangeControl
            label="Font size"
            value={style.fontSize}
            min={24}
            max={110}
            onChange={(value) => update({ fontSize: value })}
          />
          <RangeControl
            label="Distance from edge"
            value={style.marginV}
            min={0}
            max={400}
            suffix="px"
            onChange={(value) => update({ marginV: value })}
          />
          <RangeControl
            label="Chars per line"
            value={style.maxCharsPerLine}
            min={16}
            max={56}
            onChange={(value) => update({ maxCharsPerLine: value })}
          />

          <div className="grid grid-cols-2 gap-x-4 gap-y-2">
            <ToggleControl
              label="Bold"
              checked={style.bold}
              onChange={(value) => update({ bold: value })}
            />
            <ToggleControl
              label="Italic"
              checked={style.italic}
              onChange={(value) => update({ italic: value })}
            />
            <ToggleControl
              label="Uppercase"
              checked={style.uppercase}
              onChange={(value) => update({ uppercase: value })}
            />
            <ToggleControl
              label="Speaker names"
              checked={style.speakerLabels}
              onChange={(value) => update({ speakerLabels: value })}
            />
            <ToggleControl
              label="Karaoke highlight"
              checked={style.highlightEnabled}
              onChange={(value) => update({ highlightEnabled: value })}
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Background</Label>
            <Select
              value={style.background}
              onValueChange={(value) =>
                update({ background: value as CaptionStyle["background"] })
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CAPTION_BACKGROUND_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-3 rounded-lg border p-3">
            <ColorControl
              label="Text"
              value={style.textColor}
              onChange={(value) => update({ textColor: value })}
            />
            {style.highlightEnabled ? (
              <ColorControl
                label="Highlight"
                value={style.highlightColor}
                onChange={(value) => update({ highlightColor: value })}
              />
            ) : null}
            {style.background === "outline" ? (
              <>
                <ColorControl
                  label="Outline"
                  value={style.outlineColor}
                  onChange={(value) => update({ outlineColor: value })}
                />
                <RangeControl
                  label="Outline width"
                  value={style.outlineWidth}
                  min={0}
                  max={10}
                  onChange={(value) => update({ outlineWidth: value })}
                />
              </>
            ) : null}
            {style.background === "box" ? (
              <>
                <ColorControl
                  label="Box colour"
                  value={style.backgroundColor}
                  onChange={(value) => update({ backgroundColor: value })}
                />
                <RangeControl
                  label="Box opacity"
                  value={style.backgroundOpacity}
                  min={0}
                  max={100}
                  suffix="%"
                  onChange={(value) => update({ backgroundOpacity: value })}
                />
              </>
            ) : null}
            <RangeControl
              label="Shadow"
              value={style.shadow}
              min={0}
              max={10}
              onChange={(value) => update({ shadow: value })}
            />
          </div>
        </div>
      </div>

      {isRendering ? (
        <div className="space-y-2 rounded-lg border bg-muted/40 p-3">
          <div className="flex items-center gap-2 text-sm">
            <Icon icon={Loading03Icon} className="animate-spin text-signal" />
            <span>{jobMessage}</span>
            <span className="ml-auto tabular text-muted-foreground">
              {percent}%
            </span>
          </div>
          <Progress value={percent} />
        </div>
      ) : null}

      {error ? (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      ) : null}

      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">
          {style.fontFamily} · {style.background} ·{" "}
          {style.highlightEnabled ? "karaoke" : "static"}
        </p>
        <div className="flex items-center gap-2">
          {onClose ? (
            <Button type="button" variant="outline" onClick={onClose}>
              Close
            </Button>
          ) : null}
          <Button
            type="button"
            onClick={() => createMutation.mutate()}
            disabled={isRendering || createMutation.isPending}
          >
            <Icon
              icon={isRendering ? Loading03Icon : SparklesIcon}
              className={isRendering ? "animate-spin" : undefined}
            />
            {isRendering ? "Rendering…" : "Render captions"}
          </Button>
        </div>
      </div>

      {renders.length > 0 ? (
        <div className="space-y-2 border-t pt-4">
          <Label className="text-xs text-muted-foreground">
            Rendered videos
          </Label>
          <ul className="space-y-2">
            {renders.map((render) => (
              <li
                key={render.captionRenderId}
                className="flex items-center gap-3 rounded-lg border p-2.5"
              >
                <Icon
                  icon={FileVideoIcon}
                  className="shrink-0 text-muted-foreground"
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm">
                      {render.fileName ?? "Captioned video"}
                    </span>
                    <Badge variant={statusVariant(render.status)}>
                      {render.status}
                    </Badge>
                  </div>
                  <p className="tabular text-xs text-muted-foreground">
                    {render.status === "ready"
                      ? `${render.width}×${render.height} · ${formatBytes(
                          render.sizeBytes,
                        )} · ${Math.round(render.durationMs / 1000)}s`
                      : (render.error?.message ?? "Working…")}
                  </p>
                </div>
                {render.status === "ready" && render.downloadUrl ? (
                  <Button
                    size="sm"
                    variant="outline"
                    render={
                      <a
                        href={render.downloadUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label="Download captioned video"
                        download={`${slugify(
                          render.fileName ?? projectName,
                          "captions",
                        )}-${render.captionRenderId.slice(0, 6)}.mp4`}
                      />
                    }
                  >
                    <Icon icon={FileVideoIcon} />
                    Download
                  </Button>
                ) : null}
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label="Delete render"
                  disabled={deleteMutation.isPending}
                  onClick={() => deleteMutation.mutate(render.captionRenderId)}
                >
                  <Icon icon={Delete02Icon} />
                </Button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

/**
 * Dialog wrapper around {@link CaptionBurnPanel}, for opening the caption
 * studio modally. The Burn Captions module renders the panel inline instead.
 */
export function CaptionBurnDialog({
  projectId,
  projectName,
  transcriptVersion,
  open,
  onOpenChange,
}: {
  projectId: string;
  projectName?: string;
  transcriptVersion?: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Icon icon={ClosedCaptionIcon} className="text-muted-foreground" />
            Burn captions onto the video
          </DialogTitle>
          <DialogDescription>
            Render a new MP4 with styled captions from this transcript. The
            original file is never changed.
          </DialogDescription>
        </DialogHeader>
        <CaptionBurnPanel
          projectId={projectId}
          projectName={projectName}
          transcriptVersion={transcriptVersion}
          enabled={open}
          onClose={() => onOpenChange(false)}
        />
      </DialogContent>
    </Dialog>
  );
}

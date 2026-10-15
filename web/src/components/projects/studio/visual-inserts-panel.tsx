"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import { getJob } from "@/lib/projects";
import {
  deleteVisualInsert,
  listVisualInserts,
  renderVisualInsert,
  suggestVisualInserts,
  type VisualInsert,
} from "@/lib/packaging";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";

const kindLabel = {
  chart: "Comparison chart",
  callout: "Context card",
  broll: "Illustrative footage",
};

function timestamp(ms: number) {
  const seconds = Math.floor(ms / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function InsertCard({
  projectId,
  insert,
  remaining,
}: {
  projectId: string;
  insert: VisualInsert;
  remaining: number;
}) {
  const readOnly = useReadOnly();
  const client = useQueryClient();
  const [prompt, setPrompt] = useState(insert.prompt);
  const [aspect, setAspect] = useState<"16:9" | "9:16">(insert.aspectRatio);
  const active = insert.status === "queued" || insert.status === "rendering";
  const refresh = () =>
    client.invalidateQueries({ queryKey: ["visual-inserts", projectId] });
  const render = useMutation({
    mutationFn: () =>
      renderVisualInsert(projectId, insert.insertId, {
        ...(insert.kind === "broll" ? { prompt } : {}),
        aspectRatio: aspect,
        allowPaidGeneration: insert.kind === "broll",
      }),
    onSuccess: refresh,
    onError: (error) => toast.error(error.message),
  });
  const remove = useMutation({
    mutationFn: () => deleteVisualInsert(projectId, insert.insertId),
    onSuccess: refresh,
    onError: (error) => toast.error(error.message),
  });
  const maximum = Math.max(1, ...insert.chart.map((point) => point.value));
  const disabled = readOnly || active || render.isPending || remove.isPending;
  const needsNewDirection = insert.kind === "broll" && !insert.visualStyle;
  return (
    <article className="overflow-hidden rounded-xl border bg-card">
      {insert.previewUrl ? (
        // Silent visual inserts have no dialogue or caption track.
        // oxlint-disable-next-line jsx-a11y/media-has-caption
        <video
          src={insert.previewUrl}
          controls
          preload="metadata"
          playsInline
          aria-label={insert.headline}
          className="aspect-video w-full bg-[#191a2c] object-contain"
        />
      ) : (
        <div className="flex min-h-48 flex-col justify-center gap-4 bg-[#191a2c] p-6 text-[#f3f1fa]">
          <p className="text-lg font-semibold leading-tight">
            {insert.headline}
          </p>
          {insert.kind === "chart" ? (
            <div className="space-y-3">
              {insert.chart.map((point) => (
                <div key={point.label} className="space-y-1">
                  <div className="flex justify-between gap-3 text-xs">
                    <span>{point.label}</span>
                    <span className="tabular text-[#7ddcd2]">
                      {point.value.toLocaleString("en-US", {
                        maximumFractionDigits: 20,
                      })}
                      {insert.chartUnit.startsWith("%") ? "" : " "}
                      {insert.chartUnit}
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-white/10">
                    <div
                      className="h-full rounded-full bg-[#7ddcd2]"
                      style={{ width: `${(point.value / maximum) * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm leading-relaxed text-[#b2b4cb]">
              {insert.body || insert.sourceQuote}
            </p>
          )}
          <span className="text-[10px] tracking-wider text-[#b2b4cb] uppercase">
            6-second insert
          </span>
        </div>
      )}
      <div className="space-y-4 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">{kindLabel[insert.kind]}</Badge>
          <button
            type="button"
            className="font-mono text-xs text-muted-foreground underline underline-offset-4"
            aria-label={`Seek source video to ${timestamp(insert.sourceStartMs)}`}
            onClick={() =>
              window.dispatchEvent(
                new CustomEvent("creator-studio:seek", {
                  detail: { projectId, seconds: insert.sourceStartMs / 1000 },
                }),
              )
            }
          >
            {timestamp(insert.sourceStartMs)}–{timestamp(insert.sourceEndMs)}
          </button>
          {insert.status === "ready" ? (
            <Badge variant="outline">Ready</Badge>
          ) : null}
        </div>
        <p className="text-sm">{insert.rationale}</p>
        <blockquote className="border-l-2 border-signal/50 pl-3 text-xs leading-relaxed text-muted-foreground">
          “{insert.sourceQuote}”
        </blockquote>
        {insert.kind === "broll" && insert.visualStyle ? (
          <div className="space-y-2 rounded-lg border bg-muted/30 p-3">
            {insert.styleReferenceUrl ? (
              <Image
                src={insert.styleReferenceUrl}
                alt={`Source video reference at ${timestamp(insert.styleReferenceTimestampMs ?? insert.sourceStartMs)}`}
                width={1280}
                height={720}
                unoptimized
                className="max-h-40 w-full rounded object-contain"
              />
            ) : null}
            <p className="text-xs font-medium">
              {insert.generationMode === "image-to-video"
                ? "Starts from this frame"
                : "Matches this video's look"}
            </p>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {insert.visualStyle.summary}
            </p>
            <details className="text-xs text-muted-foreground">
              <summary className="cursor-pointer">Visual direction</summary>
              <dl className="mt-2 space-y-2">
                {(
                  [
                    ["Color", insert.visualStyle.palette],
                    ["Light", insert.visualStyle.lighting],
                    ["Framing", insert.visualStyle.composition],
                    ["Texture", insert.visualStyle.texture],
                    ["Motion", insert.visualStyle.motion],
                    ["Setting", insert.visualStyle.setting],
                  ] as const
                ).map(([label, value]) => (
                  <div key={label}>
                    <dt className="font-medium">{label}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-3">{insert.conditioningReason}</p>
            </details>
          </div>
        ) : null}
        {needsNewDirection && insert.status !== "ready" ? (
          <p role="status" className="text-xs text-muted-foreground">
            Suggest new inserts to analyze and match this video’s visual style.
          </p>
        ) : null}
        {insert.kind === "chart" ? (
          <details className="text-xs text-muted-foreground">
            <summary className="cursor-pointer">
              Sources for chart values
            </summary>
            <ul className="mt-2 space-y-2">
              {insert.chart.map((point) => (
                <li key={point.label}>
                  {point.label}: {point.value}
                  {insert.chartUnit} — “{point.sourceQuote}”
                </li>
              ))}
            </ul>
          </details>
        ) : null}
        {insert.stale ? (
          <p role="status" className="text-xs text-sev-medium">
            This suggestion belongs to an earlier video or transcript. Suggest
            new inserts to render.
          </p>
        ) : null}
        {insert.error ? (
          <p role="alert" className="text-xs text-destructive">
            {insert.error}
          </p>
        ) : null}
        {insert.kind === "broll" && insert.status !== "ready" ? (
          <div className="space-y-1.5">
            <Label htmlFor={`prompt-${insert.insertId}`} className="text-xs">
              Footage direction
            </Label>
            <Textarea
              id={`prompt-${insert.insertId}`}
              value={prompt}
              maxLength={2000}
              rows={4}
              disabled={disabled || insert.status === "failed"}
              onChange={(event) => setPrompt(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              {insert.generationMode === "image-to-video"
                ? "Describe motion; the source frame supplies the look. "
                : insert.visualStyle
                  ? "Your video's style is applied. "
                  : ""}
              AI-generated illustration. Review it before adding it to your
              video.
            </p>
          </div>
        ) : null}
        {insert.status !== "ready" ? (
          <fieldset
            disabled={disabled || insert.status === "failed"}
            className="flex items-center gap-3 text-xs text-muted-foreground"
          >
            <legend className="sr-only">Clip aspect ratio</legend>
            {(["16:9", "9:16"] as const).map((value) => (
              <label key={value} className="flex items-center gap-1.5">
                <input
                  type="radio"
                  name={`aspect-${insert.insertId}`}
                  value={value}
                  checked={aspect === value}
                  disabled={
                    insert.generationMode === "image-to-video" &&
                    value !== insert.aspectRatio
                  }
                  onChange={() => setAspect(value)}
                />
                {value === "16:9" ? "Landscape" : "Portrait"}
              </label>
            ))}
          </fieldset>
        ) : null}
        <div className="flex flex-wrap items-center gap-2">
          {insert.status === "ready" && insert.previewUrl ? (
            <Button
              variant="outline"
              render={
                <a
                  aria-label="Download MP4"
                  href={insert.previewUrl}
                  download={`visual-insert-${insert.insertId}.mp4`}
                  target="_blank"
                  rel="noreferrer"
                />
              }
            >
              Download MP4
            </Button>
          ) : (
            <Button
              disabled={
                disabled ||
                !insert.canRetry ||
                (needsNewDirection && insert.status !== "failed") ||
                insert.stale ||
                (insert.kind === "broll" && !prompt.trim()) ||
                (insert.kind === "broll" &&
                  remaining === 0 &&
                  insert.status !== "failed")
              }
              title={readOnly ? READ_ONLY_REASON : undefined}
              onClick={() => render.mutate()}
            >
              {active || render.isPending ? <Spinner /> : null}
              {active || render.isPending
                ? "Rendering…"
                : insert.status === "failed"
                  ? insert.canRetry
                    ? "Resume"
                    : "Unavailable"
                  : insert.kind === "broll"
                    ? `Generate footage · ≤$${insert.estimatedCostUsd.toFixed(2)}`
                    : "Create graphic"}
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            disabled={disabled}
            onClick={() => remove.mutate()}
          >
            Delete
          </Button>
        </div>
      </div>
    </article>
  );
}

export function VisualInsertsPanel({ projectId }: { projectId: string }) {
  const client = useQueryClient();
  const readOnly = useReadOnly();
  const [brief, setBrief] = useState("");
  const [history, setHistory] = useState(true);
  const inserts = useQuery({
    queryKey: ["visual-inserts", projectId],
    queryFn: () => listVisualInserts(projectId),
    refetchInterval: (query) =>
      query.state.data?.items.some(
        (item) => item.status === "queued" || item.status === "rendering",
      )
        ? 3000
        : false,
  });
  const jobId = inserts.data?.suggestionJobId;
  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) =>
      query.state.data?.status === "queued" ||
      query.state.data?.status === "running"
        ? 3000
        : false,
  });
  useEffect(() => {
    if (job.data?.status === "succeeded" || job.data?.status === "failed") {
      void client.invalidateQueries({
        queryKey: ["visual-inserts", projectId],
      });
    }
  }, [job.data?.status, projectId, client]);
  const suggest = useMutation({
    mutationFn: () =>
      suggestVisualInserts(projectId, { brief, useCreatorHistory: history }),
    onSuccess: () =>
      client.invalidateQueries({ queryKey: ["visual-inserts", projectId] }),
    onError: (error) => toast.error(error.message),
  });
  const busy =
    suggest.isPending ||
    job.data?.status === "queued" ||
    job.data?.status === "running";
  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <Label htmlFor="insert-brief">
          What would help the viewer? (optional)
        </Label>
        <Input
          id="insert-brief"
          value={brief}
          maxLength={2000}
          disabled={readOnly || busy}
          placeholder="Show the process, explain a term, compare the numbers"
          onChange={(event) => setBrief(event.target.value)}
        />
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <Checkbox
            aria-label="Match my creator library when available"
            checked={history}
            disabled={readOnly || busy}
            onCheckedChange={(checked) => setHistory(checked === true)}
          />
          Match my creator library when available
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button
          disabled={readOnly || busy || inserts.isPending}
          title={readOnly ? READ_ONLY_REASON : undefined}
          onClick={() => suggest.mutate()}
        >
          {busy ? <Spinner /> : null}
          {busy ? "Finding moments…" : "Suggest visual inserts"}
        </Button>
        {inserts.data ? (
          <span className="text-xs text-muted-foreground">
            {inserts.data.paidRendersRemaining} AI footage clips left for this
            project
          </span>
        ) : null}
      </div>
      <p className="text-xs text-muted-foreground">
        Suggestions use the video and transcript. Footage is generated only when
        you choose it. Download a clip to add in your editor.
      </p>
      {inserts.error ? (
        <p role="alert" className="text-sm text-destructive">
          {inserts.error.message}
        </p>
      ) : null}
      {job.data?.status === "failed" ? (
        <p role="alert" className="text-sm text-destructive">
          {String(job.data.error?.message ?? "Suggestions failed. Try again.")}
        </p>
      ) : null}
      {inserts.isPending ? (
        <p className="text-sm text-muted-foreground">Loading visual inserts…</p>
      ) : null}
      {!inserts.isPending && !inserts.error && !inserts.data?.items.length ? (
        <div className="rounded-lg border border-dashed p-6 text-sm text-muted-foreground">
          Find the moments where a chart, an explanation, or an illustrative
          shot would make this video clearer.
        </div>
      ) : null}
      <div className="grid gap-5 xl:grid-cols-2">
        {inserts.data?.items.map((insert) => (
          <InsertCard
            key={insert.insertId}
            projectId={projectId}
            insert={insert}
            remaining={inserts.data.paidRendersRemaining}
          />
        ))}
      </div>
    </div>
  );
}

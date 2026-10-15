"use client";

import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { ReviewComparison } from "@/components/projects/review-comparison";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  dimensionLabel,
  formatDurationMs,
  listAnalysisRuns,
  startAnalysis,
} from "@/lib/analysis";
import {
  activateRevision,
  getDownloadUrl,
  getJob,
  listAssets,
} from "@/lib/projects";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";
import { listVisualInserts } from "@/lib/packaging";
import {
  discardRoughCut,
  downloadRoughCutPlan,
  getRoughCutPlan,
  getSourceCaptions,
  previewRoughCutPlan,
  renderRoughCut,
} from "@/lib/rough-cut";
import { ANALYSIS_DIMENSIONS } from "@/lib/types";
import type {
  Asset,
  Project,
  RoughCutMetadata,
  RoughCutPlan,
  RoughCutAccepted,
} from "@/lib/types";

export function RoughCutModule({
  project,
  onJobId,
  onReview,
}: {
  project: Project;
  onJobId: (id: string) => void;
  onReview: () => void;
}) {
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const runs = useQuery({
    queryKey: ["analysis-runs", project.projectId],
    queryFn: () => listAnalysisRuns(project.projectId),
  });
  const completed =
    runs.data?.items.filter(
      (run) => run.status === "ready" || run.status === "partial_failure",
    ) ?? [];
  // Reviews of the active source come first, so a cut's own re-review never becomes the
  // default base for another cut.
  const eligible = [
    ...completed.filter((run) => run.sourceAssetId === project.sourceAssetId),
    ...completed.filter((run) => run.sourceAssetId !== project.sourceAssetId),
  ];
  const runId =
    eligible.find((run) => run.analysisRunId === selectedRun)?.analysisRunId ??
    eligible[0]?.analysisRunId;
  const plan = useQuery({
    queryKey: ["rough-cut-plan", project.projectId, runId],
    queryFn: () => getRoughCutPlan(project.projectId, runId!),
    enabled: Boolean(runId),
    retry: false,
  });
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-medium tracking-widest text-muted-foreground uppercase">
            The edit room
          </p>
          <h2 className="mt-1 font-heading text-3xl font-semibold tracking-tight">
            Rough cut
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Your accepted edits, brought to the timeline. Preview first. You
            decide what stays.
          </p>
        </div>
        {eligible.length > 0 && (
          <label className="space-y-1 text-xs text-muted-foreground">
            Source review
            <select
              className="block max-w-full rounded-lg border bg-background px-3 py-2 text-sm text-foreground focus-visible:ring-2 focus-visible:ring-ring"
              value={runId}
              onChange={(event) => setSelectedRun(event.target.value)}
            >
              {eligible.map((run, index) => (
                <option key={run.analysisRunId} value={run.analysisRunId}>
                  Review {eligible.length - index} ·{" "}
                  {new Date(run.createdAt).toLocaleDateString()}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      {(runs.isLoading || plan.isLoading) && (
        <Skeleton className="h-80 w-full" />
      )}
      {(runs.error || plan.error) && (
        <p role="alert" className="text-sm text-destructive">
          {(runs.error ?? plan.error)?.message}
        </p>
      )}
      {!runs.isLoading && !runs.error && !runId && (
        <Card>
          <CardContent className="space-y-3 py-8">
            <h3 className="font-medium">Start with a review</h3>
            <p className="text-sm text-muted-foreground">
              Run a review, then accept or revise the findings you want in your
              edit plan.
            </p>
            <Button variant="outline" onClick={onReview}>
              Open review
            </Button>
          </CardContent>
        </Card>
      )}
      {plan.data && runId && (
        <CutEditor
          key={runId}
          project={project}
          initial={plan.data}
          sourceTranscriptId={
            eligible.find((run) => run.analysisRunId === runId)?.transcriptId
          }
          onJobId={onJobId}
          onReview={onReview}
        />
      )}
    </div>
  );
}

function CutEditor({
  project,
  initial,
  sourceTranscriptId,
  onJobId,
  onReview,
}: {
  project: Project;
  initial: RoughCutPlan;
  sourceTranscriptId?: string;
  onJobId: (id: string) => void;
  onReview: () => void;
}) {
  const projectId = project.projectId;
  const runId = initial.analysisRunId;
  const readOnly = useReadOnly();
  const client = useQueryClient();
  const [selected, setSelected] = useState(initial.findingIds);
  const [labels, setLabels] = useState<Record<string, "cut" | "note">>({});
  const [insertIds, setInsertIds] = useState<string[]>([]);
  const [pending, setPending] = useState<RoughCutAccepted | null>(
    () =>
      client.getQueryData<RoughCutAccepted>([
        "rough-cut-preview",
        projectId,
        runId,
      ]) ?? null,
  );
  const [chosenAssetId, setChosenAssetId] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  const [fps, setFps] = useState(30);
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [reviewJobId, setReviewJobId] = useState<string | null>(null);
  const input = {
    findingIds: selected,
    labels: Object.fromEntries(
      Object.entries(labels).filter(([id]) => selected.includes(id)),
    ),
    insertIds,
  };
  const packaging = useQuery({
    queryKey: ["visual-inserts", projectId],
    queryFn: () => listVisualInserts(projectId),
  });
  const readyInserts =
    packaging.data?.items.filter(
      (insert) =>
        insert.status === "ready" &&
        insert.sourceAssetId === initial.sourceAssetId &&
        insert.transcriptId === sourceTranscriptId,
    ) ?? [];
  const preview = useQuery({
    queryKey: ["rough-cut-selection", projectId, runId, input],
    queryFn: () => previewRoughCutPlan(projectId, runId, input),
    retry: false,
  });
  const plan = preview.data ?? initial;
  const job = useQuery({
    queryKey: ["job", pending?.jobId],
    queryFn: () => getJob(pending!.jobId),
    enabled: Boolean(pending),
    refetchInterval: (query) =>
      ["succeeded", "failed", "cancelled"].includes(
        query.state.data?.status ?? "",
      )
        ? false
        : 1500,
    refetchIntervalInBackground: false,
  });
  const reviewJob = useQuery({
    queryKey: ["job", reviewJobId],
    queryFn: () => getJob(reviewJobId!),
    enabled: Boolean(reviewJobId),
    refetchInterval: (query) =>
      ["succeeded", "failed", "cancelled"].includes(
        query.state.data?.status ?? "",
      )
        ? false
        : 2000,
  });
  useEffect(() => {
    if (reviewJob.data?.status !== "succeeded") return;
    void client.invalidateQueries({ queryKey: ["analysis-runs", projectId] });
  }, [reviewJob.data?.status, client, projectId]);
  const runs = useQuery({
    queryKey: ["analysis-runs", projectId],
    queryFn: () => listAnalysisRuns(projectId),
  });
  const rendering = Boolean(
    pending &&
    !job.error &&
    (!job.data ||
      job.data.status === "queued" ||
      job.data.status === "running"),
  );
  const assets = useQuery({
    queryKey: ["assets", projectId],
    queryFn: () => listAssets(projectId),
  });
  useEffect(() => {
    if (job.data?.status !== "succeeded") return;
    void client.invalidateQueries({ queryKey: ["assets", projectId] });
    void client.invalidateQueries({ queryKey: ["revisions", projectId] });
  }, [job.data?.status, client, projectId]);
  const cuts =
    assets.data?.items.filter(
      (a) => a.roughCut?.analysisRunId === runId && a.status === "ready",
    ) ?? [];
  const cut =
    cuts.find((a) => a.assetId === (pending?.assetId ?? chosenAssetId)) ??
    (!rendering ? cuts[0] : undefined);
  const original = assets.data?.items.find(
    (a) => a.assetId === initial.sourceAssetId,
  );
  const timeline =
    cut?.roughCut ?? (pending && rendering ? pending.plan : plan);
  const refresh = async () => {
    await Promise.all(
      [
        "assets",
        "revisions",
        "project",
        "transcript",
        "analysis-runs",
        "transcript-versions",
      ].map((key) => client.invalidateQueries({ queryKey: [key, projectId] })),
    );
  };
  const render = useMutation({
    mutationFn: () => renderRoughCut(projectId, runId, input),
    onSuccess: (result) => {
      setPending(result);
      client.setQueryData(["rough-cut-preview", projectId, runId], result);
      setConfirmDiscard(false);
      onJobId(result.jobId);
    },
    onError: (error) => toast.error(error.message),
  });
  const approve = useMutation({
    mutationFn: () => activateRevision(projectId, cut!.assetId),
    onSuccess: async () => {
      await refresh();
      toast.success("Rough cut approved as active version");
    },
    onError: (error) => toast.error(error.message),
  });
  const discard = useMutation({
    mutationFn: () => discardRoughCut(projectId, cut!.assetId),
    onSuccess: async () => {
      await refresh();
      setPending(null);
      client.removeQueries({
        queryKey: ["rough-cut-preview", projectId, runId],
      });
      setChosenAssetId(null);
      setConfirmDiscard(false);
      toast.success("Rough cut deleted");
    },
    onError: (error) => toast.error(error.message),
  });
  const rereview = useMutation({
    // Re-review with the base run's reviewers, or the comparison marks the rest unreviewed.
    mutationFn: () =>
      startAnalysis(projectId, {
        assetId: cut!.assetId,
        dimensions: [
          ...(runs.data?.items.find((run) => run.analysisRunId === runId)
            ?.requestedDimensions ?? ANALYSIS_DIMENSIONS),
        ],
      }),
    onSuccess: async (result) => {
      setReviewJobId(result.jobId);
      onJobId(result.jobId);
      await refresh();
      toast.success("Review started on this cut");
    },
    onError: (error) => toast.error(error.message),
  });
  const download = useMutation({
    mutationFn: (format: "cmx3600" | "markdown") =>
      downloadRoughCutPlan(projectId, runId, cut!.assetId, format, fps),
    onError: (error) => toast.error(error.message),
  });
  const isActive = cut?.assetId === project.sourceAssetId;
  const busy =
    rendering ||
    render.isPending ||
    approve.isPending ||
    discard.isPending ||
    rereview.isPending;
  const reviewing = Boolean(
    reviewJobId &&
    !reviewJob.error &&
    (!reviewJob.data ||
      reviewJob.data.status === "queued" ||
      reviewJob.data.status === "running"),
  );
  const saved = timeline.durationMsBefore - timeline.durationMsAfter;
  const cutReview = cut
    ? runs.data?.items
        .filter(
          (run) =>
            run.sourceAssetId === cut.assetId &&
            (run.status === "ready" || run.status === "partial_failure"),
        )
        .toSorted((a, b) => b.createdAt.localeCompare(a.createdAt))[0]
    : undefined;

  return (
    <div className="space-y-5">
      <Card className="overflow-hidden">
        <CardContent className="space-y-5 p-4 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-baseline gap-3 font-mono tabular-nums">
              <span className="text-xl text-muted-foreground">
                {formatDurationMs(timeline.durationMsBefore)}
              </span>
              <span aria-hidden className="text-muted-foreground">
                →
              </span>
              <span className="text-3xl font-semibold text-signal">
                {formatDurationMs(timeline.durationMsAfter)}
              </span>
              <span className="text-xs text-muted-foreground">
                {saved > 0 ? `${formatDurationMs(saved)} less` : "No cuts yet"}
              </span>
            </div>
            <span className="rounded-full border px-3 py-1 text-xs text-muted-foreground">
              {isActive
                ? "Active version"
                : cut
                  ? "Preview · awaiting your approval"
                  : "Edit plan · not rendered"}
            </span>
          </div>
          <ComparePlayers
            projectId={projectId}
            original={original}
            cut={cut}
            timeline={timeline}
          />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-muted-foreground">
              {collapsed ? "Kept footage" : "Source timeline"} ·{" "}
              <span className="text-destructive">
                striped spans are removed
              </span>
            </p>
            <div className="flex gap-1" role="group" aria-label="Timeline view">
              <Button
                size="sm"
                variant={!collapsed ? "secondary" : "ghost"}
                aria-pressed={!collapsed}
                onClick={() => setCollapsed(false)}
              >
                Original
              </Button>
              <Button
                size="sm"
                variant={collapsed ? "secondary" : "ghost"}
                aria-pressed={collapsed}
                onClick={() => setCollapsed(true)}
              >
                Cut view
              </Button>
            </div>
          </div>
          <CutTimeline timeline={timeline} collapsed={collapsed} />
          {rendering && (
            <div className="space-y-2" role="status" aria-live="polite">
              <div className="flex justify-between text-sm">
                <span>
                  {job.data?.progress.message ?? "Queuing your preview"}
                </span>
                <span className="font-mono">
                  {job.data?.progress.percent ?? 0}%
                </span>
              </div>
              <progress
                className="h-2 w-full accent-signal"
                max={100}
                value={job.data?.progress.percent ?? 0}
              />
            </div>
          )}
          {(job.data?.status === "failed" ||
            job.data?.status === "cancelled" ||
            job.error) && (
            <p role="alert" className="text-sm text-destructive">
              {job.error?.message ??
                (job.data?.error?.message as string) ??
                "Render cancelled. You can render another preview."}
            </p>
          )}
          {cut && (
            <div className="flex flex-wrap items-center gap-2 border-t pt-4">
              <Button
                disabled={readOnly || busy || isActive}
                title={readOnly ? READ_ONLY_REASON : undefined}
                onClick={() => approve.mutate()}
              >
                {approve.isPending
                  ? "Approving…"
                  : isActive
                    ? "Approved as active version"
                    : "Approve as active version"}
              </Button>
              <Button
                variant="outline"
                disabled={readOnly || busy || reviewing}
                onClick={() => rereview.mutate()}
              >
                {rereview.isPending
                  ? "Starting review…"
                  : reviewing
                    ? "Reviewing this cut…"
                    : "Re-review this cut"}
              </Button>
              <Button
                variant="destructive"
                disabled={readOnly || busy || isActive || reviewing}
                onClick={() =>
                  confirmDiscard ? discard.mutate() : setConfirmDiscard(true)
                }
              >
                {discard.isPending
                  ? "Deleting…"
                  : confirmDiscard
                    ? "Confirm delete"
                    : "Delete preview"}
              </Button>
              {confirmDiscard && (
                <Button
                  variant="ghost"
                  onClick={() => setConfirmDiscard(false)}
                >
                  Keep preview
                </Button>
              )}
            </div>
          )}
          {reviewJobId && (
            <div
              className="space-y-2 border-t pt-3 text-sm"
              role="status"
              aria-live="polite"
            >
              <p>
                {reviewing
                  ? (reviewJob.data?.progress.message ??
                    "Review queued on your preview")
                  : reviewJob.data?.status === "succeeded"
                    ? "The review of your preview is ready."
                    : (reviewJob.error?.message ??
                      String(
                        reviewJob.data?.error?.message ?? "Review cancelled.",
                      ))}
              </p>
              {reviewing && (
                <progress
                  aria-label="Preview review progress"
                  className="h-2 w-full accent-signal"
                  max={100}
                  value={reviewJob.data?.progress.percent ?? 0}
                />
              )}
              {reviewJob.data?.status === "succeeded" && isActive && (
                <Button size="sm" variant="outline" onClick={onReview}>
                  Open review results
                </Button>
              )}
            </div>
          )}
          {confirmDiscard && (
            <p className="text-xs text-muted-foreground">
              Deleting removes this preview, its transcript and completed
              reviews.
            </p>
          )}
          {cut && (
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                disabled={download.isPending}
                title="Opens in Premiere, Final Cut, and DaVinci Resolve"
                onClick={() => download.mutate("cmx3600")}
              >
                Download edit list (.edl)
              </Button>
              <Button
                variant="outline"
                disabled={download.isPending}
                onClick={() => download.mutate("markdown")}
              >
                Edit plan (.md)
              </Button>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                Timeline frame rate
                <select
                  aria-label="Timeline frame rate"
                  className="rounded-md border bg-background p-1 text-foreground"
                  value={fps}
                  onChange={(event) => setFps(Number(event.target.value))}
                >
                  {[24, 25, 30, 60].map((rate) => (
                    <option key={rate} value={rate}>
                      {rate} fps
                    </option>
                  ))}
                </select>
              </label>
              {cuts.length > 1 && (
                <label className="ml-auto flex items-center gap-2 text-xs">
                  Preview
                  <select
                    aria-label="Rendered preview"
                    className="rounded-md border bg-background p-1"
                    value={cut.assetId}
                    disabled={busy}
                    onChange={(event) => {
                      setPending(null);
                      client.removeQueries({
                        queryKey: ["rough-cut-preview", projectId, runId],
                      });
                      setChosenAssetId(event.target.value);
                      setConfirmDiscard(false);
                    }}
                  >
                    {cuts.map((asset) => (
                      <option key={asset.assetId} value={asset.assetId}>
                        Revision {asset.revision}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </div>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-4 sm:p-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h3 className="font-heading text-lg font-semibold">
                Decide what changes
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Cut removes footage. Note keeps it and adds an edit marker.
              </p>
            </div>
            <Button
              disabled={
                readOnly ||
                busy ||
                preview.isFetching ||
                Boolean(preview.error) ||
                plan.removedSpans.length === 0
              }
              title={readOnly ? READ_ONLY_REASON : undefined}
              onClick={() => render.mutate()}
            >
              {render.isPending || rendering
                ? "Rendering preview…"
                : "Render preview"}
            </Button>
          </div>
          {readOnly && (
            <p className="mt-3 text-xs text-muted-foreground">
              {READ_ONLY_REASON}
            </p>
          )}
          {initial.findings.length === 0 && (
            <div className="space-y-3 py-8">
              <p className="text-sm text-muted-foreground">
                Accept or revise findings in the review to build your first cut.
              </p>
              <Button variant="outline" onClick={onReview}>
                Choose findings in review
              </Button>
            </div>
          )}
          {preview.error && (
            <p role="alert" className="mt-3 text-sm text-destructive">
              {preview.error.message}
            </p>
          )}
          <div className="mt-4 divide-y">
            {initial.findings.map((finding) => {
              const updated =
                plan.findings.find(
                  (item) => item.findingId === finding.findingId,
                ) ?? finding;
              const chosen = selected.includes(finding.findingId);
              return (
                <div
                  key={finding.findingId}
                  className="flex items-start gap-3 py-4"
                >
                  <input
                    aria-label={`Include finding at ${formatDurationMs(finding.startMs)}`}
                    type="checkbox"
                    checked={chosen}
                    disabled={busy}
                    className="mt-1 size-4 accent-signal"
                    onChange={(event) =>
                      setSelected((prev) =>
                        event.target.checked
                          ? [...prev, finding.findingId]
                          : prev.filter((id) => id !== finding.findingId),
                      )
                    }
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="font-mono text-time">
                        {formatDurationMs(finding.startMs)}–
                        {formatDurationMs(finding.endMs)}
                      </span>
                      <span className="text-muted-foreground">
                        {dimensionLabel(finding.dimension)}
                      </span>
                    </div>
                    <p className="mt-1 text-sm leading-relaxed">
                      {finding.action}
                    </p>
                    <p
                      className={`mt-1 text-xs ${chosen && updated.skippedReason ? "text-destructive" : "text-muted-foreground"}`}
                    >
                      {chosen && updated.skippedReason
                        ? `Skipped: ${updated.skippedReason}`
                        : updated.labelReason}
                    </p>
                  </div>
                  <div
                    className="flex rounded-lg border p-0.5"
                    role="group"
                    aria-label={`Edit type at ${formatDurationMs(finding.startMs)}`}
                  >
                    {(["cut", "note"] as const).map((label) => (
                      <Button
                        key={label}
                        size="sm"
                        aria-pressed={
                          (labels[finding.findingId] ?? finding.label) === label
                        }
                        disabled={!chosen || busy}
                        variant={
                          (labels[finding.findingId] ?? finding.label) === label
                            ? "secondary"
                            : "ghost"
                        }
                        onClick={() =>
                          setLabels((prev) => ({
                            ...prev,
                            [finding.findingId]: label,
                          }))
                        }
                      >
                        {label === "cut" ? "Cut" : "Note"}
                      </Button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
          {initial.findings.length > 0 && (
            <p className="border-t pt-3 text-xs text-muted-foreground">
              {selected.length} selected · {plan.removedSpans.length} safe
              removal{plan.removedSpans.length === 1 ? "" : "s"} · Cuts snap to
              speech pauses. Very short or long cuts are skipped.
            </p>
          )}
          {readyInserts.length > 0 && (
            <fieldset className="mt-5 space-y-3 border-t pt-4">
              <legend className="px-1 text-sm font-medium">
                Add rendered packaging inserts
              </legend>
              <p className="text-xs text-muted-foreground">
                Overlays footage at its original moment, keeping its timing and
                audio.
              </p>
              {readyInserts.map((insert) => {
                const planned = plan.inserts.find(
                  (item) => item.insertId === insert.insertId,
                );
                return (
                  <label
                    key={insert.insertId}
                    className="flex items-start gap-3 text-sm"
                  >
                    <input
                      type="checkbox"
                      className="mt-1 size-4 accent-signal"
                      checked={insertIds.includes(insert.insertId)}
                      disabled={
                        busy ||
                        (!insertIds.includes(insert.insertId) &&
                          insertIds.length >= 8)
                      }
                      onChange={(event) =>
                        setInsertIds((prev) =>
                          event.target.checked
                            ? [...prev, insert.insertId]
                            : prev.filter((id) => id !== insert.insertId),
                        )
                      }
                    />
                    <span>
                      {insert.headline}
                      <span className="ml-2 font-mono text-xs text-muted-foreground">
                        {formatDurationMs(insert.sourceStartMs)}
                      </span>
                      {planned?.skippedReason && (
                        <span className="block text-xs text-destructive">
                          Skipped: {planned.skippedReason}
                        </span>
                      )}
                    </span>
                  </label>
                );
              })}
            </fieldset>
          )}
          {cut && (
            <p className="mt-2 text-xs text-muted-foreground">
              Changes apply to the next preview. Downloads and approval use the
              current preview.
            </p>
          )}
        </CardContent>
      </Card>
      {cutReview && (
        <section aria-label="Before and after review" className="space-y-2">
          <h3 className="text-sm font-medium">Before / after review</h3>
          <ReviewComparison
            projectId={projectId}
            baseRunId={runId}
            targetRunId={cutReview.analysisRunId}
          />
        </section>
      )}
    </div>
  );
}

function CutTimeline({
  timeline,
  collapsed,
}: {
  timeline: RoughCutMetadata;
  collapsed: boolean;
}) {
  const spans = [
    ...timeline.keptSegments.map((s) => ({
      start: s.sourceStartMs,
      end: s.sourceEndMs,
      removed: false,
    })),
    ...timeline.removedSpans.map((s) => ({
      start: s.startMs,
      end: s.endMs,
      removed: true,
    })),
  ].toSorted((a, b) => a.start - b.start);
  return (
    <div
      aria-label={`${collapsed ? "Cut" : "Original"} timeline: ${timeline.removedSpans.length} removed spans`}
      role="img"
      className="flex h-11 overflow-hidden rounded-md border bg-muted"
    >
      {spans.map((span) => (
        <div
          key={`${span.start}-${span.removed}`}
          title={`${span.removed ? "Removed" : "Kept"}: ${formatDurationMs(span.start)}–${formatDurationMs(span.end)}`}
          className={`flex min-w-0 items-center justify-center overflow-hidden border-r border-background/50 transition-[flex-grow,opacity] duration-700 motion-reduce:transition-none ${span.removed ? "bg-destructive/25 text-destructive" : "bg-signal/20 text-signal"}`}
          style={{
            flexBasis: 0,
            flexGrow: collapsed && span.removed ? 0 : span.end - span.start,
            opacity: collapsed && span.removed ? 0 : 1,
            backgroundImage: span.removed
              ? "repeating-linear-gradient(135deg, transparent, transparent 5px, currentColor 5px, currentColor 6px)"
              : undefined,
          }}
        >
          <span className="bg-background/80 px-1 font-mono text-[10px]">
            {formatDurationMs(span.start)}
          </span>
        </div>
      ))}
    </div>
  );
}

function ComparePlayers({
  projectId,
  original,
  cut,
  timeline,
}: {
  projectId: string;
  original?: Asset;
  cut?: Asset;
  timeline: RoughCutMetadata;
}) {
  const originalRef = useRef<HTMLVideoElement>(null);
  const cutRef = useRef<HTMLVideoElement>(null);
  const [sync, setSync] = useState(true);
  const source = useQuery({
    queryKey: ["rough-cut-video-url", projectId, original?.assetId],
    queryFn: () => getDownloadUrl(projectId, original!.assetId),
    enabled: Boolean(original),
    staleTime: 600000,
    refetchInterval: 600000,
  });
  const preview = useQuery({
    queryKey: ["rough-cut-video-url", projectId, cut?.assetId],
    queryFn: () => getDownloadUrl(projectId, cut!.assetId),
    enabled: Boolean(cut),
    staleTime: 600000,
    refetchInterval: 600000,
  });
  const sourceCaptions = useQuery({
    queryKey: ["source-captions", projectId, original?.assetId],
    queryFn: () => getSourceCaptions(projectId, original!.assetId),
    enabled: Boolean(original),
  });
  const captions = useQuery({
    queryKey: ["source-captions", projectId, cut?.assetId],
    queryFn: () => getSourceCaptions(projectId, cut!.assetId),
    enabled: Boolean(cut),
  });
  function align() {
    if (!sync || !cutRef.current || !originalRef.current) return;
    const outputMs = cutRef.current.currentTime * 1000;
    const keep = timeline.keptSegments.find(
      (s) =>
        outputMs >= s.outputStartMs &&
        outputMs < s.outputStartMs + s.sourceEndMs - s.sourceStartMs,
    );
    if (keep) {
      const sourceTime =
        (keep.sourceStartMs + outputMs - keep.outputStartMs) / 1000;
      if (Math.abs(originalRef.current.currentTime - sourceTime) > 0.18)
        originalRef.current.currentTime = sourceTime;
    }
  }
  return (
    <div className="space-y-3">
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            ORIGINAL
          </p>
          {source.data ? (
            <video
              key={original?.assetId}
              ref={originalRef}
              aria-label="Original video"
              controls
              preload="metadata"
              className="aspect-video w-full rounded-lg bg-black"
              src={source.data.url}
              muted={sync && Boolean(cut)}
            >
              <track
                kind="captions"
                label="Source transcript"
                src={sourceCaptions.data}
              />
            </video>
          ) : (
            <div className="flex aspect-video items-center justify-center rounded-lg bg-muted text-sm text-muted-foreground">
              {source.error ? source.error.message : "Loading source…"}
            </div>
          )}
        </div>
        <div>
          <p className="mb-2 text-xs font-medium text-signal">ROUGH CUT</p>
          {preview.data ? (
            <video
              key={cut?.assetId}
              ref={cutRef}
              aria-label="Rough-cut video"
              controls
              preload="metadata"
              className="aspect-video w-full rounded-lg bg-black ring-1 ring-signal/30"
              src={preview.data.url}
              onTimeUpdate={align}
              onSeeking={align}
              onRateChange={() => {
                if (sync && originalRef.current && cutRef.current)
                  originalRef.current.playbackRate =
                    cutRef.current.playbackRate;
              }}
              onPlay={() => {
                if (sync) {
                  align();
                  void originalRef.current?.play().catch(() => undefined);
                }
              }}
              onPause={() => {
                if (sync) originalRef.current?.pause();
              }}
              onEnded={() => originalRef.current?.pause()}
            >
              <track
                kind="captions"
                label="Rough-cut transcript"
                src={captions.data}
              />
            </video>
          ) : (
            <div className="flex aspect-video flex-col items-center justify-center gap-2 rounded-lg border border-dashed bg-muted/30 p-5 text-center">
              <span className="text-sm font-medium">
                {preview.error
                  ? preview.error.message
                  : "Your next version starts here"}
              </span>
              <span className="text-xs text-muted-foreground">
                Choose cuts below, then render a preview.
              </span>
            </div>
          )}
        </div>
      </div>
      {cut && (
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            checked={sync}
            onChange={(event) => {
              setSync(event.target.checked);
              originalRef.current?.pause();
            }}
            className="accent-signal"
          />
          Link playback · play the rough cut to compare matching moments
          (original muted)
        </label>
      )}
    </div>
  );
}

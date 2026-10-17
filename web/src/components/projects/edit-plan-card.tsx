"use client";

import { useId, useState } from "react";
import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";

import { NewRevisionButton } from "@/components/projects/video-revisions";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDurationMs, listFindings } from "@/lib/analysis";
import {
  downloadEditPlan,
  getEditPlan,
  type EditLabels,
} from "@/lib/edit-plan";

export function EditPlanCard({
  projectId,
  runId,
  onJobId,
}: {
  projectId: string;
  runId: string;
  onJobId?: (jobId: string) => void;
}) {
  const fpsId = useId();
  const [overrides, setOverrides] = useState<EditLabels>({});
  const [fps, setFps] = useState(30);
  const findings = useQuery({
    queryKey: ["analysis-findings", projectId, runId],
    queryFn: () => listFindings(projectId, runId),
  });
  const accepted = (findings.data?.items ?? []).filter(
    (finding) =>
      finding.decision?.status === "accepted" ||
      finding.decision?.status === "revised",
  );
  // A changed decision refreshes the preview and drops overrides for ineligible findings.
  const labels = Object.fromEntries(
    Object.entries(overrides).filter(([id]) =>
      accepted.some((finding) => finding.findingId === id),
    ),
  );
  const plan = useQuery({
    queryKey: [
      "edit-plan",
      projectId,
      runId,
      accepted.map((finding) => [finding.findingId, finding.decision]),
      labels,
    ],
    queryFn: () => getEditPlan(projectId, runId, labels),
    enabled: findings.isSuccess,
    placeholderData: keepPreviousData,
    retry: false,
  });
  const download = useMutation({
    mutationFn: (format: "cmx3600" | "markdown") =>
      downloadEditPlan(projectId, runId, labels, format, fps),
  });
  const data = plan.data;
  const error = findings.error ?? plan.error ?? download.error;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Export edit plan</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-muted-foreground">
          Accepted and revised findings become cuts or edit notes. Change a
          label for this download; your review decisions stay saved separately.
        </p>
        {error && (
          <div role="alert" className="space-y-2 text-xs text-destructive">
            <p>{error.message || "Could not load the edit plan."}</p>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                void findings.refetch();
                void plan.refetch();
              }}
            >
              Retry plan
            </Button>
          </div>
        )}
        {!data && (findings.isPending || plan.isFetching) && (
          <Skeleton className="h-24 w-full" />
        )}
        {data && (
          <>
            <p role="status" className="text-sm font-medium tabular-nums">
              Removes {data.removedSpans.length}{" "}
              {data.removedSpans.length === 1 ? "span" : "spans"} ·{" "}
              {formatDurationMs(data.durationMsBefore)} →{" "}
              {formatDurationMs(data.durationMsAfter)}
              {plan.isFetching ? " · Updating…" : ""}
            </p>
            {data.findings.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                Accept or revise a finding to include it in your edit plan.
              </p>
            ) : (
              <ul
                aria-label="Accepted edits"
                className="max-h-72 space-y-2 overflow-y-auto"
              >
                {data.findings.map((finding) => (
                  <li
                    key={finding.findingId}
                    className="space-y-2 rounded-lg border border-border p-3 text-xs"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="tabular-nums">
                        {formatDurationMs(finding.startMs)}–
                        {formatDurationMs(finding.endMs)}
                      </span>
                      <div
                        role="group"
                        aria-label={`Edit label at ${formatDurationMs(finding.startMs)}`}
                        className="flex gap-1"
                      >
                        {(["cut", "note"] as const).map((label) => (
                          <Button
                            key={label}
                            size="sm"
                            variant={
                              finding.label === label ? "default" : "outline"
                            }
                            aria-pressed={finding.label === label}
                            disabled={plan.isFetching}
                            onClick={() =>
                              setOverrides((value) => ({
                                ...value,
                                [finding.findingId]: label,
                              }))
                            }
                          >
                            {label === "cut" ? "Cut" : "Note"}
                          </Button>
                        ))}
                      </div>
                    </div>
                    <p>{finding.action}</p>
                    <p className="text-muted-foreground">
                      {finding.skippedReason
                        ? `Skipped cut: ${finding.skippedReason}`
                        : finding.labelReason}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
        <div className="flex flex-wrap items-end gap-2">
          <div className="space-y-1">
            <label htmlFor={fpsId} className="block text-xs font-medium">
              Frame rate
            </label>
            <select
              id={fpsId}
              value={fps}
              onChange={(event) => setFps(Number(event.target.value))}
              className="h-8 rounded-lg border border-input bg-background px-2 text-xs"
            >
              {[24, 25, 30, 60].map((value) => (
                <option key={value} value={value}>
                  {value} fps
                </option>
              ))}
            </select>
          </div>
          <Button
            size="sm"
            variant="outline"
            disabled={
              !data ||
              !data.findings.length ||
              plan.isFetching ||
              !!plan.error ||
              download.isPending
            }
            onClick={() => download.mutate("cmx3600")}
          >
            Download cut list (.edl)
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={
              !data ||
              !data.findings.length ||
              plan.isFetching ||
              !!plan.error ||
              download.isPending
            }
            onClick={() => download.mutate("markdown")}
          >
            Download edit plan (.md)
          </Button>
        </div>
        <div className="space-y-2 border-t border-border pt-3">
          <p className="text-xs text-muted-foreground">
            Edited it in your editor? Upload the new version and re-run review
            to see what changed.
          </p>
          <NewRevisionButton projectId={projectId} onQueued={onJobId} />
        </div>
      </CardContent>
    </Card>
  );
}

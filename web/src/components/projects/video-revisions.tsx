"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CloudUploadIcon,
  HistoryIcon,
  Loading03Icon,
} from "@hugeicons/core-free-icons";
import { format } from "date-fns";

import { Icon } from "@/components/common/icon";
import { DisabledReason } from "@/components/common/disabled-reason";
import { VideoDropzone } from "@/components/projects/video-dropzone";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ApiError } from "@/lib/api-client";
import { activateRevision, formatBytes, listRevisions } from "@/lib/projects";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";
import type { Revision } from "@/lib/types";

/*
 * A project keeps one video but several revisions of it. The header shows which
 * revision is active and opens the retained history (with the transcript and
 * review count each revision already has). Uploading a new revision and deleting
 * the project live below the video card.
 */

function useRevisionInvalidation(projectId: string) {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: ["revisions", projectId] });
    void queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    void queryClient.invalidateQueries({ queryKey: ["assets", projectId] });
    void queryClient.invalidateQueries({ queryKey: ["transcript", projectId] });
    void queryClient.invalidateQueries({
      queryKey: ["analysis-runs", projectId],
    });
  };
}

/** Active-revision badge + the revision history dialog. Lives in the card header. */
export function VideoRevisions({
  projectId,
  activeRevision,
  revisionCount,
  onQueued,
}: {
  projectId: string;
  activeRevision: number | null;
  revisionCount: number;
  onQueued?: (jobId: string) => void;
}) {
  const invalidate = useRevisionInvalidation(projectId);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [activatingId, setActivatingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const revisionsQuery = useQuery({
    queryKey: ["revisions", projectId],
    queryFn: () => listRevisions(projectId),
  });
  const revisions = revisionsQuery.data?.items ?? [];
  // The project's counter is the source of truth, but legacy projects predate it:
  // fall back to what the revision list actually holds.
  const total = Math.max(revisionCount, revisions.length);
  const active =
    activeRevision ?? revisions.find((item) => item.isActive)?.revision ?? null;

  const activateMutation = useMutation({
    mutationFn: (assetId: string) => activateRevision(projectId, assetId),
    onMutate: (assetId) => {
      setActivatingId(assetId);
      setError(null);
    },
    onSuccess: (activation) => {
      setActivatingId(null);
      setHistoryOpen(false);
      invalidate();
      // No transcript existed for that revision: a fresh run was queued, so let
      // the workspace track the job just like an upload.
      if (activation.jobId) onQueued?.(activation.jobId);
    },
    onError: (caught) => {
      setActivatingId(null);
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not switch to that revision.",
      );
    },
  });

  if (total === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {active != null && <Badge variant="secondary">Revision {active}</Badge>}

      <Dialog
        open={historyOpen}
        onOpenChange={(next) => {
          setHistoryOpen(next);
          if (!next) setError(null);
        }}
      >
        <DialogTrigger
          render={
            <Button variant="ghost" size="sm">
              <Icon icon={HistoryIcon} />
              History
            </Button>
          }
        />
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Video revisions</DialogTitle>
            <DialogDescription>
              Every upload is kept, so transcripts and reviews stay attributable
              to the revision they were built from. Switch back to an earlier
              revision any time — nothing is deleted.
            </DialogDescription>
          </DialogHeader>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <ul className="max-h-80 space-y-1 overflow-y-auto">
            {revisions.map((revision) => (
              <RevisionRow
                key={revision.assetId}
                revision={revision}
                activating={activatingId === revision.assetId}
                busy={activateMutation.isPending}
                onActivate={() => activateMutation.mutate(revision.assetId)}
              />
            ))}
          </ul>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/** Upload a new cut. Lives below the video card, next to Delete. */
export function NewRevisionButton({
  projectId,
  onQueued,
  variant = "outline",
}: {
  projectId: string;
  onQueued?: (jobId: string) => void;
  variant?: "outline" | "default";
}) {
  const invalidate = useRevisionInvalidation(projectId);
  const readOnly = useReadOnly();
  const [uploadOpen, setUploadOpen] = useState(false);

  function handleQueued(jobId: string) {
    setUploadOpen(false);
    invalidate();
    onQueued?.(jobId);
  }

  return (
    <Dialog open={uploadOpen} onOpenChange={setUploadOpen}>
      <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
        <DialogTrigger
          render={
            <Button variant={variant} size="sm" disabled={readOnly}>
              <Icon icon={CloudUploadIcon} />
              New revision
            </Button>
          }
        />
      </DisabledReason>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upload a new revision</DialogTitle>
          <DialogDescription>
            This becomes the project&apos;s active video and is transcribed
            automatically. Earlier revisions and their transcripts are kept, and
            you can re-run the review once the new transcript is ready.
          </DialogDescription>
        </DialogHeader>
        <VideoDropzone projectId={projectId} onQueued={handleQueued} />
      </DialogContent>
    </Dialog>
  );
}

function RevisionRow({
  revision,
  activating,
  busy,
  onActivate,
}: {
  revision: Revision;
  activating: boolean;
  busy: boolean;
  onActivate: () => void;
}) {
  const readOnly = useReadOnly();
  return (
    <li className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-sm">
      <div className="flex items-center gap-2">
        <span className="font-medium">Revision {revision.revision}</span>
        {revision.isActive && <Badge variant="secondary">Active</Badge>}
      </div>
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span>{format(new Date(revision.createdAt), "d MMM yyyy")}</span>
        <span className="tabular">{formatBytes(revision.sizeBytes)}</span>
        {revision.transcriptVersion != null ? (
          <span>Transcript v{revision.transcriptVersion}</span>
        ) : (
          <span>No transcript</span>
        )}
        {revision.analysisRunCount > 0 ? (
          <span>
            {revision.analysisRunCount} review
            {revision.analysisRunCount === 1 ? "" : "s"}
          </span>
        ) : null}
        {!revision.isActive && (
          <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
            <Button
              variant="outline"
              size="sm"
              onClick={onActivate}
              disabled={busy || readOnly}
            >
              {activating ? (
                <Icon icon={Loading03Icon} className="animate-spin" />
              ) : null}
              {activating ? "Switching…" : "Activate"}
            </Button>
          </DisabledReason>
        )}
      </div>
    </li>
  );
}

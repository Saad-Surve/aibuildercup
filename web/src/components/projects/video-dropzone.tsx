"use client";

import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { CloudUploadIcon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { DisabledReason } from "@/components/common/disabled-reason";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ApiError } from "@/lib/api-client";
import { saveVideoBlob } from "@/lib/local-media";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";
import {
  ACCEPTED_VIDEO_EXTENSIONS,
  completeUpload,
  createUploadSession,
  uploadToStorage,
  validateVideoFile,
} from "@/lib/projects";
import { cn } from "@/lib/utils";

type Phase = "idle" | "uploading" | "finalizing";

function describe(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Upload failed. Try again.";
}

export function VideoDropzone({
  projectId,
  onQueued,
}: {
  projectId: string;
  onQueued?: (jobId: string) => void;
}) {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const readOnly = useReadOnly();

  const [dragging, setDragging] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [percent, setPercent] = useState(0);
  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const busy = phase !== "idle";

  async function start(file: File) {
    const invalid = validateVideoFile(file);
    if (invalid) {
      setError(invalid);
      return;
    }

    setError(null);
    setFileName(file.name);
    setPercent(0);
    setPhase("uploading");

    try {
      const session = await createUploadSession(projectId, file);
      await uploadToStorage(session, file, setPercent);
      setPhase("finalizing");
      // Keep a local copy so the project can play the video and card
      // thumbnails can be captured from it, even while offline. Stored under
      // both keys so cards recover even if the asset record is unavailable.
      saveVideoBlob(session.assetId, file, projectId).catch(() => {});
      const job = await completeUpload(projectId, session.assetId);
      await queryClient.invalidateQueries({ queryKey: ["assets", projectId] });
      await queryClient.invalidateQueries({
        queryKey: ["revisions", projectId],
      });
      await queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      onQueued?.(job.jobId);
    } catch (caught) {
      setError(describe(caught));
    } finally {
      setPhase("idle");
    }
  }

  function onDrop(event: React.DragEvent) {
    event.preventDefault();
    setDragging(false);
    if (busy || readOnly) return;
    const file = event.dataTransfer.files?.[0];
    if (file) void start(file);
  }

  return (
    <div className="space-y-3">
      <div
        onDragOver={(event) => {
          event.preventDefault();
          if (!busy && !readOnly) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex flex-col items-center gap-3 rounded-lg border border-dashed px-6 py-12 text-center transition-colors",
          dragging && "border-signal bg-signal/5",
        )}
      >
        <span className="flex size-10 items-center justify-center rounded-lg bg-muted text-muted-foreground">
          <Icon icon={CloudUploadIcon} className="size-5" />
        </span>

        {busy ? (
          <div className="w-full max-w-sm space-y-2">
            <p className="truncate text-sm font-medium">{fileName}</p>
            <Progress value={percent} />
            <p className="tabular text-xs text-muted-foreground">
              {phase === "finalizing"
                ? "Confirming upload…"
                : `Uploading ${percent}%`}
            </p>
          </div>
        ) : (
          <>
            <div className="space-y-1">
              <p className="text-sm font-medium">Drop a video here</p>
              <p className="text-sm text-muted-foreground">
                MP4, MOV, WebM, or M4V up to 500 MB.
              </p>
            </div>
            <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
              <Button
                type="button"
                variant="outline"
                onClick={() => inputRef.current?.click()}
                disabled={readOnly}
              >
                <Icon icon={CloudUploadIcon} />
                Choose a file
              </Button>
            </DisabledReason>
          </>
        )}

        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_VIDEO_EXTENSIONS}
          className="sr-only"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void start(file);
            event.target.value = "";
          }}
        />
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </div>
  );
}

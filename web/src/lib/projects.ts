import { apiFetch, apiFetchBlob } from "@/lib/api-client";
import type {
  AcceptedJob,
  Asset,
  AssetList,
  CaptionPreset,
  CaptionRender,
  CaptionRenderAccepted,
  CaptionStyle,
  CreateProjectInput,
  GenerateThumbnailsInput,
  Job,
  DownloadUrl,
  Project,
  ProjectList,
  RevisionActivation,
  RevisionList,
  ThumbnailBatchAccepted,
  ThumbnailConcept,
  ThumbnailRevisionAccepted,
  Transcript,
  TranscriptSegment,
  TranscriptVersion,
  UploadSession,
} from "@/lib/types";

export const MAX_UPLOAD_BYTES = 500 * 1024 * 1024;

export const ALLOWED_VIDEO_TYPES = [
  "video/mp4",
  "video/quicktime",
  "video/webm",
  "video/x-m4v",
];

export const ACCEPTED_VIDEO_EXTENSIONS = ".mp4,.mov,.webm,.m4v";

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${units[unit]}`;
}

export function validateVideoFile(file: File): string | null {
  if (!ALLOWED_VIDEO_TYPES.includes(file.type)) {
    return "Unsupported format. Upload an MP4, MOV, WebM, or M4V file.";
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return "This file is larger than the 500 MB limit.";
  }
  return null;
}

export function listProjects(): Promise<ProjectList> {
  return apiFetch<ProjectList>("/projects");
}

export function getProject(projectId: string): Promise<Project> {
  return apiFetch<Project>(`/projects/${projectId}`);
}

export function createProject(input: CreateProjectInput): Promise<Project> {
  return apiFetch<Project>("/projects", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateProject(
  projectId: string,
  input: {
    name?: string;
    description?: string;
    thumbnailConcept?: string;
    /** Link/unlink the script source; explicit null clears the link. */
    sourceDraftId?: string | null;
  },
): Promise<Project> {
  return apiFetch<Project>(`/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function deleteProject(projectId: string): Promise<void> {
  return apiFetch<void>(`/projects/${projectId}`, {
    method: "DELETE",
  });
}

export function listAssets(projectId: string): Promise<AssetList> {
  return apiFetch<AssetList>(`/projects/${projectId}/assets`);
}

/**
 * The project's active source video.
 *
 * A project may hold several revisions, so "newest" is not the same as "active":
 * always prefer the asset the project points at and only fall back to the first
 * source video for legacy projects that predate the pointer.
 */
export function pickSourceAsset(
  assets: Asset[] | undefined,
  activeAssetId: string | null | undefined,
): Asset | undefined {
  if (!assets) return undefined;
  return (
    assets.find((asset) => asset.assetId === activeAssetId) ??
    assets.find((asset) => asset.type === "source_video")
  );
}

/** Source-video revisions, newest first; the active one is flagged. */
export function listRevisions(projectId: string): Promise<RevisionList> {
  return apiFetch<RevisionList>(`/projects/${projectId}/revisions`);
}

/** Make an earlier revision the project's active source video. */
export function activateRevision(
  projectId: string,
  assetId: string,
): Promise<RevisionActivation> {
  return apiFetch<RevisionActivation>(
    `/projects/${projectId}/revisions/${assetId}/activate`,
    { method: "POST" },
  );
}

export function createUploadSession(
  projectId: string,
  file: File,
): Promise<UploadSession> {
  return apiFetch<UploadSession>(`/projects/${projectId}/upload-session`, {
    method: "POST",
    body: JSON.stringify({
      fileName: file.name,
      contentType: file.type,
      sizeBytes: file.size,
    }),
  });
}

export function completeUpload(
  projectId: string,
  assetId: string,
): Promise<AcceptedJob> {
  return apiFetch<AcceptedJob>(
    `/projects/${projectId}/assets/${assetId}/complete`,
    { method: "POST" },
  );
}

export function getJob(jobId: string): Promise<Job> {
  return apiFetch<Job>(`/jobs/${jobId}`);
}

export function getTranscript(
  projectId: string,
  version?: number | null,
): Promise<Transcript> {
  const suffix = version != null ? `?version=${version}` : "";
  return apiFetch<Transcript>(`/projects/${projectId}/transcript${suffix}`);
}

export function listTranscriptVersions(
  projectId: string,
): Promise<{ items: TranscriptVersion[] }> {
  return apiFetch<{ items: TranscriptVersion[] }>(
    `/projects/${projectId}/transcript/versions`,
  );
}

/** Queue a fresh transcription run for the project's source video. */
export function retranscribeTranscript(
  projectId: string,
): Promise<AcceptedJob> {
  return apiFetch<AcceptedJob>(
    `/projects/${projectId}/transcript/retranscribe`,
    { method: "POST" },
  );
}

/**
 * Persist edited transcript segments. The API saves them as a new active
 * version and returns it, so history (including the machine transcript) stays
 * recoverable through the version picker.
 */
export function updateTranscript(
  projectId: string,
  input: {
    language?: string | null;
    speakerLabels?: Record<string, string> | null;
    segments: TranscriptSegment[];
  },
): Promise<Transcript> {
  return apiFetch<Transcript>(`/projects/${projectId}/transcript`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

export function formatTimestamp(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export function getDownloadUrl(
  projectId: string,
  assetId: string,
): Promise<DownloadUrl> {
  return apiFetch<DownloadUrl>(
    `/projects/${projectId}/assets/${assetId}/download-url`,
  );
}

// --------------------------------------------------------------------- captions

/** Style presets offered by the backend; the preview and the render share them. */
export function listCaptionPresets(): Promise<{ items: CaptionPreset[] }> {
  return apiFetch<{ items: CaptionPreset[] }>("/caption-presets");
}

/** Queue a burn-in of the transcript onto the project's source video. */
export function createCaptionRender(
  projectId: string,
  input: {
    style: CaptionStyle;
    transcriptVersion?: number | null;
    /** Burn a dub's localized captions onto its dubbed video instead of the source. */
    localizationId?: string | null;
    fileName?: string | null;
  },
): Promise<CaptionRenderAccepted> {
  return apiFetch<CaptionRenderAccepted>(
    `/projects/${projectId}/captions/renders`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function listCaptionRenders(
  projectId: string,
): Promise<{ items: CaptionRender[] }> {
  return apiFetch<{ items: CaptionRender[] }>(
    `/projects/${projectId}/captions/renders`,
  );
}

export function deleteCaptionRender(
  projectId: string,
  captionRenderId: string,
): Promise<void> {
  return apiFetch<void>(
    `/projects/${projectId}/captions/renders/${captionRenderId}`,
    { method: "DELETE" },
  );
}

// ------------------------------------------------------------------- thumbnails

export function listThumbnails(
  projectId: string,
): Promise<{ items: ThumbnailConcept[] }> {
  return apiFetch<{ items: ThumbnailConcept[] }>(
    `/projects/${projectId}/thumbnails`,
  );
}

/** Plan and render a batch of grounded thumbnail concepts. */
export function generateThumbnails(
  projectId: string,
  input: GenerateThumbnailsInput,
): Promise<ThumbnailBatchAccepted> {
  return apiFetch<ThumbnailBatchAccepted>(`/projects/${projectId}/thumbnails`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/** Conversationally edit a concept's active image; appends a new version. */
export function reviseThumbnail(
  projectId: string,
  thumbnailId: string,
  instruction: string,
): Promise<ThumbnailRevisionAccepted> {
  return apiFetch<ThumbnailRevisionAccepted>(
    `/projects/${projectId}/thumbnails/${thumbnailId}/revise`,
    { method: "POST", body: JSON.stringify({ instruction }) },
  );
}

/** Make this concept the project's packaging promise (feeds the reviewers). */
export function applyThumbnail(
  projectId: string,
  thumbnailId: string,
): Promise<ThumbnailConcept> {
  return apiFetch<ThumbnailConcept>(
    `/projects/${projectId}/thumbnails/${thumbnailId}/apply`,
    { method: "POST" },
  );
}

export function deleteThumbnail(
  projectId: string,
  thumbnailId: string,
): Promise<void> {
  return apiFetch<void>(`/projects/${projectId}/thumbnails/${thumbnailId}`, {
    method: "DELETE",
  });
}

/** Re-render selected concepts as fresh versions, keeping each idea. */
export function regenerateThumbnails(
  projectId: string,
  thumbnailIds: string[],
): Promise<ThumbnailBatchAccepted> {
  return apiFetch<ThumbnailBatchAccepted>(
    `/projects/${projectId}/thumbnails/regenerate`,
    { method: "POST", body: JSON.stringify({ thumbnailIds }) },
  );
}

/** Zip of the selected concepts' active images, for a bulk download. */
export function downloadThumbnailsZip(
  projectId: string,
  thumbnailIds: string[],
): Promise<Blob> {
  return apiFetchBlob(`/projects/${projectId}/thumbnails/download`, {
    method: "POST",
    body: JSON.stringify({ thumbnailIds }),
  });
}

/**
 * Upload the file straight to Cloud Storage with the signed URL from the API.
 * Uses XHR because fetch has no upload-progress events.
 */
export function uploadToStorage(
  session: UploadSession,
  file: File,
  onProgress: (percent: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("PUT", session.uploadUrl);
    for (const [key, value] of Object.entries(session.requiredHeaders)) {
      request.setRequestHeader(key, value);
    }
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    });
    request.addEventListener("load", () => {
      if (request.status >= 200 && request.status < 300) {
        onProgress(100);
        resolve();
      } else {
        reject(new Error(`Upload failed (${request.status}).`));
      }
    });
    request.addEventListener("error", () =>
      reject(new Error("Upload failed. Check your connection and try again.")),
    );
    request.send(file);
  });
}

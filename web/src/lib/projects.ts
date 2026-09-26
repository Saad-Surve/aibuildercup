import { API_BASE_URL } from "@/lib/api-base";
import { apiFetch } from "@/lib/api-client";
import { auth } from "@/lib/firebase";
import type {
  AcceptedJob,
  AssetList,
  CreateProjectInput,
  Job,
  DownloadUrl,
  Project,
  ProjectList,
  ProjectStatus,
  Transcript,
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
  input: { name?: string; description?: string },
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

export interface ProjectProgressEvent {
  projectId: string;
  status: ProjectStatus;
  progress: Project["progress"];
  job: {
    jobId: string;
    status: Job["status"];
    progress: Job["progress"];
  } | null;
}

/**
 * Subscribe to the backend SSE stream `GET /projects/{id}/events`.
 *
 * Plain `EventSource` cannot send the Firebase `Authorization` header, so this
 * uses `fetch` + a `ReadableStream` reader and parses `job.progress` frames.
 * Failures are silent on purpose: the workspace keeps its polling queries as
 * a fallback, so a dropped stream only means slower updates, never a stuck UI.
 * Returns an unsubscribe function.
 */
export function subscribeToProjectEvents(
  projectId: string,
  onEvent: (event: ProjectProgressEvent) => void,
): () => void {
  const controller = new AbortController();

  async function run(): Promise<void> {
    try {
      const token = await auth.currentUser?.getIdToken();
      if (!token || controller.signal.aborted) return;
      const response = await fetch(
        `${API_BASE_URL}/projects/${projectId}/events`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "text/event-stream",
          },
          signal: controller.signal,
        },
      );
      if (!response.ok || !response.body) return;
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const dataLine = frame
            .split("\n")
            .filter((line) => line.startsWith("data:"));
          if (dataLine.length === 0) continue;
          try {
            onEvent(
              JSON.parse(
                dataLine.map((line) => line.slice(5)).join("\n"),
              ) as ProjectProgressEvent,
            );
          } catch {
            // Ignore a malformed frame; the next one carries fresh state.
          }
        }
        if (controller.signal.aborted) break;
      }
    } catch {
      // Abort or network error: polling fallback keeps the UI fresh.
    }
  }

  void run();
  return () => controller.abort();
}

export function getTranscript(projectId: string): Promise<Transcript> {
  return apiFetch<Transcript>(`/projects/${projectId}/transcript`);
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

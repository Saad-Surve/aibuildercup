import { http, HttpResponse } from "msw";

import { API_BASE_URL } from "@/lib/api-base";
import type { Asset, Job, Project, UploadSession } from "@/lib/types";

const projects = new Map<string, Project>();
const assets = new Map<string, Asset>();
const jobs = new Map<string, Job>();
/* Raw upload bytes, so mock projects can play back what was uploaded. */
const media = new Map<string, { bytes: ArrayBuffer; contentType: string }>();

function newId(): string {
  return crypto.randomUUID().replace(/-/g, "");
}

function now(): string {
  return new Date().toISOString();
}

function notFound(code = "NOT_FOUND") {
  return HttpResponse.json(
    { error: { code, message: "Not found", requestId: null, details: {} } },
    { status: 404 },
  );
}

export const handlers = [
  http.get(`${API_BASE_URL}/healthz`, () =>
    HttpResponse.json({ status: "ok" }),
  ),

  http.get(`${API_BASE_URL}/me`, () =>
    HttpResponse.json({
      uid: "demo-user",
      displayName: "Demo Creator",
      email: "demo@example.com",
      onboardingCompleted: true,
      personaVersion: 1,
      preferences: { timezone: "Asia/Kolkata", defaultLanguage: "en" },
    }),
  ),

  http.get(`${API_BASE_URL}/projects`, () => {
    const items = [...projects.values()]
      .filter((project) => project.status !== "archived")
      .toSorted((a, b) => b.updatedAt.localeCompare(a.updatedAt));
    return HttpResponse.json({ items, nextPageToken: null });
  }),

  http.post(`${API_BASE_URL}/projects`, async ({ request }) => {
    const body = (await request.json()) as Partial<Project>;
    const timestamp = now();
    const project: Project = {
      projectId: newId(),
      name: body.name ?? "Untitled project",
      description: body.description ?? "",
      primaryLanguage: body.primaryLanguage ?? "en",
      targetLanguages: body.targetLanguages ?? [],
      targetPlatforms: body.targetPlatforms ?? [],
      isDemo: body.isDemo ?? false,
      demoProfileId: body.demoProfileId ?? null,
      status: "draft",
      progress: null,
      createdAt: timestamp,
      updatedAt: timestamp,
    };
    projects.set(project.projectId, project);
    return HttpResponse.json(project, { status: 201 });
  }),

  http.get(`${API_BASE_URL}/projects/:projectId`, ({ params }) => {
    const project = projects.get(String(params.projectId));
    if (!project || project.status === "archived") return notFound();
    return HttpResponse.json(project);
  }),

  http.delete(`${API_BASE_URL}/projects/:projectId`, ({ params }) => {
    const project = projects.get(String(params.projectId));
    if (!project || project.status === "archived") return notFound();
    project.status = "archived";
    project.updatedAt = now();
    return HttpResponse.json({ status: "accepted" }, { status: 202 });
  }),

  http.get(`${API_BASE_URL}/projects/:projectId/assets`, ({ params }) => {
    const items = [...assets.values()]
      .filter((asset) => asset.projectId === String(params.projectId))
      .toSorted((a, b) => b.createdAt.localeCompare(a.createdAt));
    return HttpResponse.json({ items });
  }),

  http.post(
    `${API_BASE_URL}/projects/:projectId/upload-session`,
    async ({ params, request }) => {
      const projectId = String(params.projectId);
      const project = projects.get(projectId);
      if (!project) return notFound();

      const body = (await request.json()) as {
        fileName: string;
        contentType: string;
        sizeBytes: number;
      };
      const assetId = newId();
      const extension =
        body.fileName.split(".").pop()?.toLowerCase() ??
        (body.contentType.split("/").pop() || "mp4");
      const timestamp = now();
      const asset: Asset = {
        assetId,
        projectId,
        type: "source_video",
        status: "pending",
        storagePath: `users/demo-user/projects/${projectId}/source/${assetId}.${extension}`,
        mimeType: body.contentType,
        sizeBytes: body.sizeBytes,
        durationMs: null,
        createdAt: timestamp,
        updatedAt: timestamp,
      };
      assets.set(assetId, asset);

      const session: UploadSession = {
        assetId,
        storagePath: asset.storagePath,
        uploadUrl: `${API_BASE_URL}/_mock-upload/${assetId}`,
        expiresAt: new Date(Date.now() + 900_000).toISOString(),
        requiredHeaders: { "Content-Type": body.contentType },
      };
      return HttpResponse.json(session, { status: 201 });
    },
  ),

  http.put(
    `${API_BASE_URL}/_mock-upload/:assetId`,
    async ({ params, request }) => {
      const bytes = await request.arrayBuffer();
      media.set(String(params.assetId), {
        bytes,
        contentType: request.headers.get("Content-Type") ?? "video/mp4",
      });
      return new HttpResponse(null, { status: 200 });
    },
  ),

  http.get(
    `${API_BASE_URL}/projects/:projectId/assets/:assetId/playback-url`,
    ({ params }) => {
      const asset = assets.get(String(params.assetId));
      if (!asset || asset.projectId !== String(params.projectId)) {
        return notFound();
      }
      return HttpResponse.json({
        url: `${API_BASE_URL}/_mock-media/${asset.assetId}`,
        expiresAt: new Date(Date.now() + 900_000).toISOString(),
      });
    },
  ),

  http.get(`${API_BASE_URL}/_mock-media/:assetId`, ({ params }) => {
    const item = media.get(String(params.assetId));
    if (!item) return notFound("MEDIA_NOT_FOUND");
    return new HttpResponse(item.bytes, {
      headers: { "Content-Type": item.contentType },
    });
  }),

  http.post(
    `${API_BASE_URL}/projects/:projectId/assets/:assetId/complete`,
    ({ params }) => {
      const projectId = String(params.projectId);
      const asset = assets.get(String(params.assetId));
      const project = projects.get(projectId);
      if (!asset || !project) return notFound();

      const timestamp = now();
      asset.status = "uploaded";
      asset.updatedAt = timestamp;
      project.status = "processing";
      project.progress = {
        stage: "transcription",
        percent: 0,
        message: "Queued for transcription",
      };
      project.updatedAt = timestamp;

      const job: Job = {
        jobId: newId(),
        type: "transcribe",
        status: "queued",
        progress: {
          percent: 0,
          step: "queued",
          message: "Waiting to start",
        },
        error: null,
        createdAt: timestamp,
        updatedAt: timestamp,
      };
      jobs.set(job.jobId, job);
      return HttpResponse.json(
        { jobId: job.jobId, status: job.status },
        { status: 202 },
      );
    },
  ),

  http.get(`${API_BASE_URL}/jobs/:jobId`, ({ params }) => {
    const job = jobs.get(String(params.jobId));
    return job ? HttpResponse.json(job) : notFound();
  }),
];

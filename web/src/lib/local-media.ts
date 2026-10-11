/*
 * Client-side media cache.
 *
 * The browser keeps a copy of every video it uploads (IndexedDB) so playback
 * and thumbnails work instantly — and survive reloads — even when the API has
 * no record of the asset (e.g. an older upload that predates the cache).
 * Posters are captured from a video frame via canvas and cached as data URLs
 * in localStorage.
 *
 * Blob/poster lookups are keyed by assetId first, then fall back to a
 * project-level key, so cards and the player recover even when the asset list
 * from the API is empty or uses a different id.
 */

const DB_NAME = "habeas-codus-media";
const STORE_NAME = "project-videos";
const POSTER_PREFIX = "hc-poster:";
const LEGACY_POSTER_PREFIX = "hc-video-poster:";
const POSTER_WIDTH = 480;
/** Only fetch remote bytes for a poster when the file is at most this big. */
const MAX_POSTER_FETCH_BYTES = 64 * 1024 * 1024;
/** Timestamps (seconds) tried in order until a non-blank frame is captured. */
const POSTER_SEEK_ATTEMPTS = [1, 3, 6];

function assetBlobKey(assetId: string): string {
  return `asset:${assetId}`;
}

function projectBlobKey(projectId: string): string {
  return `project:${projectId}`;
}

function assetPosterKey(assetId: string): string {
  return `${POSTER_PREFIX}asset:${assetId}`;
}

function projectPosterKey(projectId: string): string {
  return `${POSTER_PREFIX}project:${projectId}`;
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB is unavailable."));
      return;
    }
    const request = indexedDB.open(DB_NAME, 1);
    request.addEventListener("upgradeneeded", () => {
      request.result.createObjectStore(STORE_NAME);
    });
    request.addEventListener("success", () => resolve(request.result));
    request.addEventListener("error", () =>
      reject(request.error ?? new Error("Could not open media cache.")),
    );
  });
}

async function readBlob(key: string): Promise<Blob | null> {
  try {
    const db = await openDatabase();
    try {
      const value = await new Promise<unknown>((resolve, reject) => {
        const transaction = db.transaction(STORE_NAME, "readonly");
        const store = transaction.objectStore(STORE_NAME);
        const request = store.get(key);
        request.addEventListener("success", () => {
          // New project entries point to the asset blob; older entries contain
          // the blob itself and remain readable without a migration.
          if (typeof request.result === "string") {
            const linked = store.get(request.result);
            linked.addEventListener("success", () =>
              resolve(linked.result ?? null),
            );
            linked.addEventListener("error", () => reject(linked.error));
          } else {
            resolve(request.result ?? null);
          }
        });
        request.addEventListener("error", () =>
          reject(request.error ?? new Error("Could not read video cache.")),
        );
      });
      return value instanceof Blob ? value : null;
    } finally {
      db.close();
    }
  } catch {
    return null;
  }
}

/** Persist the uploaded file so the project can play it back later. */
export async function saveVideoBlob(
  assetId: string,
  blob: Blob,
  projectId?: string,
): Promise<void> {
  const db = await openDatabase();
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, "readwrite");
      const store = transaction.objectStore(STORE_NAME);
      store.put(blob, assetBlobKey(assetId));
      if (projectId)
        store.put(assetBlobKey(assetId), projectBlobKey(projectId));
      transaction.addEventListener("complete", () => resolve());
      transaction.addEventListener("error", () =>
        reject(transaction.error ?? new Error("Could not cache video.")),
      );
    });
  } finally {
    db.close();
  }
}

/** The locally cached upload for an asset, or null when absent/unavailable. */
export function getVideoBlob(assetId: string): Promise<Blob | null> {
  return readBlob(assetBlobKey(assetId));
}

/** The locally cached upload for a project, regardless of asset id. */
export function getVideoBlobForProject(
  projectId: string,
): Promise<Blob | null> {
  return readBlob(projectBlobKey(projectId));
}

function readPoster(key: string): string | null {
  try {
    if (typeof window === "undefined") return null;
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function getCachedPoster(
  assetId: string,
  projectId?: string,
): string | null {
  return (
    readPoster(assetPosterKey(assetId)) ??
    (projectId ? readPoster(projectPosterKey(projectId)) : null) ??
    // Keys written before the project-level fallback existed.
    readPoster(LEGACY_POSTER_PREFIX + assetId)
  );
}

export function getCachedPosterForProject(projectId: string): string | null {
  return readPoster(projectPosterKey(projectId));
}

function writePoster(key: string, dataUrl: string): void {
  try {
    window.localStorage.setItem(key, dataUrl);
  } catch {
    // Quota or private mode: posters are a nice-to-have, ignore.
  }
}

export function saveCachedPoster(
  assetId: string,
  dataUrl: string,
  projectId?: string,
): void {
  writePoster(assetPosterKey(assetId), dataUrl);
  if (projectId) writePoster(projectPosterKey(projectId), dataUrl);
}

export function saveCachedPosterForProject(
  projectId: string,
  dataUrl: string,
): void {
  writePoster(projectPosterKey(projectId), dataUrl);
}

function isBlankFrame(canvas: HTMLCanvasElement): boolean {
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) return false;
  const { width, height } = canvas;
  // Sample the central region (skips letterbox bars) on a coarse grid.
  const sample = context.getImageData(
    Math.floor(width * 0.25),
    Math.floor(height * 0.25),
    Math.ceil(width * 0.5),
    Math.ceil(height * 0.5),
  );
  let brightest = 0;
  for (let i = 0; i < sample.data.length; i += 4 * 37) {
    const pixel = Math.max(
      sample.data[i] ?? 0,
      sample.data[i + 1] ?? 0,
      sample.data[i + 2] ?? 0,
    );
    if (pixel > brightest) brightest = pixel;
    if (brightest >= 16) return false;
  }
  return true;
}

function drawPoster(video: HTMLVideoElement): string {
  const width = video.videoWidth;
  const height = video.videoHeight;
  if (!width || !height) throw new Error("Video has no dimensions yet.");
  const scale = Math.min(1, POSTER_WIDTH / width);
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Canvas 2D is unavailable.");
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  if (isBlankFrame(canvas)) throw new Error("Captured frame is blank.");
  return canvas.toDataURL("image/jpeg", 0.7);
}

/** Capture a poster frame from an already-loaded video element. */
export function capturePosterFromElement(video: HTMLVideoElement): string {
  return drawPoster(video);
}

function nextFrames(count = 2): Promise<void> {
  return new Promise((resolve) => {
    const step = (remaining: number) => {
      if (remaining <= 0) {
        resolve();
        return;
      }
      window.requestAnimationFrame(() => step(remaining - 1));
    };
    step(count);
  });
}

/**
 * Capture a poster frame from a blob without attaching anything to the DOM.
 * Tries several timestamps so fade-from-black intros don't yield a black card.
 */
export function capturePoster(source: Blob | string): Promise<string> {
  return new Promise((resolve, reject) => {
    const objectUrl =
      typeof source === "string" ? null : URL.createObjectURL(source);
    const url = objectUrl ?? (source as string);
    const video = document.createElement("video");
    video.muted = true;
    video.playsInline = true;
    video.preload = "metadata";
    video.crossOrigin = "anonymous";
    video.src = url;

    let settled = false;
    const cleanup = () => {
      window.clearTimeout(timer);
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      video.removeAttribute("src");
      video.load();
    };
    const fail = (error: unknown) => {
      if (settled) return;
      settled = true;
      cleanup();
      reject(error);
    };
    const succeed = (dataUrl: string) => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve(dataUrl);
    };
    const timer = window.setTimeout(() => {
      fail(new Error("Timed out capturing a poster frame."));
    }, 20_000);

    async function finish() {
      try {
        // Let the compositor paint the seeked frame before readback.
        await nextFrames();
        succeed(drawPoster(video));
      } catch (error) {
        fail(error);
      }
    }

    let attempt = 0;
    video.addEventListener("error", () => {
      fail(new Error("Could not load the video for a poster frame."));
    });
    video.addEventListener("loadedmetadata", () => {
      const duration = video.duration;
      const target =
        Number.isFinite(duration) && duration > 0
          ? Math.min(
              POSTER_SEEK_ATTEMPTS[attempt] ?? 1,
              Math.max(0, duration - 0.1),
            )
          : 0;
      // Setting the same time fires no `seeked`; capture directly instead.
      if (Math.abs(video.currentTime - target) < 0.01) {
        void finish();
      } else {
        video.currentTime = target;
      }
    });
    video.addEventListener("seeked", () => {
      // A blank frame (fade-in, dark scene) retries at the next timestamp.
      try {
        succeed(drawPoster(video));
      } catch {
        attempt += 1;
        if (attempt >= POSTER_SEEK_ATTEMPTS.length) {
          fail(new Error("No non-blank frame found for a poster."));
          return;
        }
        const duration = video.duration;
        const next =
          Number.isFinite(duration) && duration > 0
            ? Math.min(
                POSTER_SEEK_ATTEMPTS[attempt] ?? 1,
                Math.max(0, duration - 0.1),
              )
            : 0;
        if (Math.abs(video.currentTime - next) < 0.01) {
          void finish();
        } else {
          video.currentTime = next;
        }
      }
    });
  });
}

export interface PosterRef {
  projectId: string;
  assetId: string;
  sizeBytes?: number | null;
}

const inflightPosters = new Map<string, Promise<string | null>>();

/**
 * Best-effort poster for an asset: memory cache → local upload copy → a
 * bounded fetch of the playback bytes (works for uploads that predate the
 * local cache). Never throws; returns null when nothing works.
 */
export function ensurePoster(ref: PosterRef): Promise<string | null> {
  const cached = inflightPosters.get(ref.assetId);
  if (cached) return cached;
  const task = resolvePoster(ref).catch(() => null);
  inflightPosters.set(ref.assetId, task);
  void task.finally(() => {
    if (inflightPosters.get(ref.assetId) === task) {
      inflightPosters.delete(ref.assetId);
    }
  });
  return task;
}

async function resolvePoster(ref: PosterRef): Promise<string | null> {
  const cached = getCachedPoster(ref.assetId, ref.projectId);
  if (cached) return cached;

  const local =
    (await getVideoBlob(ref.assetId)) ??
    (await getVideoBlobForProject(ref.projectId));
  if (local) {
    try {
      const dataUrl = await capturePoster(local);
      saveCachedPoster(ref.assetId, dataUrl, ref.projectId);
      return dataUrl;
    } catch {
      // Fall through to the network attempt.
    }
  }

  if (
    ref.sizeBytes != null &&
    ref.sizeBytes > 0 &&
    ref.sizeBytes <= MAX_POSTER_FETCH_BYTES
  ) {
    try {
      const { getDownloadUrl } = await import("@/lib/projects");
      const playback = await getDownloadUrl(ref.projectId, ref.assetId);
      // Let the video element request metadata/frame ranges from GCS instead
      // of downloading and caching the entire object just for a small poster.
      const dataUrl = await capturePoster(playback.url);
      saveCachedPoster(ref.assetId, dataUrl, ref.projectId);
      return dataUrl;
    } catch {
      return null;
    }
  }

  return null;
}

/**
 * Drop every local trace of a project (upload blobs + posters) so a deleted
 * project can't resurface in cards or the player. Never throws.
 */
export async function purgeProjectMedia(
  projectId: string,
  assetIds: string[] = [],
): Promise<void> {
  try {
    const db = await openDatabase();
    try {
      await new Promise<void>((resolve, reject) => {
        const transaction = db.transaction(STORE_NAME, "readwrite");
        const store = transaction.objectStore(STORE_NAME);
        store.delete(projectBlobKey(projectId));
        for (const assetId of assetIds) store.delete(assetBlobKey(assetId));
        transaction.addEventListener("complete", () => resolve());
        transaction.addEventListener("error", () =>
          reject(transaction.error ?? new Error("Could not purge cache.")),
        );
      });
    } finally {
      db.close();
    }
  } catch {
    // Cache unavailable: nothing to purge.
  }
  try {
    window.localStorage.removeItem(projectPosterKey(projectId));
    for (const assetId of assetIds) {
      window.localStorage.removeItem(assetPosterKey(assetId));
      window.localStorage.removeItem(LEGACY_POSTER_PREFIX + assetId);
    }
  } catch {
    // Ignore storage failures on a best-effort purge.
  }
}

/** Poster from the project-level cache only (API knows no assets). */
export async function ensureProjectPoster(
  projectId: string,
): Promise<string | null> {
  const cached = getCachedPosterForProject(projectId);
  if (cached) return cached;
  const blob = await getVideoBlobForProject(projectId);
  if (!blob) return null;
  try {
    const dataUrl = await capturePoster(blob);
    saveCachedPosterForProject(projectId, dataUrl);
    return dataUrl;
  } catch {
    return null;
  }
}

export type { Finding, RubricSummary } from "@/lib/types";

import type { CreatorInterestCalibration } from "@/lib/types";
import { API_BASE_URL } from "@/lib/api-base";
import { auth } from "@/lib/firebase";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/*
 * The API runs on a single Cloud Run instance (process-local job locks). A burst of parallel
 * calls makes Cloud Run's router try to scale out, and with max-instances=1 it rejects some of
 * them with a 429 "no available instance" before they reach the app. Those responses carry no
 * CORS headers, so the browser reports them as a network failure. Cap in-flight requests to
 * smooth bursts, and retry idempotent GETs with backoff.
 */
const MAX_IN_FLIGHT = 6;
const GET_RETRIES = 3;
let inFlight = 0;
const waiting: (() => void)[] = [];

async function acquireSlot(): Promise<void> {
  if (inFlight < MAX_IN_FLIGHT) {
    inFlight += 1;
    return;
  }
  await new Promise<void>((resolve) => waiting.push(resolve));
}

function releaseSlot(): void {
  const next = waiting.shift();
  if (next) next();
  else inFlight -= 1;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function sendRequest(path: string, init: RequestInit): Promise<Response> {
  const method = (init.method ?? "GET").toUpperCase();
  const retries = method === "GET" ? GET_RETRIES : 0;
  for (let attempt = 0; ; attempt += 1) {
    const headers = await authHeaders();
    new Headers(init.headers).forEach((value, key) => headers.set(key, value));
    await acquireSlot();
    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
    } catch (error) {
      if (attempt >= retries || init.signal?.aborted) throw error;
      await sleep(400 * 2 ** attempt + Math.random() * 300);
      continue;
    } finally {
      releaseSlot();
    }
    if (response.status !== 429 || attempt >= retries) return response;
    const retryAfter = Number(response.headers.get("Retry-After"));
    await sleep(
      retryAfter > 0
        ? retryAfter * 1000
        : 400 * 2 ** attempt + Math.random() * 300,
    );
  }
}

async function authHeaders(): Promise<Headers> {
  const headers = new Headers({ "Content-Type": "application/json" });
  await auth.authStateReady();
  const user = auth.currentUser;
  if (user) {
    headers.set("Authorization", `Bearer ${await user.getIdToken()}`);
  }
  return headers;
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await sendRequest(path, init);

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      body?.error?.code ?? "UNKNOWN",
      body?.error?.message ?? response.statusText,
      body?.error?.details,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

/** Same auth + error handling as `apiFetch`, but for a binary response (e.g. a zip). */
export async function apiFetchBlob(
  path: string,
  init: RequestInit = {},
): Promise<Blob> {
  const response = await sendRequest(path, init);

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      body?.error?.code ?? "UNKNOWN",
      body?.error?.message ?? response.statusText,
      body?.error?.details,
    );
  }
  return await response.blob();
}

/** Channel drop-off calibration; all requests share the authenticated API boundary. */
export function getInterestCalibration(): Promise<CreatorInterestCalibration> {
  return apiFetch<CreatorInterestCalibration>("/interest-calibration");
}

export function calibrateInterest(
  connectionId: string,
): Promise<CreatorInterestCalibration> {
  return apiFetch<CreatorInterestCalibration>("/interest-calibration", {
    method: "POST",
    body: JSON.stringify({ connectionId }),
  });
}

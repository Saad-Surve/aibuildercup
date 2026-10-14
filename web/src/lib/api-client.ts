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

async function authHeaders(): Promise<Headers> {
  const headers = new Headers({ "Content-Type": "application/json" });
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
  const headers = await authHeaders();
  new Headers(init.headers).forEach((value, key) => headers.set(key, value));

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

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
  const headers = await authHeaders();
  new Headers(init.headers).forEach((value, key) => headers.set(key, value));

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  });

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

import { API_BASE_URL } from "@/lib/api-base";
import { auth } from "@/lib/firebase";

/*
 * Normalised API base. The contract serves everything under `/api/*`
 * (see `contracts/openapi.yaml`), but a bare origin without the `/api`
 * suffix (e.g. `http://localhost:8080`) used to silently produce 404s such
 * as `GET /me`. Appending the suffix when missing makes both forms work.
 */
function normalizeApiBaseUrl(raw: string | undefined): string {
  const trimmed =
    (raw ?? "").trim().replace(/\/+$/, "") || "http://localhost:8080/api";
  return trimmed.endsWith("/api") ? trimmed : `${trimmed}/api`;
}

export const API_BASE_URL = normalizeApiBaseUrl(
  process.env.NEXT_PUBLIC_API_BASE_URL,
);

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
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
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

import { API_BASE_URL } from "@/lib/api-base";
import { auth } from "@/lib/firebase";

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

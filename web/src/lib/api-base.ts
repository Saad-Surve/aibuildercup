/**
 * Base URL for the API.
 *
 * The backend always serves under `/api`: routers are mounted with that prefix in `main.py`, and
 * Firebase Hosting rewrites `/api/**` to Cloud Run. `NEXT_PUBLIC_API_BASE_URL` is configured both
 * with and without that suffix depending on the environment, so normalise it here. Without this a
 * base like `http://localhost:8080` would make every request 404.
 */
const RAW_API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080/api";

function withApiSuffix(url: string): string {
  const trimmed = url.replace(/\/+$/, "");
  return trimmed.endsWith("/api") ? trimmed : `${trimmed}/api`;
}

export const API_BASE_URL = withApiSuffix(RAW_API_BASE_URL);

import { apiFetch } from "@/lib/api-client";
import type {
  AudienceProfile,
  ChannelContentProfile,
  Connection,
  ConnectionList,
  CrosspostInput,
  CrosspostResult,
  OAuthStartRequest,
  OAuthStartResponse,
} from "@/lib/types";

export function listConnections(): Promise<ConnectionList> {
  return apiFetch<ConnectionList>("/connections");
}

/**
 * Begin the Google OAuth flow.
 *
 * The response carries the authorization URL. Open it in the same tab (or a popup) and Google
 * shows its account chooser (`prompt=select_account`), so the creator picks which Gmail account
 * to connect from. `redirectPath` is the same-origin path to land on afterwards.
 */
export function startYouTubeOAuth(
  input: OAuthStartRequest = {},
): Promise<OAuthStartResponse> {
  return apiFetch<OAuthStartResponse>("/connections/youtube/oauth/start", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function syncConnection(connectionId: string): Promise<Connection> {
  return apiFetch<Connection>(`/connections/${connectionId}/sync`, {
    method: "POST",
  });
}

/**
 * Begin the Reddit OAuth flow (confidential web-app flow, `duration=permanent`
 * so refresh keeps working). Same redirect-callback shape as YouTube; the
 * callback lands on `redirectPath` with `reddit=connected|error`.
 */
export function startRedditOAuth(
  input: OAuthStartRequest = {},
): Promise<OAuthStartResponse> {
  return apiFetch<OAuthStartResponse>("/connections/reddit/oauth/start", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

/**
 * Connect Medium with a legacy integration token. Medium stopped issuing new
 * tokens in January 2025 — this only works for creators who already hold one.
 */
export function connectMedium(token: string): Promise<Connection> {
  return apiFetch<Connection>("/connections/medium/connect", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

/**
 * Connect a Substack publication with a browser session cookie (`substack.sid`)
 * plus the publication subdomain. Cookie-based, so an expired session needs a
 * reconnect.
 */
export function connectSubstack(
  sid: string,
  subdomain?: string,
): Promise<Connection> {
  return apiFetch<Connection>("/connections/substack/connect", {
    method: "POST",
    body: JSON.stringify({ sid, subdomain: subdomain ?? null }),
  });
}

/** Cross-post a written piece. Synchronous — the result carries the live URL. */
export function crosspost(
  projectId: string,
  input: CrosspostInput,
): Promise<CrosspostResult> {
  return apiFetch<CrosspostResult>(`/projects/${projectId}/crossposts`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function deleteConnection(connectionId: string): Promise<void> {
  return apiFetch<void>(`/connections/${connectionId}`, { method: "DELETE" });
}

/** Read the channel's existing videos back for style/RAG. */
export function syncConnectionContent(
  connectionId: string,
): Promise<ChannelContentProfile> {
  return apiFetch<ChannelContentProfile>(
    `/connections/${connectionId}/content/sync`,
    { method: "POST" },
  );
}

export function getConnectionContent(
  connectionId: string,
): Promise<ChannelContentProfile> {
  return apiFetch<ChannelContentProfile>(`/connections/${connectionId}/content`);
}

/** Read YouTube Analytics for the channel's audience profile. */
export function syncConnectionAudience(
  connectionId: string,
): Promise<AudienceProfile> {
  return apiFetch<AudienceProfile>(
    `/connections/${connectionId}/audience/sync`,
    { method: "POST" },
  );
}

export function getConnectionAudience(
  connectionId: string,
): Promise<AudienceProfile> {
  return apiFetch<AudienceProfile>(`/connections/${connectionId}/audience`);
}

import { apiFetch } from "@/lib/api-client";
import type {
  Connection,
  ConnectionList,
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

export function deleteConnection(connectionId: string): Promise<void> {
  return apiFetch<void>(`/connections/${connectionId}`, { method: "DELETE" });
}

import { apiFetch } from "@/lib/api-client";
import type {
  Publish,
  PublishAccepted,
  PublishList,
  PublishRequest,
} from "@/lib/types";

export function listPublishes(projectId: string): Promise<PublishList> {
  return apiFetch<PublishList>(`/projects/${projectId}/publishes`);
}

export function getPublish(
  projectId: string,
  publishId: string,
): Promise<Publish> {
  return apiFetch<Publish>(`/projects/${projectId}/publishes/${publishId}`);
}

export function createPublish(
  projectId: string,
  input: PublishRequest,
): Promise<PublishAccepted> {
  return apiFetch<PublishAccepted>(`/projects/${projectId}/publishes`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function retryPublish(
  projectId: string,
  publishId: string,
): Promise<PublishAccepted> {
  return apiFetch<PublishAccepted>(
    `/projects/${projectId}/publishes/${publishId}/retry`,
    { method: "POST" },
  );
}

export function deletePublish(
  projectId: string,
  publishId: string,
): Promise<void> {
  return apiFetch<void>(`/projects/${projectId}/publishes/${publishId}`, {
    method: "DELETE",
  });
}

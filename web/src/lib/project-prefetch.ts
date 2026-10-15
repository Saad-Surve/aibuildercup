import type { QueryClient } from "@tanstack/react-query";
import { getProject, listAssets, getTranscript } from "@/lib/projects";
import type { Project } from "@/lib/types";

export function prefetchProject(client: QueryClient, project: Project): void {
  const id = project.projectId;
  void client.prefetchQuery({
    queryKey: ["project", id],
    queryFn: () => getProject(id),
  });
  if (project.kind === "draft") return;
  void import("@/components/projects/video-studio");
  void client.prefetchQuery({
    queryKey: ["assets", id],
    queryFn: () => listAssets(id),
  });
  void client.prefetchQuery({
    queryKey: ["transcript", id, "active"],
    queryFn: () => getTranscript(id),
    retry: false,
    staleTime: 60_000,
  });
}

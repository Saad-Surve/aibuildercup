import { apiFetch } from "@/lib/api-client";
import type { SeedYouTubeContentResult } from "@/lib/types";

/**
 * Load a public CC-BY YouTube channel's content into the signed-in account as a synthetic demo
 * connection, so the creator-content features have data to work with on a fresh account.
 */
export function seedYouTubeContent(
  channel = "psych2go",
): Promise<SeedYouTubeContentResult> {
  return apiFetch<SeedYouTubeContentResult>("/seed/youtube-content", {
    method: "POST",
    body: JSON.stringify({ channel }),
  });
}

import { apiFetch } from "@/lib/api-client";

export interface ListingFields {
  title: string;
  description: string;
  tags: string[];
}

export interface PackagingListing extends ListingFields {
  status: "queued" | "generating" | "ready" | "failed";
  sourceAssetId: string;
  transcriptId: string;
  titleOptions: string[];
  rationale: string;
  creatorHistoryUsed: boolean;
  evidence: { title: string; url: string | null }[];
  jobId: string | null;
  error: string | null;
  updatedAt: string;
  stale: boolean;
}

export interface PackagingBrief {
  brief?: string;
  useCreatorHistory?: boolean;
}

export interface PackagingAccepted {
  jobId: string;
  status: string;
}

export interface VisualInsert {
  insertId: string;
  kind: "chart" | "callout" | "broll";
  status: "suggested" | "queued" | "rendering" | "ready" | "failed";
  headline: string;
  body: string;
  rationale: string;
  sourceStartMs: number;
  sourceEndMs: number;
  sourceQuote: string;
  sourceAssetId: string;
  transcriptId: string;
  durationSeconds: 6;
  aspectRatio: "16:9" | "9:16";
  canRetry: boolean;
  prompt: string;
  chart: {
    label: string;
    value: number;
    sourceQuote: string;
    sourceTimestampMs: number;
  }[];
  chartUnit: string;
  estimatedCostUsd: number;
  jobId: string | null;
  previewUrl: string | null;
  error: string | null;
  stale: boolean;
  createdAt: string;
}

export interface VisualInsertList {
  items: VisualInsert[];
  suggestionJobId: string | null;
  paidRendersRemaining: number;
}

function base(projectId: string) {
  return `/projects/${encodeURIComponent(projectId)}`;
}

export const getPackagingListing = (id: string) =>
  apiFetch<PackagingListing | null>(`${base(id)}/packaging/listing`);

export const savePackagingListing = (id: string, fields: ListingFields) =>
  apiFetch<PackagingListing>(`${base(id)}/packaging/listing`, {
    method: "PUT",
    body: JSON.stringify(fields),
  });

export const generatePackagingListing = (
  id: string,
  brief: PackagingBrief = {},
) =>
  apiFetch<PackagingAccepted>(`${base(id)}/packaging/listing/generate`, {
    method: "POST",
    body: JSON.stringify(brief),
  });

export const listVisualInserts = (id: string) =>
  apiFetch<VisualInsertList>(`${base(id)}/visual-inserts`);

export const suggestVisualInserts = (id: string, brief: PackagingBrief = {}) =>
  apiFetch<PackagingAccepted>(`${base(id)}/visual-inserts/suggest`, {
    method: "POST",
    body: JSON.stringify(brief),
  });

export const renderVisualInsert = (
  id: string,
  insertId: string,
  payload: {
    prompt?: string;
    aspectRatio: "16:9" | "9:16";
    allowPaidGeneration: boolean;
  },
) =>
  apiFetch<PackagingAccepted>(
    `${base(id)}/visual-inserts/${encodeURIComponent(insertId)}/render`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );

export const deleteVisualInsert = (id: string, insertId: string) =>
  apiFetch<void>(`${base(id)}/visual-inserts/${encodeURIComponent(insertId)}`, {
    method: "DELETE",
  });

export function parseListingTags(value: string): string[] {
  return [
    ...new Set(
      value
        .split(",")
        .map((tag) => tag.trim())
        .filter(Boolean),
    ),
  ];
}

export function youtubeTagsSize(tags: string[]): number {
  return (
    tags.reduce(
      (sum, tag) => sum + tag.length + (tag.includes(" ") ? 2 : 0),
      0,
    ) + Math.max(0, tags.length - 1)
  );
}

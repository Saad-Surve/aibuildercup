"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Spinner } from "@/components/ui/spinner";
import { usePackagingListing } from "@/hooks/use-packaging-listing";
import {
  formatListingTags,
  parseListingTags,
  savePackagingListing,
  youtubeTagsSize,
  type ListingFields,
} from "@/lib/packaging";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";

export function ListingPanel({
  projectId,
  projectName,
}: {
  projectId: string;
  projectName: string;
}) {
  const readOnly = useReadOnly();
  const client = useQueryClient();
  const { listing, generate, busy } = usePackagingListing(projectId);
  const [draft, setDraft] = useState<
    (Omit<ListingFields, "tags"> & { tagsInput: string }) | null
  >(null);
  const [brief, setBrief] = useState("");
  const [history, setHistory] = useState(true);
  const saved = listing.data;
  const fields = draft ?? {
    title: saved?.title ?? projectName.slice(0, 100),
    description: saved?.description ?? "",
    tagsInput: formatListingTags(saved?.tags ?? []),
  };
  const tags = parseListingTags(fields.tagsInput);
  const tagSize = youtubeTagsSize(tags);
  const save = useMutation({
    mutationFn: () =>
      savePackagingListing(projectId, {
        title: fields.title,
        description: fields.description,
        tags,
      }),
    onSuccess: (data) => {
      client.setQueryData(["packaging-listing", projectId], data);
      setDraft(null);
      toast.success("Listing saved. It will fill the YouTube upload fields.");
    },
    onError: (error) => toast.error(error.message),
  });
  const disabled = readOnly || busy || save.isPending;
  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <Label htmlFor="listing-brief">Direction (optional)</Label>
        <Input
          id="listing-brief"
          value={brief}
          maxLength={2000}
          placeholder="For beginners; lead with the practical takeaway"
          disabled={disabled}
          onChange={(event) => setBrief(event.target.value)}
        />
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <Checkbox
            aria-label="Match my creator library when available"
            checked={history}
            disabled={disabled}
            onCheckedChange={(checked) => setHistory(checked === true)}
          />
          Match my creator library when available
        </label>
      </div>
      {listing.isPending ? (
        <p className="text-sm text-muted-foreground">Loading saved listing…</p>
      ) : null}
      {listing.error ? (
        <p role="alert" className="text-sm text-destructive">
          {listing.error.message}
        </p>
      ) : null}
      {saved?.stale ? (
        <p role="status" className="text-sm text-sev-medium">
          The video or transcript changed. Generate a fresh listing before
          saving or using it.
        </p>
      ) : null}
      {saved?.error ? (
        <p role="alert" className="text-sm text-destructive">
          {saved.error}
        </p>
      ) : null}
      <div className="space-y-1.5">
        <Label htmlFor="seo-title">
          Title{" "}
          <span className="text-muted-foreground">
            {fields.title.length}/100
          </span>
        </Label>
        <Input
          id="seo-title"
          value={fields.title}
          maxLength={100}
          disabled={disabled}
          onChange={(event) =>
            setDraft({ ...fields, title: event.target.value })
          }
        />
        {saved?.titleOptions.length ? (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {saved.titleOptions.map((title) => (
              <button
                key={title}
                type="button"
                disabled={disabled}
                onClick={() => setDraft({ ...fields, title })}
                className="rounded-md border px-2 py-1 text-left text-xs text-muted-foreground transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring disabled:opacity-50"
              >
                {title}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="seo-description">
          Description{" "}
          <span className="text-muted-foreground">
            {fields.description.length}/5000
          </span>
        </Label>
        <Textarea
          id="seo-description"
          rows={7}
          value={fields.description}
          maxLength={5000}
          disabled={disabled}
          onChange={(event) =>
            setDraft({ ...fields, description: event.target.value })
          }
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="seo-tags">
          Tags (space separated){" "}
          <span
            className={
              tagSize > 500 ? "text-destructive" : "text-muted-foreground"
            }
          >
            {tagSize}/500
          </span>
        </Label>
        <Input
          id="seo-tags"
          value={fields.tagsInput}
          disabled={disabled}
          onChange={(event) =>
            setDraft({ ...fields, tagsInput: event.target.value })
          }
          onBlur={() => {
            const formattedTags = formatListingTags(tags);
            if (formattedTags !== fields.tagsInput) {
              setDraft({ ...fields, tagsInput: formattedTags });
            }
          }}
          placeholder="#creators #video #storytelling"
        />
      </div>
      {saved?.rationale ? (
        <p className="text-xs text-muted-foreground">{saved.rationale}</p>
      ) : null}
      {saved?.creatorHistoryUsed ? (
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer">
            Style informed by your creator library
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-4">
            {saved.evidence.map((item, index) => (
              <li key={index}>
                {item.url && item.url.startsWith("https://") ? (
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noreferrer"
                    className="underline"
                  >
                    {item.title}
                  </a>
                ) : (
                  item.title
                )}
              </li>
            ))}
          </ul>
        </details>
      ) : saved?.status === "ready" ? (
        <p className="text-xs text-muted-foreground">
          Based on this video only.
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <Button
          disabled={disabled || listing.isPending}
          title={readOnly ? READ_ONLY_REASON : undefined}
          onClick={() =>
            generate.mutate(
              { brief, useCreatorHistory: history },
              { onSuccess: () => setDraft(null) },
            )
          }
        >
          {busy ? <Spinner /> : null}
          {busy
            ? "Writing listing…"
            : saved
              ? "Generate new listing"
              : "Generate listing"}
        </Button>
        <Button
          variant="outline"
          disabled={
            disabled ||
            listing.isPending ||
            !fields.title.trim() ||
            tagSize > 500 ||
            tags.length > 30 ||
            saved?.stale
          }
          onClick={() => save.mutate()}
        >
          {save.isPending ? <Spinner /> : null}Save listing
        </Button>
        {draft ? (
          <span className="text-xs text-muted-foreground">Unsaved edits</span>
        ) : null}
      </div>
      <p className="text-xs text-muted-foreground">
        Generating replaces saved fields. Save to keep your edits.
      </p>
    </div>
  );
}

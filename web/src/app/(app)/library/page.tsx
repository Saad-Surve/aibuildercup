"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiFetch } from "@/lib/api-client";
import type { CreatorLibrary, LibrarySearch } from "@/lib/creator-library";
import { useReadOnly, READ_ONLY_REASON } from "@/lib/read-only";
import { cn } from "@/lib/utils";

const position = (value: number | null) => 8 + (value ?? 0.5) * 84;
const formatTime = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;

export default function LibraryPage() {
  const cache = useQueryClient();
  const readOnly = useReadOnly();
  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["creator-library"],
    queryFn: () => apiFetch<CreatorLibrary>("/creator-library"),
    staleTime: 30_000,
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "text" | "image">("all");
  const [query, setQuery] = useState("");
  const [searchState, setSearchState] = useState<{
    fingerprint: string;
    result: LibrarySearch;
  } | null>(null);
  const [busy, setBusy] = useState<"index" | "search" | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const fingerprint = data?.nodes.map((n) => n.id).join(",") ?? "";
  const search =
    searchState?.fingerprint === fingerprint ? searchState.result : null;
  const matches = new Map(search?.matches.map((n) => [n.id, n]) ?? []);
  const nodes = (data?.nodes ?? []).filter(
    (n) => filter === "all" || n.modality === filter,
  );
  const plotted = nodes.filter(
    (n) => n.indexed && n.x !== null && n.y !== null,
  );
  const selected =
    search?.matches.find((n) => n.id === selectedId) ??
    data?.nodes.find((n) => n.id === selectedId);
  const selectedPlot = plotted.find((n) => n.id === selectedId);
  const rows = search
    ? search.matches.filter((n) => filter === "all" || n.modality === filter)
    : nodes;

  async function index() {
    setBusy("index");
    setNotice(null);
    try {
      const next = await apiFetch<CreatorLibrary>("/creator-library/index", {
        method: "POST",
      });
      cache.setQueryData(["creator-library"], next);
      setSearchState(null);
      setNotice(
        next.errorMessage ??
          (next.indexedNodes === next.totalNodes
            ? "Your library is ready to search."
            : "Batch saved. Continue indexing to add the remaining material."),
      );
    } catch (e) {
      setNotice(e instanceof Error ? e.message : "Indexing failed. Try again.");
      void refetch();
    } finally {
      setBusy(null);
    }
  }
  async function find(event: FormEvent) {
    event.preventDefault();
    if (!query.trim()) return;
    setBusy("search");
    setNotice(null);
    try {
      const result = await apiFetch<LibrarySearch>("/creator-library/search", {
        method: "POST",
        body: JSON.stringify({ query: query.trim() }),
      });
      setSearchState({ fingerprint, result });
      setSelectedId(result.matches[0]?.id ?? null);
    } catch (e) {
      setNotice(e instanceof Error ? e.message : "Search failed. Try again.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader
        title="Creator library"
        description="Explore the words and images that make your work yours."
        actions={
          <Link
            href="/settings"
            className="text-sm text-signal underline-offset-4 hover:underline"
          >
            Manage connections
          </Link>
        }
      />
      {isPending ? (
        <p role="status" className="text-sm text-muted-foreground">
          Reading your library…
        </p>
      ) : error ? (
        <div role="alert" className="rounded-xl border p-6">
          <p>{error.message}</p>
          <Button onClick={() => void refetch()} className="mt-3">
            Retry
          </Button>
        </div>
      ) : data && !data.totalNodes ? (
        <div className="rounded-2xl border bg-muted/20 px-6 py-16 text-center">
          <div className="mx-auto mb-5 grid size-14 place-items-center rounded-full border border-signal/30 font-mono text-xl text-signal">
            ∴
          </div>
          <h2 className="text-xl font-semibold">
            Start with something you’ve made
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-muted-foreground">
            Connect a YouTube channel in Settings and sync its content. For a
            demo, an operator can import a folder of transcripts, writing and
            thumbnails into your account.
          </p>
          <Link
            href="/settings"
            className="mt-6 inline-flex rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground focus-visible:outline-2 focus-visible:outline-signal"
          >
            Connect a channel
          </Link>
        </div>
      ) : data ? (
        <>
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border px-5 py-4">
            <div>
              <p className="text-sm font-medium">
                {data.displayName}{" "}
                <span className="ml-2 rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                  {data.sourceType === "folder_import"
                    ? "Imported library"
                    : "YouTube"}
                </span>
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {data.itemCount} sources · {data.indexedNodes} of{" "}
                {data.totalNodes} passages and images ready
              </p>
            </div>
            <div className="flex items-center gap-4">
              <div
                className="h-1.5 w-24 overflow-hidden rounded-full bg-muted"
                role="progressbar"
                aria-label="Library indexing"
                aria-valuenow={data.indexedNodes}
                aria-valuemin={0}
                aria-valuemax={data.totalNodes}
              >
                <div
                  className="h-full bg-signal"
                  style={{
                    width: `${(100 * data.indexedNodes) / data.totalNodes}%`,
                  }}
                />
              </div>
              <Button
                onClick={() => void index()}
                disabled={
                  !!busy || readOnly || data.indexedNodes === data.totalNodes
                }
                title={
                  readOnly
                    ? READ_ONLY_REASON
                    : "Adds up to 16 passages or images per batch"
                }
              >
                {busy === "index"
                  ? "Indexing batch…"
                  : data.indexedNodes === data.totalNodes
                    ? "Library ready"
                    : data.indexedNodes
                      ? "Continue indexing"
                      : "Index library"}
              </Button>
            </div>
          </div>
          {notice && (
            <p role="status" className="rounded-lg border px-4 py-3 text-sm">
              {notice}
            </p>
          )}
          {readOnly && (
            <p className="text-xs text-muted-foreground">
              Browse the map and source passages. Indexing and new searches are
              disabled for this read-only account.
            </p>
          )}
          <form onSubmit={find} className="flex gap-2">
            <label htmlFor="library-query" className="sr-only">
              Find something in your work
            </label>
            <Input
              id="library-query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              maxLength={1000}
              placeholder="Find something in your work — e.g. learning by making small projects"
              disabled={readOnly || !!busy}
              className="h-10"
            />
            <Button
              type="submit"
              size="lg"
              disabled={!query.trim() || !!busy || readOnly}
            >
              {busy === "search" ? "Searching…" : "Find matches"}
            </Button>
            {search && (
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setSearchState(null);
                  setSelectedId(null);
                }}
              >
                Clear
              </Button>
            )}
          </form>
          <div className="overflow-hidden rounded-2xl border">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-3">
              <div>
                <p className="text-sm font-medium">Your work, connected</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Similar material sits closer. Lines join passages from the
                  same source.
                </p>
              </div>
              <div className="flex gap-1" aria-label="Filter by material">
                {(["all", "text", "image"] as const).map((value) => (
                  <Button
                    key={value}
                    size="sm"
                    variant={filter === value ? "secondary" : "ghost"}
                    aria-pressed={filter === value}
                    onClick={() => setFilter(value)}
                  >
                    {value === "all"
                      ? "Everything"
                      : value === "text"
                        ? "Words"
                        : "Thumbnails"}
                  </Button>
                ))}
              </div>
            </div>
            <div className="grid lg:grid-cols-[1fr_320px]">
              <div
                className="relative h-[340px] overflow-hidden bg-muted/15 sm:h-[450px]"
                aria-label="Approximate content similarity map"
              >
                <svg
                  className="pointer-events-none absolute inset-0 size-full text-border"
                  aria-hidden="true"
                >
                  <defs>
                    <pattern
                      id="library-grid"
                      width="24"
                      height="24"
                      patternUnits="userSpaceOnUse"
                    >
                      <circle cx="1" cy="1" r="0.8" fill="currentColor" />
                    </pattern>
                  </defs>
                  <rect width="100%" height="100%" fill="url(#library-grid)" />
                  {selectedPlot &&
                    plotted
                      .filter(
                        (n) =>
                          n.itemId === selectedPlot.itemId &&
                          n.id !== selectedPlot.id,
                      )
                      .map((n) => (
                        <line
                          key={n.id}
                          x1={`${position(selectedPlot.x)}%`}
                          y1={`${position(selectedPlot.y)}%`}
                          x2={`${position(n.x)}%`}
                          y2={`${position(n.y)}%`}
                          stroke="var(--signal)"
                          strokeOpacity="0.35"
                          strokeDasharray="4 4"
                        />
                      ))}
                </svg>
                {!plotted.length && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center px-8 text-center">
                    <span className="font-mono text-4xl text-signal/60">∴</span>
                    <p className="mt-4 text-sm font-medium">
                      The map starts with your first index
                    </p>
                    <p className="mt-1 max-w-xs text-xs leading-5 text-muted-foreground">
                      Your sources are listed below. Index a batch to see how
                      passages and images relate.
                    </p>
                  </div>
                )}
                {plotted.map((n, i) => (
                  <button
                    key={n.id}
                    type="button"
                    onClick={() => setSelectedId(n.id)}
                    aria-label={`${n.modality === "image" ? "Thumbnail" : "Passage"}: ${n.title}`}
                    aria-pressed={selectedId === n.id}
                    title={n.title}
                    className={cn(
                      "absolute -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background bg-signal shadow-sm outline-offset-4 focus-visible:outline-2 focus-visible:outline-signal",
                      n.modality === "image"
                        ? "size-10 overflow-hidden rounded-md sm:size-12"
                        : "size-3.5 hover:scale-125",
                      selectedId === n.id &&
                        "ring-2 ring-signal ring-offset-3 ring-offset-background",
                      search && !matches.has(n.id) && "opacity-20",
                      search && matches.has(n.id) && "ring-2 ring-signal/30",
                      !search && "opacity-85",
                    )}
                    style={{
                      left: `${position(n.x)}%`,
                      top: `${position(n.y)}%`,
                      zIndex:
                        selectedId === n.id
                          ? 20
                          : n.modality === "image"
                            ? 10
                            : (i % 3) + 1,
                    }}
                  >
                    {n.modality === "image" && n.thumbnailUrl ? (
                      <img
                        src={n.thumbnailUrl}
                        alt=""
                        className="size-full object-cover"
                      />
                    ) : n.modality === "image" ? (
                      <span className="text-xs text-white">▧</span>
                    ) : null}
                  </button>
                ))}
                <div className="pointer-events-none absolute bottom-4 left-5 flex items-center gap-4 text-[10px] text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <span className="size-2 rounded-full bg-signal" />
                    Passage
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="size-2.5 rounded-sm border border-signal" />
                    Thumbnail
                  </span>
                </div>
              </div>
              <aside
                className="border-t bg-background p-5 lg:border-t-0 lg:border-l"
                aria-label="Selected source"
                aria-live="polite"
              >
                {selected ? (
                  <>
                    <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                      {selected.kind} ·{" "}
                      {selected.modality === "image" ? "thumbnail" : "passage"}
                      {selected.startSeconds !== null
                        ? ` · ${formatTime(selected.startSeconds)}`
                        : ""}
                    </p>
                    <h2 className="mt-2 text-base font-semibold leading-snug">
                      {selected.title}
                    </h2>
                    {selected.modality === "image" && selected.thumbnailUrl && (
                      <img
                        src={selected.thumbnailUrl}
                        alt={`Supplied thumbnail for ${selected.title}`}
                        className="mt-4 w-full rounded-lg border"
                      />
                    )}
                    <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">
                      {selected.excerpt}
                    </p>
                    {selected.url && /^https?:\/\//i.test(selected.url) && (
                      <a
                        href={selected.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-4 inline-block text-xs text-signal hover:underline"
                      >
                        Open original ↗
                      </a>
                    )}
                    <p className="mt-5 text-xs text-muted-foreground">
                      {selected.indexed
                        ? "Available for semantic retrieval"
                        : "Waiting to be indexed"}
                    </p>
                  </>
                ) : (
                  <div className="flex h-full flex-col justify-center">
                    <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                      Source inspector
                    </p>
                    <h2 className="mt-3 text-lg font-semibold">
                      Every point has a source
                    </h2>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                      Choose a passage or thumbnail to see the original
                      evidence. Search to find related material across words and
                      images.
                    </p>
                  </div>
                )}
              </aside>
            </div>
            <div className="flex flex-wrap justify-between gap-2 border-t px-5 py-3 text-[10px] text-muted-foreground">
              <span>
                Approximate 2D projection · distances are not quality or
                confidence scores
              </span>
              <span className="font-mono">
                {data.model} · {data.dimensions} dimensions
              </span>
            </div>
          </div>
          <div>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold">
                {search ? `${rows.length} matches` : "Source passages"}
              </h2>
              <span className="text-xs text-muted-foreground">
                {search
                  ? search.mode === "semantic"
                    ? "Matched by meaning"
                    : "Matched by words · semantic search unavailable"
                  : "Choose a row to inspect it"}
              </span>
            </div>
            {search?.mode === "semantic" &&
              data.indexedNodes < data.totalNodes && (
                <p className="mb-3 text-xs text-muted-foreground">
                  Search covers the indexed material. Continue indexing to
                  include the remaining sources.
                </p>
              )}
            {rows.length ? (
              <div className="max-h-[440px] overflow-y-auto rounded-xl border">
                {rows.map((n) => (
                  <button
                    key={n.id}
                    type="button"
                    onClick={() => setSelectedId(n.id)}
                    aria-pressed={selectedId === n.id}
                    className={cn(
                      "flex w-full items-start gap-4 border-b px-5 py-3 text-left last:border-0 hover:bg-muted/30 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-signal",
                      selectedId === n.id && "bg-signal/5",
                    )}
                  >
                    <span className="mt-1 font-mono text-xs text-signal">
                      {n.modality === "image" ? "▧" : "●"}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium">
                        {n.title}
                      </span>
                      <span className="mt-1 line-clamp-2 block text-xs leading-5 text-muted-foreground">
                        {n.excerpt}
                      </span>
                    </span>
                    <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                      {n.startSeconds !== null
                        ? formatTime(n.startSeconds)
                        : n.modality}
                      {!n.indexed ? " · pending" : ""}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="rounded-xl border p-5 text-sm text-muted-foreground">
                No matches in this view. Try a different phrase or material
                filter.
              </p>
            )}
          </div>
          {data.omittedPassages > 0 && (
            <p className="text-xs text-muted-foreground">
              This demo indexes up to six passages per source, ten thumbnails
              and 300 nodes. {data.omittedPassages} additional passages are
              outside that scope.
            </p>
          )}
        </>
      ) : null}
    </div>
  );
}

"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/common/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiFetch } from "@/lib/api-client";
import type { CreatorLibrary, LibrarySearch } from "@/lib/creator-library";
import { useReadOnly, READ_ONLY_REASON } from "@/lib/read-only";
import { cn } from "@/lib/utils";
import { thumbnailLabels } from "@/lib/library-layout";

const position = (value: number | null) => 8 + (value ?? 0.5) * 84;
const formatTime = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;

export default function LibraryPage() {
  const mapRef = useRef<HTMLDivElement>(null);
  const [mapSize, setMapSize] = useState({ width: 800, height: 540 });
  const cache = useQueryClient();
  const readOnly = useReadOnly();
  const { data, isPending, error, refetch } = useQuery({
    queryKey: ["creator-library"],
    queryFn: () => apiFetch<CreatorLibrary>("/creator-library"),
    staleTime: 30_000,
  });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "text" | "image">("all");
  const [topic, setTopic] = useState("all");
  const [zoom, setZoom] = useState(1);
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
    (n) =>
      (filter === "all" || n.modality === filter) &&
      (topic === "all" || n.tags.includes(topic)),
  );
  const plotted = nodes.filter(
    (n) => n.indexed && n.x !== null && n.y !== null,
  );
  const labels = thumbnailLabels(plotted, mapSize.width, mapSize.height);
  useEffect(() => {
    if (!data?.totalNodes) return;
    const element = mapRef.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => {
      if (entry.contentRect.width > 0)
        setMapSize({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [data?.totalNodes]);
  const selected =
    search?.matches.find((n) => n.id === selectedId) ??
    data?.nodes.find((n) => n.id === selectedId) ??
    nodes.find((n) => n.modality === "image" && n.indexed) ??
    nodes[0];
  const selectedPlot = plotted.find((n) => n.id === selected?.id);
  const relationNode = data?.nodes.find((n) => n.id === selected?.id);
  const neighbors = (relationNode?.related ?? []).flatMap((edge) => {
    const node = data?.nodes.find((n) => n.id === edge.nodeId);
    return node
      ? [{ node, similarity: edge.similarity, relation: edge.relation }]
      : [];
  });
  const relatedIds = new Set(neighbors.map(({ node }) => node.id));
  const topics = Array.from(
    new Set((data?.nodes ?? []).flatMap((n) => n.tags)),
  ).toSorted();
  const thumbnails = (data?.nodes ?? []).filter((n) => n.modality === "image");
  const rows = search
    ? search.matches.filter(
        (n) =>
          (filter === "all" || n.modality === filter) &&
          (topic === "all" || n.tags.includes(topic)),
      )
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
            Connect an account in Settings and read its published content to
            bring your words and images into the studio.
          </p>
          <Link
            href="/settings"
            className="mt-6 inline-flex rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground focus-visible:outline-2 focus-visible:outline-signal"
          >
            Connect an account
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
                    ? "Creator sources"
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
              placeholder="Find ideas, visual styles or buying advice across your work…"
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
          {thumbnails.length > 0 && (
            <div
              className="flex gap-3 overflow-x-auto pb-2"
              aria-label="Thumbnail collection"
            >
              {thumbnails.map((n) => (
                <button
                  key={n.id}
                  onClick={() => {
                    setSelectedId(n.id);
                    setFilter("all");
                    setTopic("all");
                  }}
                  aria-label={`Explore thumbnail: ${n.title}`}
                  aria-pressed={selected?.id === n.id}
                  className={cn(
                    "w-36 shrink-0 rounded-lg border bg-muted/20 p-1 text-left outline-offset-2 focus-visible:outline-2 focus-visible:outline-signal",
                    selected?.id === n.id && "border-signal",
                  )}
                >
                  {n.thumbnailUrl && (
                    <img
                      src={n.thumbnailUrl}
                      alt=""
                      className="aspect-video w-full rounded-md object-cover"
                    />
                  )}
                  <span className="mt-1.5 line-clamp-2 px-1 pb-1 text-[10px] leading-4 text-muted-foreground">
                    {n.title}
                  </span>
                </button>
              ))}
            </div>
          )}
          <div className="flex flex-wrap gap-1.5" aria-label="Filter by topic">
            {["all", ...topics].map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setTopic(value)}
                aria-pressed={topic === value}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs transition-colors focus-visible:outline-2 focus-visible:outline-signal",
                  topic === value
                    ? "border-signal/50 bg-signal/10 text-signal"
                    : "text-muted-foreground hover:bg-muted",
                )}
              >
                {value === "all" ? "All topics" : value}
              </button>
            ))}
          </div>
          <div className="overflow-hidden rounded-2xl border">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b px-5 py-3">
              <div>
                <p className="text-sm font-medium">Your work, connected</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Select a source to reveal its closest semantic neighbors.
                  Links use similarity in the full embedding space.
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
                ref={mapRef}
                className="relative h-[400px] overflow-hidden bg-muted/15 sm:h-[540px]"
                aria-label="Approximate content similarity map"
              >
                <div
                  className="absolute inset-0 transition-transform duration-300 motion-reduce:transition-none"
                  style={{
                    transform: `scale(${zoom})`,
                    transformOrigin: `${position(selectedPlot?.x ?? null)}% ${position(selectedPlot?.y ?? null)}%`,
                  }}
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
                    <rect
                      width="100%"
                      height="100%"
                      fill="url(#library-grid)"
                    />
                    {plotted
                      .filter((n) => n.modality === "image")
                      .map((n) => (
                        <g key={`anchor-${n.id}`}>
                          <line
                            x1={`${position(n.x)}%`}
                            y1={`${position(n.y)}%`}
                            x2={`${labels.get(n.id)?.x ?? position(n.x)}%`}
                            y2={`${labels.get(n.id)?.y ?? position(n.y)}%`}
                            stroke="currentColor"
                            strokeWidth="1"
                          />
                          <circle
                            cx={`${position(n.x)}%`}
                            cy={`${position(n.y)}%`}
                            r="3"
                            fill="var(--signal)"
                          />
                        </g>
                      ))}
                    {selectedPlot &&
                      plotted
                        .filter((n) => relatedIds.has(n.id))
                        .map((n) => (
                          <line
                            key={n.id}
                            x1={`${position(selectedPlot.x)}%`}
                            y1={`${position(selectedPlot.y)}%`}
                            x2={`${position(n.x)}%`}
                            y2={`${position(n.y)}%`}
                            stroke="var(--signal)"
                            strokeOpacity="0.65"
                            strokeDasharray={
                              neighbors.find((edge) => edge.node.id === n.id)
                                ?.relation === "cross_modal"
                                ? "5 4"
                                : undefined
                            }
                            strokeWidth="1.5"
                          />
                        ))}
                  </svg>
                  {!plotted.length && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center px-8 text-center">
                      <span className="font-mono text-4xl text-signal/60">
                        ∴
                      </span>
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
                      aria-pressed={selected?.id === n.id}
                      title={`${n.title} · ${n.language} · ${n.contentType}`}
                      className={cn(
                        "absolute -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-background bg-signal shadow-sm outline-offset-4 focus-visible:outline-2 focus-visible:outline-signal",
                        n.modality === "image"
                          ? "h-10 w-[70px] overflow-hidden rounded-md sm:h-[52px] sm:w-[92px]"
                          : n.kind === "profile"
                            ? "size-6"
                            : "size-3.5 hover:scale-125",
                        n.modality === "text" &&
                          n.kind === "post" &&
                          "bg-chart-2",
                        n.modality === "text" &&
                          n.kind === "article" &&
                          "bg-chart-3",
                        relatedIds.has(n.id) && "ring-2 ring-signal/40",
                        selected &&
                          !relatedIds.has(n.id) &&
                          n.id !== selected.id &&
                          !search &&
                          "opacity-60",
                        selected?.id === n.id &&
                          "ring-2 ring-signal ring-offset-3 ring-offset-background",
                        search && !matches.has(n.id) && "opacity-20",
                        search && matches.has(n.id) && "ring-2 ring-signal/30",
                      )}
                      style={{
                        left: `${labels.get(n.id)?.x ?? position(n.x)}%`,
                        top: `${labels.get(n.id)?.y ?? position(n.y)}%`,
                        zIndex:
                          selected?.id === n.id
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
                      ) : n.kind === "profile" ? (
                        <span className="text-xs text-primary-foreground">
                          ◎
                        </span>
                      ) : null}
                    </button>
                  ))}
                </div>
                <div
                  className="absolute right-4 top-4 flex items-center gap-1 rounded-lg border bg-background/95 p-1 shadow-sm"
                  aria-label="Map zoom"
                >
                  <Button
                    size="icon-sm"
                    variant="ghost"
                    aria-label="Zoom out"
                    onClick={() => setZoom(Math.max(1, zoom - 0.5))}
                    disabled={zoom === 1}
                  >
                    −
                  </Button>
                  <span className="w-9 text-center font-mono text-[10px]">
                    {zoom}×
                  </span>
                  <Button
                    size="icon-sm"
                    variant="ghost"
                    aria-label="Zoom into selected source"
                    onClick={() => setZoom(Math.min(3, zoom + 0.5))}
                    disabled={zoom === 3}
                  >
                    +
                  </Button>
                </div>
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
                className="border-t bg-background p-5 lg:max-h-[540px] lg:overflow-y-auto lg:border-t-0 lg:border-l"
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
                    {selected.thumbnailUrl && (
                      <img
                        src={selected.thumbnailUrl}
                        alt={`Thumbnail for ${selected.title}`}
                        className="mt-4 w-full rounded-lg border"
                      />
                    )}
                    <div className="mt-3 flex flex-wrap gap-1.5 text-[10px] text-muted-foreground">
                      <span className="rounded border px-2 py-0.5">
                        {selected.platform}
                      </span>
                      <span className="rounded border px-2 py-0.5">
                        {selected.language === "hi"
                          ? "Hindi"
                          : selected.language === "en"
                            ? "English"
                            : selected.language}
                      </span>
                      <span className="rounded border px-2 py-0.5">
                        {selected.contentType}
                      </span>
                    </div>
                    {selected.attribution && (
                      <p className="mt-2 text-[10px] text-muted-foreground">
                        {selected.attribution}
                      </p>
                    )}
                    <p className="mt-4 max-h-48 overflow-y-auto whitespace-pre-wrap text-sm leading-6 text-muted-foreground">
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
                    {neighbors.length > 0 && (
                      <div className="mt-5 space-y-2 border-t pt-4">
                        <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                          Closest related sources
                        </p>
                        {neighbors.map(({ node, similarity, relation }) => (
                          <button
                            key={node.id}
                            onClick={() => {
                              setSelectedId(node.id);
                              setTopic("all");
                              setFilter("all");
                            }}
                            className="flex w-full items-center gap-2 rounded-lg border p-2 text-left hover:bg-muted/40 focus-visible:outline-2 focus-visible:outline-signal"
                          >
                            {node.thumbnailUrl ? (
                              <img
                                src={node.thumbnailUrl}
                                alt=""
                                className="h-8 w-12 shrink-0 rounded object-cover"
                              />
                            ) : (
                              <span className="grid size-8 shrink-0 place-items-center rounded bg-muted text-signal">
                                ¶
                              </span>
                            )}
                            <span className="min-w-0 flex-1">
                              <span className="line-clamp-2 text-[11px] leading-4">
                                {node.title}
                              </span>
                              <span className="text-[9px] text-muted-foreground">
                                {relation === "cross_modal"
                                  ? "Closest " +
                                    (node.modality === "image"
                                      ? "image"
                                      : "words")
                                  : node.modality}{" "}
                                · cosine {similarity.toFixed(3)}
                              </span>
                            </span>
                          </button>
                        ))}
                      </div>
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
                Approximate 2D projection · image tiles connect to their true
                positions · distances are not quality scores
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
                      <span className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">
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
              The map includes up to six passages sampled across each source,
              ten thumbnails and 300 nodes. {data.omittedPassages} additional
              passages are outside that scope.
            </p>
          )}
        </>
      ) : null}
    </div>
  );
}

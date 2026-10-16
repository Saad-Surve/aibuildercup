"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight01Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { PageHeader } from "@/components/common/page-header";
import { PlatformLogo, platformLabel } from "@/components/calendar/platform";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { apiFetch } from "@/lib/api-client";
import { languageLabel } from "@/lib/onboarding";
import type {
  CreatorLibrary,
  LibraryNode,
  LibrarySearch,
} from "@/lib/creator-library";
import { useReadOnly, READ_ONLY_REASON } from "@/lib/read-only";
import { cn } from "@/lib/utils";

const position = (value: number | null) => 8 + (value ?? 0.5) * 84;
const formatTime = (seconds: number) =>
  `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;

function nodeTypeLabel(node: LibraryNode) {
  if (node.modality === "image") return "Thumbnail";
  if (node.kind === "profile") return "Profile";
  if (node.kind === "video") return "Video passage";
  return node.kind === "article" ? "Article" : "Post";
}

function relationLabel(
  selected: LibraryNode,
  neighbor: LibraryNode,
  relation: "nearest" | "cross_modal",
) {
  if (relation === "cross_modal" || selected.modality !== neighbor.modality) {
    if (neighbor.modality === "image") {
      return "Thumbnail matches this passage";
    }
    if (selected.modality === "image") {
      return "Passage matches this thumbnail";
    }
    return "Words and image share the same idea";
  }
  if (selected.modality === "image" && neighbor.modality === "image") {
    return "Similar visual style";
  }
  if (selected.kind === "profile" || neighbor.kind === "profile") {
    return "Similar creator context";
  }
  return "Similar wording";
}

function ThumbnailImage({
  src,
  alt,
  className,
}: {
  src: string;
  alt: string;
  className?: string;
}) {
  return <img src={src} alt={alt} loading="lazy" className={className} />;
}

function NodeMarker({ node }: { node: LibraryNode }) {
  if (node.modality === "image") {
    return (
      <span className="grid size-4 place-items-center rounded-[3px] border-2 border-chart-3 bg-background shadow-sm">
        <span className="h-1.5 w-2 rounded-[1px] bg-chart-3" />
      </span>
    );
  }
  if (node.kind === "profile") {
    return (
      <span className="grid size-5 place-items-center rounded-full border-2 border-foreground bg-background shadow-sm">
        <span className="size-1.5 rounded-full bg-foreground" />
      </span>
    );
  }
  if (node.kind === "article" || node.kind === "post") {
    return (
      <span className="size-3.5 rotate-45 rounded-[3px] border-2 border-background bg-chart-2 shadow-sm" />
    );
  }
  return (
    <span className="size-3.5 rounded-full border-2 border-background bg-signal shadow-sm" />
  );
}

function MapLegend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t bg-muted/15 px-5 py-3 text-[11px] text-muted-foreground">
      <span className="font-medium text-foreground">Map key</span>
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 rounded-full bg-signal" />
        Video passage
      </span>
      <span className="flex items-center gap-1.5">
        <span className="size-2.5 rotate-45 rounded-[2px] bg-chart-2" />
        Article or post
      </span>
      <span className="flex items-center gap-1.5">
        <span className="grid size-3 place-items-center rounded-[2px] border border-chart-3 bg-background">
          <span className="h-1 w-1.5 rounded-[1px] bg-chart-3" />
        </span>
        Thumbnail
      </span>
      <span className="flex items-center gap-1.5">
        <span className="grid size-3 place-items-center rounded-full border border-foreground bg-background">
          <span className="size-1 rounded-full bg-foreground" />
        </span>
        Profile
      </span>
      <span className="hidden h-4 w-px bg-border sm:block" />
      <span className="flex items-center gap-1.5">
        <svg aria-hidden="true" width="24" height="6" viewBox="0 0 24 6">
          <path d="M1 3h22" stroke="currentColor" strokeWidth="1.5" />
        </svg>
        Same kind
      </span>
      <span className="flex items-center gap-1.5">
        <svg aria-hidden="true" width="24" height="6" viewBox="0 0 24 6">
          <path
            d="M1 3h22"
            stroke="currentColor"
            strokeDasharray="4 3"
            strokeWidth="1.5"
          />
        </svg>
        Words ↔ image
      </span>
    </div>
  );
}

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
  const selected = selectedId
    ? (search?.matches.find((n) => n.id === selectedId) ??
      data?.nodes.find((n) => n.id === selectedId))
    : undefined;
  const selectedPlot = plotted.find((n) => n.id === selected?.id);
  const relationNode = data?.nodes.find((n) => n.id === selected?.id);
  const neighbors = (relationNode?.related ?? []).flatMap((edge) => {
    const node = data?.nodes.find((n) => n.id === edge.nodeId);
    return node
      ? [{ node, similarity: edge.similarity, relation: edge.relation }]
      : [];
  });
  const relatedIds = new Set(neighbors.map(({ node }) => node.id));
  const labeledIds = new Set([
    ...(selectedPlot ? [selectedPlot.id] : []),
    ...neighbors
      .filter(({ node }) => plotted.some((item) => item.id === node.id))
      .slice(0, 3)
      .map(({ node }) => node.id),
  ]);
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
            ? "Creator library is ready to search."
            : "Saved. Process more to add the rest."),
      );
    } catch (e) {
      setNotice(
        e instanceof Error
          ? e.message
          : "Could not process your library. Try again.",
      );
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
                aria-label="Library processing"
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
                title={readOnly ? READ_ONLY_REASON : "Process your library"}
              >
                {busy === "index"
                  ? "Processing…"
                  : data.indexedNodes === data.totalNodes
                    ? "Library ready"
                    : data.indexedNodes
                      ? "Process more"
                      : "Process library"}
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
              Browse the map and source passages. Processing and new searches
              are disabled in the demo.
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
                    <ThumbnailImage
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
                onClick={() => {
                  setTopic(value);
                  setSelectedId(null);
                }}
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
          <section
            className="overflow-hidden rounded-2xl border"
            aria-labelledby="library-map-title"
          >
            <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
              <div>
                <h2 id="library-map-title" className="text-sm font-medium">
                  Your work, connected
                </h2>
                <p
                  id="library-map-explainer"
                  className="mt-1 text-xs leading-5 text-muted-foreground"
                >
                  Closer together means a similar topic or style; lines show the
                  strongest connections for the item you select.
                </p>
              </div>
              <div className="flex gap-1" aria-label="Filter by material">
                {(["all", "text", "image"] as const).map((value) => (
                  <Button
                    key={value}
                    size="sm"
                    variant={filter === value ? "secondary" : "ghost"}
                    aria-pressed={filter === value}
                    onClick={() => {
                      setFilter(value);
                      setSelectedId(null);
                    }}
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
            <MapLegend />
            <div className="grid lg:grid-cols-[minmax(0,1fr)_320px]">
              <div
                className="relative h-[400px] overflow-hidden border-t bg-muted/10 sm:h-[540px] lg:border-t-0"
                role="group"
                aria-label="Related material map"
                aria-describedby="library-map-explainer"
              >
                <div
                  className="absolute inset-0 transition-transform duration-300 motion-reduce:transition-none"
                  style={{
                    transform: `scale(${zoom})`,
                    transformOrigin: `${position(selectedPlot?.x ?? null)}% ${position(selectedPlot?.y ?? null)}%`,
                  }}
                >
                  {selectedPlot && (
                    <span
                      aria-hidden="true"
                      className="pointer-events-none absolute size-44 -translate-x-1/2 -translate-y-1/2 rounded-full bg-signal/8 blur-2xl"
                      style={{
                        left: `${position(selectedPlot.x)}%`,
                        top: `${position(selectedPlot.y)}%`,
                      }}
                    />
                  )}
                  <svg
                    className="pointer-events-none absolute inset-0 size-full"
                    aria-hidden="true"
                  >
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
                            strokeOpacity="0.72"
                            strokeDasharray={
                              neighbors.find((edge) => edge.node.id === n.id)
                                ?.relation === "cross_modal" ||
                              selectedPlot.modality !== n.modality
                                ? "5 4"
                                : undefined
                            }
                            strokeWidth="1.5"
                            vectorEffect="non-scaling-stroke"
                          />
                        ))}
                  </svg>
                  {!plotted.length && (
                    <div className="absolute inset-0 flex flex-col items-center justify-center px-8 text-center">
                      <span className="font-mono text-4xl text-signal/60">
                        ∴
                      </span>
                      <p className="mt-4 text-sm font-medium">
                        The map appears after your first batch is processed
                      </p>
                      <p className="mt-1 max-w-xs text-xs leading-5 text-muted-foreground">
                        Your sources are listed below. Process a batch to see
                        how passages and images relate.
                      </p>
                    </div>
                  )}
                  {plotted.map((n, i) => {
                    const isSelected = selected?.id === n.id;
                    const isRelated = relatedIds.has(n.id);
                    const isDimmed =
                      (!!selected && !isSelected && !isRelated) ||
                      (!!search && !matches.has(n.id));
                    const showLabel = labeledIds.has(n.id);
                    const labelOnLeft = position(n.x) > 68;
                    return (
                      <Tooltip key={n.id}>
                        <TooltipTrigger
                          render={
                            <button
                              type="button"
                              onClick={() => setSelectedId(n.id)}
                              aria-label={`${nodeTypeLabel(n)}: ${n.title}. ${languageLabel(n.language)}`}
                              aria-pressed={isSelected}
                              className={cn(
                                "absolute grid size-8 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full outline-none transition-[opacity,transform,box-shadow] duration-150 hover:scale-110 focus-visible:ring-2 focus-visible:ring-signal focus-visible:ring-offset-2 focus-visible:ring-offset-background motion-reduce:transition-none motion-reduce:hover:scale-100",
                                isRelated && "ring-1 ring-signal/50",
                                isSelected &&
                                  "bg-background/80 ring-2 ring-signal ring-offset-2 ring-offset-background",
                                isDimmed &&
                                  "opacity-20 hover:opacity-70 focus-visible:opacity-100",
                                search &&
                                  matches.has(n.id) &&
                                  "ring-2 ring-signal/35",
                              )}
                              style={{
                                left: `${position(n.x)}%`,
                                top: `${position(n.y)}%`,
                                zIndex: isSelected
                                  ? 20
                                  : isRelated
                                    ? 10
                                    : (i % 3) + 1,
                              }}
                            />
                          }
                        >
                          <NodeMarker node={n} />
                          {showLabel && (
                            <span
                              className={cn(
                                "pointer-events-none absolute top-1/2 block max-w-32 -translate-y-1/2 truncate rounded-md border bg-background/95 px-1.5 py-0.5 text-[9px] shadow-sm",
                                labelOnLeft
                                  ? "right-full mr-1.5"
                                  : "left-full ml-1.5",
                                isSelected
                                  ? "font-medium text-foreground"
                                  : "text-muted-foreground",
                              )}
                            >
                              {n.title}
                            </span>
                          )}
                        </TooltipTrigger>
                        <TooltipContent
                          side="top"
                          sideOffset={8}
                          className="block w-60 overflow-hidden border bg-popover p-0 text-popover-foreground shadow-lg motion-reduce:data-open:animate-none motion-reduce:data-closed:animate-none"
                        >
                          {n.modality === "image" && n.thumbnailUrl && (
                            <ThumbnailImage
                              src={n.thumbnailUrl}
                              alt=""
                              className="aspect-video w-full object-cover"
                            />
                          )}
                          <span className="block px-3 py-2.5">
                            <span className="block line-clamp-2 font-medium leading-4">
                              {n.title}
                            </span>
                            <span className="mt-1 block text-[10px] text-muted-foreground">
                              {nodeTypeLabel(n)} · {languageLabel(n.language)}
                            </span>
                          </span>
                        </TooltipContent>
                      </Tooltip>
                    );
                  })}
                </div>
                {plotted.length > 0 && !selected && (
                  <div className="pointer-events-none absolute bottom-4 left-1/2 w-[calc(100%-2rem)] max-w-sm -translate-x-1/2 rounded-lg border bg-background/95 px-3 py-2 text-center text-xs text-muted-foreground shadow-sm">
                    Click a marker—or Tab to one—to reveal its closest
                    connections.
                  </div>
                )}
                <div
                  className="absolute right-3 top-3 flex items-center gap-1 rounded-lg border bg-background/95 p-1 shadow-sm sm:right-4 sm:top-4"
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
                    disabled={!selectedPlot || zoom === 3}
                  >
                    +
                  </Button>
                </div>
              </div>
              <aside
                className="min-h-64 border-t bg-background p-5 lg:max-h-[540px] lg:overflow-y-auto lg:border-t-0 lg:border-l"
                aria-label="Selected source"
                aria-live="polite"
              >
                {selected ? (
                  <>
                    <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                      {nodeTypeLabel(selected)}
                      {selected.startSeconds !== null
                        ? ` · ${formatTime(selected.startSeconds)}`
                        : ""}
                    </p>
                    <h3 className="mt-2 text-base font-semibold leading-snug">
                      {selected.title}
                    </h3>
                    {selected.thumbnailUrl && (
                      <ThumbnailImage
                        src={selected.thumbnailUrl}
                        alt={`Thumbnail for ${selected.title}`}
                        className="mt-4 aspect-video w-full rounded-lg border object-cover"
                      />
                    )}
                    <div className="mt-3 flex flex-wrap gap-1.5 text-[10px] text-muted-foreground">
                      <span className="inline-flex items-center gap-1 rounded border px-2 py-0.5">
                        <PlatformLogo platform={selected.platform} size={12} />
                        {platformLabel(selected.platform)}
                      </span>
                      <span className="rounded border px-2 py-0.5">
                        {languageLabel(selected.language)}
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
                        className="mt-4 inline-flex items-center gap-1 text-xs text-signal hover:underline focus-visible:outline-2 focus-visible:outline-signal"
                      >
                        Open original
                        <Icon icon={ArrowUpRight01Icon} className="size-3" />
                      </a>
                    )}
                    {neighbors.length > 0 && (
                      <div className="mt-5 space-y-2 border-t pt-4">
                        <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                          Why these are close
                        </p>
                        {neighbors.map(({ node, relation }) => (
                          <button
                            key={node.id}
                            onClick={() => {
                              setSelectedId(node.id);
                              setTopic("all");
                              setFilter("all");
                            }}
                            className="flex w-full items-center gap-2.5 rounded-lg border p-2.5 text-left hover:bg-muted/40 focus-visible:outline-2 focus-visible:outline-signal"
                          >
                            {node.thumbnailUrl ? (
                              <ThumbnailImage
                                src={node.thumbnailUrl}
                                alt=""
                                className="h-10 w-14 shrink-0 rounded object-cover"
                              />
                            ) : (
                              <span className="grid size-10 shrink-0 place-items-center rounded-md bg-muted">
                                <NodeMarker node={node} />
                              </span>
                            )}
                            <span className="min-w-0 flex-1">
                              <span className="block text-[10px] font-medium text-signal">
                                {relationLabel(selected, node, relation)}
                              </span>
                              <span className="mt-0.5 line-clamp-2 block text-[11px] leading-4">
                                {node.title}
                              </span>
                            </span>
                            <svg
                              aria-hidden="true"
                              className="shrink-0 text-muted-foreground"
                              width="20"
                              height="6"
                              viewBox="0 0 20 6"
                            >
                              <path
                                d="M1 3h18"
                                stroke="currentColor"
                                strokeDasharray={
                                  relation === "cross_modal" ||
                                  selected.modality !== node.modality
                                    ? "4 3"
                                    : undefined
                                }
                                strokeWidth="1.5"
                              />
                            </svg>
                          </button>
                        ))}
                      </div>
                    )}
                    <p className="mt-5 text-xs text-muted-foreground">
                      {selected.indexed
                        ? "Ready to use in search and drafts"
                        : "Waiting to be processed"}
                    </p>
                  </>
                ) : (
                  <div className="flex h-full flex-col justify-center">
                    <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                      Source details
                    </p>
                    <h3 className="mt-3 text-lg font-semibold">
                      Pick a marker to start
                    </h3>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                      Select any passage, post, thumbnail or profile. Its
                      strongest connections will appear on the map, with the
                      reason each one is related.
                    </p>
                    <div className="mt-5 flex items-center gap-3 rounded-lg border bg-muted/20 p-3 text-xs text-muted-foreground">
                      <span className="grid size-9 shrink-0 place-items-center rounded-full bg-background shadow-sm ring-1 ring-border">
                        <span className="size-3 rounded-full bg-signal" />
                      </span>
                      Click a dot, or use Tab and Enter.
                    </div>
                  </div>
                )}
              </aside>
            </div>
          </section>
          <div>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold">
                {search ? `${rows.length} matches` : "Source passages"}
              </h2>
              <span className="text-xs text-muted-foreground">
                {search
                  ? search.mode === "semantic"
                    ? "Related"
                    : "Matched by words. Search by meaning is unavailable right now."
                  : "Choose a row to inspect it"}
              </span>
            </div>
            {search?.mode === "semantic" &&
              data.indexedNodes < data.totalNodes && (
                <p className="mb-3 text-xs text-muted-foreground">
                  Search covers processed material. Process more to include the
                  rest.
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
        </>
      ) : null}
    </div>
  );
}

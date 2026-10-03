"use client";

import { useEffect, useRef, useState } from "react";
import type videojs from "video.js";
import "video.js/dist/video-js.css";
import "./video-player-skin.css";
import { Alert02Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import {
  CaptionOverlay,
  DEFAULT_CAPTION_LINES,
  useCaptionPreview,
} from "@/components/projects/studio/caption-preview";
import { Skeleton } from "@/components/ui/skeleton";
import { ensurePoster, getCachedPoster, getVideoBlob } from "@/lib/local-media";
import { getDownloadUrl } from "@/lib/projects";
import type { Asset } from "@/lib/types";

/*
 * Source video player (video.js default theme + signal accents).
 *
 * Prefers the locally cached upload (IndexedDB, written by the dropzone at
 * upload time) so playback is instant and works offline; otherwise streams
 * from the signed playback URL. Transcript segments seek the video through a
 * `creator-studio:seek` window event.
 */
export function SourceVideoPlayer({
  projectId,
  asset,
  onDuration,
  captionLines,
  coverUrl,
}: {
  projectId: string;
  asset: Asset;
  onDuration?: (durationMs: number) => void;
  /** Transcript lines shown in the caption preview overlay, if a style is active. */
  captionLines?: string[];
  /** Applied thumbnail cover; preferred over the captured frame poster. */
  coverUrl?: string | null;
}) {
  const captionPreview = useCaptionPreview();
  const [media, setMedia] = useState<{ assetId: string; src: string } | null>(
    null,
  );
  const [framePoster, setFramePoster] = useState<{
    assetId: string;
    url: string;
  } | null>(null);
  const [failure, setFailure] = useState<{ assetId: string } | null>(null);

  // Render-time reads only: the effect below writes state from async work.
  const cachedPoster = getCachedPoster(asset.assetId, projectId);

  useEffect(() => {
    let alive = true;
    let objectUrl: string | null = null;

    void (async () => {
      const local = await getVideoBlob(asset.assetId);
      if (!alive) return;
      if (local) {
        objectUrl = URL.createObjectURL(local);
        setMedia({ assetId: asset.assetId, src: objectUrl });
      } else {
        try {
          const playback = await getDownloadUrl(projectId, asset.assetId);
          if (alive) setMedia({ assetId: asset.assetId, src: playback.url });
        } catch {
          if (alive) setFailure({ assetId: asset.assetId });
        }
      }
      if (!coverUrl && !getCachedPoster(asset.assetId, projectId)) {
        const url = await ensurePoster({
          projectId,
          assetId: asset.assetId,
          sizeBytes: asset.sizeBytes,
        });
        if (alive && url) setFramePoster({ assetId: asset.assetId, url });
      }
    })();

    return () => {
      alive = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [projectId, asset.assetId, asset.sizeBytes, coverUrl]);

  const src = media?.assetId === asset.assetId ? media.src : null;
  const failed = failure?.assetId === asset.assetId;
  const poster =
    coverUrl ??
    cachedPoster ??
    (framePoster?.assetId === asset.assetId ? framePoster.url : null);

  if (failed) {
    return (
      <div className="flex aspect-video w-full flex-col items-center justify-center gap-2 rounded-lg bg-muted text-center shadow-sm ring-1 ring-foreground/10">
        <Icon icon={Alert02Icon} className="size-5 text-muted-foreground" />
        <p className="px-6 text-sm text-muted-foreground">
          Could not load this video. It may have been uploaded in another
          browser — upload it again to watch it here.
        </p>
      </div>
    );
  }

  return (
    <div className="relative">
      <div className="studio-video overflow-hidden rounded-lg bg-black shadow-sm ring-1 ring-foreground/10">
        {src ? (
          <StudioPlayer
            key={asset.assetId}
            projectId={projectId}
            src={src}
            mimeType={asset.mimeType}
            poster={poster}
            onDuration={onDuration}
          />
        ) : (
          <Skeleton className="aspect-video w-full rounded-none" />
        )}
      </div>
      {captionPreview?.style ? (
        <CaptionOverlay
          style={captionPreview.style}
          lines={
            captionLines && captionLines.length > 0
              ? captionLines
              : DEFAULT_CAPTION_LINES
          }
        />
      ) : null}
    </div>
  );
}

type Player = ReturnType<typeof videojs>;

function StudioPlayer({
  projectId,
  src,
  mimeType,
  poster,
  onDuration,
}: {
  projectId: string;
  src: string;
  mimeType: string;
  poster: string | null;
  onDuration?: (durationMs: number) => void;
}) {
  // The <video> element is created imperatively and owned by video.js, never by
  // React. Letting React render it led to the player disposing the node out from
  // under React on re-render, which is what made the video vanish.
  const containerRef = useRef<HTMLDivElement | null>(null);
  const playerRef = useRef<Player | null>(null);
  const onDurationRef = useRef(onDuration);
  // Read at init time only; later poster changes are applied by the effect below.
  const initialPosterRef = useRef(poster);

  useEffect(() => {
    onDurationRef.current = onDuration;
  }, [onDuration]);

  // video.js touches the DOM, so it loads lazily inside the effect: nothing
  // player-related evaluates during SSR/prerender. The player is created once
  // per source; later poster/size updates are applied to the live instance.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    let cancelled = false;
    let player: Player | null = null;

    void (async () => {
      const { default: videojs } = await import("video.js");
      if (cancelled) return;
      const video = document.createElement("video");
      video.className = "video-js vjs-big-play-centered";
      video.playsInline = true;
      container.appendChild(video);
      player = videojs(video, {
        controls: true,
        autoplay: false,
        preload: "metadata",
        fluid: true,
        // Pin a landscape box regardless of the source: a portrait (9:16) upload would
        // otherwise resize the fluid player taller than the fixed-height card and get
        // clipped, which reads as a zoomed/cropped preview. The video itself is
        // letterboxed inside (see `object-fit: contain` in video-player-skin.css).
        aspectRatio: "16:9",
        playsinline: true,
        responsive: true,
        poster: initialPosterRef.current ?? undefined,
        sources: [{ src, type: mimeType }],
        playbackRates: [0.5, 1, 1.25, 1.5, 2],
        controlBar: {
          volumePanel: { inline: true },
        },
      });
      playerRef.current = player;

      const reportDuration = () => {
        const duration = player?.duration();
        if (typeof duration === "number" && Number.isFinite(duration)) {
          onDurationRef.current?.(Math.round(duration * 1000));
        }
      };
      player.on("loadedmetadata", reportDuration);
      player.on("durationchange", reportDuration);
      reportDuration();
    })();

    return () => {
      cancelled = true;
      playerRef.current = null;
      player?.dispose();
    };
  }, [src, mimeType]);

  // The frame poster is captured after the player mounts; push it in when it lands.
  useEffect(() => {
    if (poster) playerRef.current?.poster(poster);
  }, [poster]);

  // Transcript segments seek the video through a window event so the
  // transcript panel stays decoupled from this player instance.
  useEffect(() => {
    const onSeek = (event: Event) => {
      const detail = (
        event as CustomEvent<{ projectId: string; seconds: number }>
      ).detail;
      if (detail.projectId !== projectId) return;
      const player = playerRef.current;
      if (player && Number.isFinite(detail.seconds)) {
        player.currentTime(Math.max(0, detail.seconds));
      }
    };
    window.addEventListener("creator-studio:seek", onSeek);
    return () => window.removeEventListener("creator-studio:seek", onSeek);
  }, [projectId]);

  return <div ref={containerRef} className="w-full" />;
}

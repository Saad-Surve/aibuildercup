"use client";

import { useEffect, useRef, useState } from "react";
import type videojs from "video.js";
import "video.js/dist/video-js.css";
import "./video-player-skin.css";
import { Alert02Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { ensurePoster, getCachedPoster, getVideoBlob } from "@/lib/local-media";
import { getPlaybackUrl } from "@/lib/projects";
import type { Asset } from "@/lib/types";

/*
 * Source video player (video.js default theme + signal accents).
 *
 * Prefers the locally cached upload (IndexedDB, written by the dropzone at
 * upload time) so playback is instant and works offline; otherwise streams
 * from the signed playback URL. Transcript segments seek the video through a
 * `creator-studio:seek` window event. Caption cues arrive with the
 * transcription pipeline (backend stores the VTT; no caption URL yet).
 */
export function SourceVideoPlayer({
  projectId,
  asset,
}: {
  projectId: string;
  asset: Asset;
}) {
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
          const playback = await getPlaybackUrl(projectId, asset.assetId);
          if (alive) setMedia({ assetId: asset.assetId, src: playback.url });
        } catch {
          if (alive) setFailure({ assetId: asset.assetId });
        }
      }
      if (!getCachedPoster(asset.assetId, projectId)) {
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
  }, [projectId, asset.assetId, asset.sizeBytes]);

  const src = media?.assetId === asset.assetId ? media.src : null;
  const failed = failure?.assetId === asset.assetId;
  const poster =
    cachedPoster ??
    (framePoster?.assetId === asset.assetId ? framePoster.url : null);

  if (failed) {
    return (
      <div className="flex aspect-video w-full flex-col items-center justify-center gap-2 rounded-xl bg-muted text-center shadow-sm ring-1 ring-foreground/10">
        <Icon icon={Alert02Icon} className="size-5 text-muted-foreground" />
        <p className="px-6 text-sm text-muted-foreground">
          Could not load this video. It may have been uploaded in another
          browser — upload it again to watch it here.
        </p>
      </div>
    );
  }

  return (
    <div className="studio-video overflow-hidden rounded-xl bg-black shadow-sm ring-1 ring-foreground/10">
      {src ? (
        <StudioPlayer
          key={asset.assetId}
          projectId={projectId}
          src={src}
          mimeType={asset.mimeType}
          poster={poster}
        />
      ) : (
        <Skeleton className="aspect-video w-full rounded-none" />
      )}
    </div>
  );
}

type Player = ReturnType<typeof videojs>;

function StudioPlayer({
  projectId,
  src,
  mimeType,
  poster,
}: {
  projectId: string;
  src: string;
  mimeType: string;
  poster: string | null;
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const playerRef = useRef<Player | null>(null);

  // video.js touches the DOM, so it loads lazily inside the effect: nothing
  // player-related evaluates during SSR/prerender.
  useEffect(() => {
    let cancelled = false;

    void (async () => {
      const { default: videojs } = await import("video.js");
      if (cancelled || !videoRef.current) return;
      playerRef.current = videojs(videoRef.current, {
        controls: true,
        autoplay: false,
        preload: "metadata",
        fluid: true,
        playsinline: true,
        responsive: true,
        poster: poster ?? undefined,
        sources: [{ src, type: mimeType }],
        playbackRates: [0.5, 1, 1.25, 1.5, 2],
        controlBar: {
          volumePanel: { inline: true },
        },
      });
    })();

    return () => {
      cancelled = true;
      playerRef.current?.dispose();
      playerRef.current = null;
    };
  }, [src, mimeType, poster]);

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

  return (
    <div data-vjs-player>
      <video
        ref={videoRef}
        className="video-js vjs-big-play-centered"
        playsInline
      >
        {/* Caption cues arrive with the transcription pipeline. */}
        <track kind="captions" />
      </video>
    </div>
  );
}

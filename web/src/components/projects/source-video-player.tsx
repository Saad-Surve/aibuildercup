"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { Alert02Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { Skeleton } from "@/components/ui/skeleton";
import { ensurePoster, getCachedPoster, getVideoBlob } from "@/lib/local-media";
import { getPlaybackUrl } from "@/lib/projects";
import type { Asset } from "@/lib/types";

/*
 * Plays an uploaded source video. Prefers the locally cached upload
 * (IndexedDB, written by the dropzone at upload time) so playback is instant
 * and works offline; otherwise streams from the signed playback URL.
 */
export function SourceVideoPlayer({
  projectId,
  asset,
}: {
  projectId: string;
  asset: Asset;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
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
    <div className="overflow-hidden rounded-xl bg-black shadow-sm ring-1 ring-foreground/10">
      {src ? (
        <motion.video
          ref={videoRef}
          controls
          playsInline
          preload="metadata"
          src={src}
          poster={poster ?? undefined}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3 }}
          className="aspect-video max-h-[60vh] w-full"
        >
          {/* Caption cues arrive with the transcription pipeline. */}
          <track kind="captions" />
        </motion.video>
      ) : (
        <Skeleton className="aspect-video w-full rounded-none" />
      )}
    </div>
  );
}

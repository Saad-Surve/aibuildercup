"use client";

import Link from "next/link";
import { Icon } from "@/components/common/icon";
import { YouTubeConnections } from "@/components/projects/studio/youtube-connections";
import {
  YoutubeIcon,
  InstagramIcon,
  Facebook01Icon,
  Linkedin01Icon,
} from "@hugeicons/core-free-icons";

/** One connection surface shared by onboarding and Settings; OAuth remains provider-specific. */
export function AccountConnections({
  redirectPath,
  beforeConnect,
}: {
  redirectPath: string;
  beforeConnect?: () => Promise<void>;
}) {
  return (
    <div className="space-y-5">
      <section className="overflow-hidden rounded-xl border">
        <div className="flex items-start gap-3 border-b bg-muted/20 px-4 py-3">
          <Icon icon={YoutubeIcon} className="mt-0.5 text-signal" />
          <div>
            <h2 className="text-sm font-semibold">YouTube</h2>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              Videos, available captions, thumbnails and audience insights.
            </p>
          </div>
        </div>
        <div className="p-4">
          <YouTubeConnections
            redirectPath={redirectPath}
            beforeConnect={beforeConnect}
          />
        </div>
      </section>
      <div className="grid gap-3 sm:grid-cols-2">
        {[
          {
            name: "Instagram",
            detail: "Reels and visual posts",
            icon: InstagramIcon,
          },
          { name: "X", detail: "Posts and conversations", icon: null },
          {
            name: "Facebook",
            detail: "Videos and page posts",
            icon: Facebook01Icon,
          },
          {
            name: "LinkedIn",
            detail: "Writing and professional updates",
            icon: Linkedin01Icon,
          },
        ].map((platform) => (
          <div
            key={platform.name}
            className="flex items-center gap-3 rounded-xl border px-4 py-3"
          >
            <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground">
              {platform.icon ? (
                <Icon icon={platform.icon} />
              ) : (
                <span className="text-base font-semibold">𝕏</span>
              )}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{platform.name}</p>
              <p className="text-xs text-muted-foreground">{platform.detail}</p>
            </div>
            <span className="text-[10px] text-muted-foreground">
              Coming soon
            </span>
          </div>
        ))}
      </div>
      <p className="text-xs leading-5 text-muted-foreground">
        Your published work helps drafts follow your voice and gives thumbnails
        visual references. Explore the material in your{" "}
        <Link href="/library" className="text-signal hover:underline">
          creator library ↗
        </Link>
        .
      </p>
    </div>
  );
}

"use client";

import Link from "next/link";
import { ArrowRight01Icon } from "@hugeicons/core-free-icons";

import { PlatformLogo } from "@/components/calendar/platform";
import { Icon } from "@/components/common/icon";
import { TextPlatformConnections } from "@/components/accounts/text-platform-connections";
import { YouTubeConnections } from "@/components/projects/studio/youtube-connections";
import { Separator } from "@/components/ui/separator";

/** One connection surface shared by onboarding and Settings; OAuth remains provider-specific. */
export function AccountConnections({
  redirectPath,
  beforeConnect,
}: {
  redirectPath: string;
  beforeConnect?: () => Promise<void>;
}) {
  return (
    <div className="space-y-6">
      <section className="space-y-3">
        <div className="flex items-start gap-3">
          <PlatformLogo platform="youtube" size={18} className="mt-0.5" />
          <div>
            <h2 className="text-sm font-semibold">YouTube</h2>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              Videos, captions, thumbnails and channel analytics.
            </p>
          </div>
        </div>
        <YouTubeConnections
          redirectPath={redirectPath}
          beforeConnect={beforeConnect}
        />
      </section>
      <Separator />
      <section className="space-y-3">
        <div>
          <h2 className="text-sm font-semibold">Writing platforms</h2>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            Cross-post drafts and essays to Medium, Substack, and Reddit.
          </p>
        </div>
        <TextPlatformConnections redirectPath={redirectPath} />
      </section>
      <Separator />
      <p className="text-xs leading-5 text-muted-foreground">
        Your published work helps drafts follow your voice and gives thumbnails
        visual references. Explore the material in your{" "}
        <Link
          href="/library"
          className="inline-flex items-center gap-1 text-signal hover:underline"
        >
          Creator library
          <Icon icon={ArrowRight01Icon} className="size-3" />
        </Link>
        .
      </p>
    </div>
  );
}

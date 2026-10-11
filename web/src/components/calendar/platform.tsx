"use client";

import Image from "next/image";

import { cn } from "@/lib/utils";

/*
 * Posting platforms, with the same SVG logos the landing page uses. Values match
 * the onboarding vocabulary (`youtube`, `instagram`, …) so stored slots resolve.
 */
export const PLATFORM_OPTIONS: { value: string; label: string }[] = [
  { value: "youtube", label: "YouTube" },
  { value: "instagram", label: "Instagram" },
  { value: "tiktok", label: "TikTok" },
  { value: "x", label: "X" },
  { value: "facebook", label: "Facebook" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "medium", label: "Medium" },
  { value: "substack", label: "Substack" },
  { value: "reddit", label: "Reddit" },
];

const LOGO_BY_PLATFORM: Record<string, string> = {
  youtube: "/youtube.svg",
  youtube_shorts: "/youtube.svg",
  instagram: "/instagram.svg",
  tiktok: "/tiktok-mono.svg",
  x: "/x.svg",
  facebook: "/facebook.svg",
  linkedin: "/linkedin.svg",
  medium: "/medium.svg",
  substack: "/substack.svg",
  reddit: "/reddit.svg",
};

/*
 * Labels for values that live outside PLATFORM_OPTIONS (the onboarding
 * vocabulary has `youtube_shorts`; stored slots may hold any casing).
 * Keys are lower-cased values.
 */
const LABEL_ALIASES: Record<string, string> = {
  youtube_shorts: "YouTube Shorts",
  youtube_shorts_video: "YouTube Shorts",
  twitter: "X",
};

export function platformLabel(value: string): string {
  const key = value.trim().toLowerCase();
  return (
    PLATFORM_OPTIONS.find((option) => option.value === key)?.label ??
    PLATFORM_OPTIONS.find(
      (option) => option.value.toLowerCase() === key,
    )?.label ??
    LABEL_ALIASES[key] ??
    PLATFORM_OPTIONS.find((option) => option.value === value)?.label ??
    value
  );
}

export function platformLogoSrc(value: string): string {
  const key = value.toLowerCase();
  if (key.includes("youtube") || key.includes("youtu"))
    return LOGO_BY_PLATFORM.youtube;
  return LOGO_BY_PLATFORM[key] ?? "/globe.svg";
}

export function PlatformLogo({
  platform,
  size = 16,
  className,
}: {
  platform: string;
  size?: number;
  className?: string;
}) {
  return (
    <Image
      src={platformLogoSrc(platform)}
      alt=""
      aria-hidden
      width={size}
      height={size}
      className={cn("shrink-0 object-contain", className)}
    />
  );
}

/*
 * Logo + label together, so a platform is never shown as bare text.
 * Use this wherever a platform name appears outside the platform dropdown.
 */
export function PlatformBadge({
  platform,
  size = 14,
  className,
}: {
  platform: string;
  size?: number;
  className?: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <PlatformLogo platform={platform} size={size} />
      {platformLabel(platform)}
    </span>
  );
}

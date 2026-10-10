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
];

const LOGO_BY_PLATFORM: Record<string, string> = {
  youtube: "/youtube.svg",
  instagram: "/instagram.svg",
  tiktok: "/tiktok-mono.svg",
  x: "/x.svg",
  facebook: "/facebook.svg",
  linkedin: "/linkedin.svg",
};

export function platformLabel(value: string): string {
  return (
    PLATFORM_OPTIONS.find((option) => option.value === value)?.label ?? value
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

"use client";

import dynamic from "next/dynamic";

// The SVG asset library is large. Load it when an authenticated avatar renders,
// keeping it out of the initial app shell and signed-out route payloads.
export const UserAvatar = dynamic(
  () =>
    import("@/components/avatar/avatar-artwork").then(
      (module) => module.AvatarArtwork,
    ),
  {
    ssr: false,
    loading: () => <span className="block size-full rounded-full bg-muted" />,
  },
);

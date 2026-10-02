import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  async rewrites() {
    return [
      // Path-based project module URLs are served by the static project shell;
      // the client reads the id/module from the path. Mirrored in `firebase.json`
      // because a static export has no runtime rewrites in production.
      {
        source: "/projects/view/project/:path*",
        destination: "/projects/view",
      },
    ];
  },
};

export default nextConfig;

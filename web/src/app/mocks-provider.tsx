"use client";

import { useEffect, type ReactNode } from "react";

export function MocksProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    if (process.env.NEXT_PUBLIC_MOCK_MODE !== "on") return;
    let cancelled = false;
    import("@/mocks/browser").then(({ worker }) => {
      if (!cancelled) {
        worker.start({ onUnhandledRequest: "bypass" });
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return <>{children}</>;
}

"use client";

import { useCallback, useState } from "react";

import {
  type StudioModuleId,
  isStudioModuleId,
  studioModuleHref,
} from "@/lib/studio";
import { useFeatureFlag } from "@/lib/feature-flags";

function normalize(moduleId: string): StudioModuleId {
  return isStudioModuleId(moduleId) ? moduleId : "overview";
}

/**
 * Owns the active studio module for a project.
 *
 * Module tabs are not real routes: this is a static export, so `/projects/view/**`
 * is served by a rewrite and a normal navigation would reload the whole document
 * (remounting the workspace and refetching every query). Instead the module lives
 * in React state and is mirrored into the URL with `window.history.pushState`,
 * which the App Router folds into `usePathname` — the documented shallow-routing
 * pattern for SPAs. A back/forward changes the pathname prop, which we adopt.
 */
export function useStudioModule(projectId: string, moduleId: string) {
  const [activeModule, setActiveModule] = useState<StudioModuleId>(() =>
    normalize(moduleId),
  );
  const [lastModuleId, setLastModuleId] = useState(moduleId);
  // With header tabs the tab strip stays put, so switching a module must not move the page:
  // only the right pane changes. Without the flag, keep the old scroll-to-top behaviour.
  const headerTabs = useFeatureFlag("headerTabs");

  // Adopt a new URL prop (back/forward or a real navigation). Adjusting state
  // during render is React's documented "previous value" pattern and avoids a
  // cascading effect.
  if (moduleId !== lastModuleId) {
    setLastModuleId(moduleId);
    setActiveModule(normalize(moduleId));
  }

  const navigate = useCallback(
    (next: StudioModuleId) => {
      if (next === activeModule) return;
      window.history.pushState(null, "", studioModuleHref(projectId, next));
      setActiveModule(next);
      // A fresh navigation used to reset scroll; keep that on tab switches, but not when the
      // tabs live in the header (the page should stay exactly where it is).
      if (!headerTabs) {
        window.scrollTo({ top: 0, behavior: "auto" });
      }
    },
    [activeModule, headerTabs, projectId],
  );

  return { activeModule, navigate };
}

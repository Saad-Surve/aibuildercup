"use client";

import { useCallback, useRef } from "react";

/** A view can reconcile once. Timer refetches only read saved state after that. */
export function useViewReconciliation(key: string): () => boolean {
  const visited = useRef(new Set<string>());
  return useCallback(() => {
    if (visited.current.has(key)) return false;
    visited.current.add(key);
    return true;
  }, [key]);
}

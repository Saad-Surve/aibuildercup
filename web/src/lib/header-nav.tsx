"use client";

import { createContext, useContext, type ReactNode } from "react";

/**
 * Slot for navigation that a page wants rendered in the app's top sticky header.
 *
 * The app shell owns the header; a page (the project studio) fills this slot with its module
 * tabs when the `headerTabs` feature flag is on. Keeping it as a slot means the shell never has
 * to know about studio-specific modules.
 */

type HeaderNavSetter = (node: ReactNode) => void;

const HeaderNavContext = createContext<HeaderNavSetter | null>(null);

export function HeaderNavProvider({
  setNav,
  children,
}: {
  setNav: HeaderNavSetter;
  children: ReactNode;
}) {
  return (
    <HeaderNavContext.Provider value={setNav}>
      {children}
    </HeaderNavContext.Provider>
  );
}

export function useSetHeaderNav(): HeaderNavSetter {
  const setter = useContext(HeaderNavContext);
  if (!setter) {
    throw new Error("useSetHeaderNav must be used within HeaderNavProvider");
  }
  return setter;
}

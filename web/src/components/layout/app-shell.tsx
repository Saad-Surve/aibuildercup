"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  Analytics01Icon,
  DashboardSquare01Icon,
  FolderOpenIcon,
  Plug01Icon,
  Settings01Icon,
  SidebarLeft01Icon,
  SidebarRight01Icon,
  UserIcon,
} from "@hugeicons/core-free-icons";
import type { IconSvgElement } from "@hugeicons/react";

import { Icon } from "@/components/common/icon";
import { Logo, LogoMark } from "@/components/common/logo";
import { UserMenu } from "@/components/layout/user-menu";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: IconSvgElement;
  ready: boolean;
}

const NAV: NavItem[] = [
  {
    href: "/dashboard",
    label: "Dashboard",
    icon: DashboardSquare01Icon,
    ready: true,
  },
  { href: "/projects", label: "Projects", icon: FolderOpenIcon, ready: true },
  {
    href: "/audience",
    label: "Audience insights",
    icon: Analytics01Icon,
    ready: false,
  },
  {
    href: "/connections",
    label: "Connections",
    icon: Plug01Icon,
    ready: false,
  },
  { href: "/profile", label: "Profile", icon: UserIcon, ready: true },
  { href: "/settings", label: "Settings", icon: Settings01Icon, ready: false },
];

const COLLAPSE_KEY = "hc-sidebar-collapsed";

/*
 * The collapsed rail is persisted in localStorage. AppShell only mounts on the
 * client (it sits behind the auth gate), so the stored value can seed useState
 * directly — no effect, no hydration mismatch, and no expanded-then-collapse
 * flash on a hard refresh.
 */
function readStoredCollapsed(): boolean {
  try {
    return window.localStorage.getItem(COLLAPSE_KEY) === "1";
  } catch {
    return false;
  }
}

function useSidebarCollapsed(): [boolean, (next: boolean) => void] {
  const [collapsed, setCollapsedState] = useState(readStoredCollapsed);

  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key === COLLAPSE_KEY) setCollapsedState(event.newValue === "1");
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  function setCollapsed(next: boolean): void {
    try {
      window.localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
    } catch {
      // Private mode: collapse still works for this session.
    }
    setCollapsedState(next);
  }

  return [collapsed, setCollapsed];
}

/*
 * Sidebar motion: the rail width tweens with motion while labels fade in
 * clipped, nowrap form. Rows never change justification or padding, so with
 * the rail anchored left the 16px icons sit pixel-static (a lone icon in a
 * px-3 row is already centered in the 64px rail) — nothing teleports.
 */
const RAIL_TWEEN = { duration: 0.22, ease: "easeInOut" } as const;

/*
 * How far the full lockup glides left on collapse so its mark lands exactly
 * where the lone collapsed mark sits: the mark is ~43px wide (h-8 at 194:145),
 * centred in the 64px rail its left edge is at 10.5, versus 24 in the px-6 row.
 */
const LOGO_GLIDE_X = -13.5;

function NavLabel({
  collapsed,
  children,
}: {
  collapsed: boolean;
  children: React.ReactNode;
}) {
  return (
    <AnimatePresence initial={false}>
      {!collapsed && (
        <motion.span
          key="nav-label"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.12 }}
          className="whitespace-nowrap overflow-hidden"
        >
          {children}
        </motion.span>
      )}
    </AnimatePresence>
  );
}

function NavLink({
  item,
  active,
  collapsed,
}: {
  item: NavItem;
  active: boolean;
  collapsed: boolean;
}) {
  if (!item.ready) {
    return (
      <div
        title={collapsed ? item.label : undefined}
        className="flex h-9 items-center gap-3 overflow-hidden rounded-lg px-3 py-2 text-sm text-muted-foreground/50"
      >
        <Icon icon={item.icon} />
        <NavLabel collapsed={collapsed}>{item.label}</NavLabel>
      </div>
    );
  }

  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      aria-label={collapsed ? item.label : undefined}
      title={collapsed ? item.label : undefined}
      className={cn(
        "flex h-9 items-center gap-3 overflow-hidden rounded-lg px-3 py-2 text-sm transition-colors",
        active
          ? "bg-signal/10 font-medium text-foreground"
          : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
      )}
    >
      <Icon icon={item.icon} className={cn(active && "text-signal")} />
      <NavLabel collapsed={collapsed}>{item.label}</NavLabel>
    </Link>
  );
}

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const readyItems = NAV.filter((item) => item.ready);
  const [collapsed, setCollapsed] = useSidebarCollapsed();

  function toggleCollapsed() {
    setCollapsed(!collapsed);
  }

  return (
    <div className="flex min-h-[100dvh]">
      <motion.aside
        initial={false}
        animate={{ width: collapsed ? 64 : 240 }}
        transition={{ type: "tween", ...RAIL_TWEEN }}
        className="app-sidebar-rail sticky top-0 hidden h-[100dvh] shrink-0 flex-col overflow-hidden border-r border-transparent shadow-[inset_-1px_0_0_0_var(--color-border)] md:flex"
      >
        <div className="relative flex h-14 shrink-0 items-center px-6">
          <motion.div
            initial={false}
            animate={{
              opacity: collapsed ? 0 : 1,
              x: collapsed ? LOGO_GLIDE_X : 0,
            }}
            transition={RAIL_TWEEN}
            aria-hidden={collapsed}
            inert={collapsed}
            className={cn(
              "flex items-center",
              collapsed && "pointer-events-none",
            )}
          >
            <Logo href="/dashboard" showSubtitle={false} />
          </motion.div>
          <motion.div
            initial={false}
            animate={{ opacity: collapsed ? 1 : 0 }}
            transition={RAIL_TWEEN}
            aria-hidden={!collapsed}
            inert={!collapsed}
            className={cn(
              "absolute inset-y-0 left-0 flex w-16 items-center justify-center",
              !collapsed && "pointer-events-none",
            )}
          >
            <Link
              href="/dashboard"
              aria-label="Go to dashboard"
              tabIndex={collapsed ? 0 : -1}
              className="inline-flex items-center rounded-lg transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
            >
              <LogoMark />
            </Link>
          </motion.div>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-x-hidden overflow-y-auto px-3 py-2">
          {NAV.map((item) => (
            <NavLink
              key={item.href}
              item={item}
              active={isActive(pathname, item.href)}
              collapsed={collapsed}
            />
          ))}
        </nav>
        <div className="p-3">
          <button
            type="button"
            onClick={toggleCollapsed}
            aria-expanded={!collapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="flex h-9 w-full items-center gap-3 overflow-hidden rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
          >
            <Icon icon={collapsed ? SidebarRight01Icon : SidebarLeft01Icon} />
            <NavLabel collapsed={collapsed}>Collapse</NavLabel>
          </button>
        </div>
      </motion.aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b border-transparent bg-background/80 px-4 shadow-[inset_0_-1px_0_0_var(--color-border)] backdrop-blur md:px-6">
          <div className="md:hidden">
            <Logo compact href="/dashboard" />
          </div>
          <div className="hidden md:block" />
          <UserMenu />
        </header>

        <nav className="flex gap-1 overflow-x-auto border-b border-transparent px-3 py-2 shadow-[inset_0_-1px_0_0_var(--color-border)] md:hidden">
          {readyItems.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex shrink-0 items-center gap-2 rounded-lg px-3 py-1.5 text-sm",
                  active
                    ? "bg-signal/10 font-medium text-foreground"
                    : "text-muted-foreground",
                )}
              >
                <Icon
                  icon={item.icon}
                  className={cn(active && "text-signal")}
                />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <main className="flex-1 px-4 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </div>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Analytics01Icon,
  DashboardSquare01Icon,
  FolderOpenIcon,
  Plug01Icon,
  Settings01Icon,
  UserIcon,
} from "@hugeicons/core-free-icons";
import type { IconSvgElement } from "@hugeicons/react";

import { Icon } from "@/components/common/icon";
import { Logo } from "@/components/common/logo";
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

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  if (!item.ready) {
    return (
      <div className="flex cursor-default items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground/50">
        <Icon icon={item.icon} />
        <span>{item.label}</span>
      </div>
    );
  }

  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
        active
          ? "bg-signal/10 font-medium text-foreground"
          : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
      )}
    >
      <Icon icon={item.icon} className={cn(active && "text-signal")} />
      {item.label}
    </Link>
  );
}

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const readyItems = NAV.filter((item) => item.ready);

  return (
    <div className="flex min-h-[100dvh]">
      <aside className="sticky top-0 hidden h-[100dvh] w-60 shrink-0 flex-col border-r md:flex">
        <div className="flex h-14 shrink-0 items-center px-5">
          <Logo href="/dashboard" />
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2">
          {NAV.map((item) => (
            <NavLink
              key={item.href}
              item={item}
              active={isActive(pathname, item.href)}
            />
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b bg-background/80 px-4 backdrop-blur md:px-6">
          <div className="md:hidden">
            <Logo compact href="/dashboard" />
          </div>
          <div className="hidden md:block" />
          <UserMenu />
        </header>

        <nav className="flex gap-1 overflow-x-auto border-b px-3 py-2 md:hidden">
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

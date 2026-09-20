"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  FolderOpen,
  LayoutDashboard,
  Plug,
  Settings,
  UserRound,
  type LucideIcon,
} from "lucide-react";

import { Logo } from "@/components/common/logo";
import { UserMenu } from "@/components/layout/user-menu";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  ready: boolean;
}

const NAV: NavItem[] = [
  {
    href: "/dashboard",
    label: "Dashboard",
    icon: LayoutDashboard,
    ready: true,
  },
  { href: "/projects", label: "Projects", icon: FolderOpen, ready: false },
  {
    href: "/audience",
    label: "Audience insights",
    icon: BarChart3,
    ready: false,
  },
  { href: "/connections", label: "Connections", icon: Plug, ready: false },
  { href: "/profile", label: "Profile", icon: UserRound, ready: true },
  { href: "/settings", label: "Settings", icon: Settings, ready: false },
];

function NavLink({ item, active }: { item: NavItem; active: boolean }) {
  const Icon = item.icon;

  if (!item.ready) {
    return (
      <div className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground/60">
        <Icon className="size-4 shrink-0" />
        <span>{item.label}</span>
        <Badge variant="ghost" className="ml-auto text-[0.65rem]">
          Soon
        </Badge>
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
          ? "bg-muted font-medium text-foreground"
          : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
      )}
    >
      <Icon className="size-4 shrink-0" />
      {item.label}
    </Link>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const readyItems = NAV.filter((item) => item.ready);

  return (
    <div className="flex min-h-[100dvh]">
      <aside className="hidden w-60 shrink-0 border-r md:flex md:flex-col">
        <div className="flex h-14 items-center px-5">
          <Logo />
        </div>
        <nav className="flex-1 space-y-0.5 px-3 py-2">
          {NAV.map((item) => (
            <NavLink
              key={item.href}
              item={item}
              active={pathname === item.href}
            />
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between gap-3 border-b bg-background/80 px-4 backdrop-blur md:px-6">
          <div className="md:hidden">
            <Logo compact />
          </div>
          <div className="hidden md:block" />
          <UserMenu />
        </header>

        <nav className="flex gap-1 overflow-x-auto border-b px-3 py-2 md:hidden">
          {readyItems.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex shrink-0 items-center gap-2 rounded-lg px-3 py-1.5 text-sm",
                  active
                    ? "bg-muted font-medium text-foreground"
                    : "text-muted-foreground",
                )}
              >
                <Icon className="size-4" />
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

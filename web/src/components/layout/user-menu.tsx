"use client";

import {
  ComputerIcon,
  LogoutSquare02Icon,
  Moon02Icon,
  Sun03Icon,
  UserIcon,
} from "@hugeicons/core-free-icons";
import Link from "next/link";
import { useTheme } from "next-themes";

import { useAuth } from "@/components/auth/auth-provider";
import { Icon } from "@/components/common/icon";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function UserMenu() {
  const { user, profile, signOut } = useAuth();
  const { theme, setTheme } = useTheme();
  const name = profile?.displayName ?? user?.displayName ?? "Creator";
  const email = profile?.email ?? user?.email ?? "";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            className="h-9 w-9 rounded-full"
          />
        }
      >
        <span className="rounded-full bg-gradient-to-br from-cyan-400 via-fuchsia-500 to-orange-400 p-[2px]">
          <span className="block rounded-full bg-background p-[2px]">
            <span
              title={name}
              className="flex size-[30px] items-center justify-center rounded-full bg-signal/15 text-xs font-semibold text-signal"
            >
              {name.trim().slice(0, 1).toUpperCase()}
            </span>
          </span>
        </span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuGroup>
          <DropdownMenuLabel>
            <span className="block truncate font-medium text-foreground">
              {name}
            </span>
            <span className="block truncate text-xs text-muted-foreground">
              {email}
            </span>
          </DropdownMenuLabel>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem render={<Link href="/profile" />}>
            <Icon icon={UserIcon} />
            Profile
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuLabel>Theme</DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={theme ?? "system"}
            onValueChange={setTheme}
          >
            <DropdownMenuRadioItem value="light">
              <Icon icon={Sun03Icon} />
              Light
            </DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="dark">
              <Icon icon={Moon02Icon} />
              Dark
            </DropdownMenuRadioItem>
            <DropdownMenuRadioItem value="system">
              <Icon icon={ComputerIcon} />
              System
            </DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onClick={signOut}>
          <Icon icon={LogoutSquare02Icon} />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

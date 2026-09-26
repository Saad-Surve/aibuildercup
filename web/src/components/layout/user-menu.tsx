"use client";

import {
  ComputerIcon,
  LogoutSquare02Icon,
  Moon02Icon,
  Sun03Icon,
} from "@hugeicons/core-free-icons";
import { useTheme } from "next-themes";

import { useAuth } from "@/components/auth/auth-provider";
import { UserAvatar } from "@/components/avatar/user-avatar";
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
import { useUserAvatar } from "@/lib/avatar";

export function UserMenu() {
  const { user, profile, signOut } = useAuth();
  const avatar = useUserAvatar();
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
            className="h-11 w-11 rounded-full"
          />
        }
      >
        <span className="rounded-full bg-gradient-to-br from-cyan-400 via-fuchsia-500 to-orange-400 p-[2px]">
          <span className="block rounded-full bg-background p-[2px]">
            <UserAvatar state={avatar} size={38} title={name} />
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

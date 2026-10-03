"use client";

import { HugeiconsIcon } from "@hugeicons/react";
import {
  Alert02Icon,
  Cancel01Icon,
  CircleCheckIcon,
  InformationCircleIcon,
  Loading03Icon,
} from "@hugeicons/core-free-icons";
import { useTheme } from "next-themes";
import { Toaster as Sonner, type ToasterProps } from "sonner";

const Toaster = ({ ...props }: ToasterProps) => {
  const { theme = "system" } = useTheme();

  return (
    <Sonner
      theme={theme as ToasterProps["theme"]}
      className="toaster group"
      offset={16}
      gap={10}
      icons={{
        success: <HugeiconsIcon icon={CircleCheckIcon} className="size-4" />,
        info: <HugeiconsIcon icon={InformationCircleIcon} className="size-4" />,
        warning: <HugeiconsIcon icon={Alert02Icon} className="size-4" />,
        error: <HugeiconsIcon icon={Cancel01Icon} className="size-4" />,
        loading: (
          <HugeiconsIcon icon={Loading03Icon} className="size-4 animate-spin" />
        ),
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--border-radius": "calc(var(--radius) + 2px)",
          "--width": "22rem",
        } as React.CSSProperties
      }
      toastOptions={{
        classNames: {
          toast:
            "cn-toast items-start gap-2.5 rounded-xl border border-border/70 bg-popover/95 text-popover-foreground shadow-lg shadow-black/5 backdrop-blur-md",
          title: "text-sm font-medium leading-snug",
          description: "text-xs text-muted-foreground",
          actionButton:
            "rounded-md bg-primary text-primary-foreground text-xs font-medium",
          cancelButton: "rounded-md bg-muted text-muted-foreground text-xs",
          closeButton: "rounded-md border-border bg-popover",
        },
      }}
      {...props}
    />
  );
};

export { Toaster };

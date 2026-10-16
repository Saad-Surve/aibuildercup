"use client";

import type { ReactNode } from "react";
import { DashboardSquare01Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { prefetchStudioModule } from "@/components/projects/studio/module-registry";
import { Button } from "@/components/ui/button";
import {
  STUDIO_MODULES,
  type StudioModuleId,
  studioModuleHref,
} from "@/lib/studio";
import { cn } from "@/lib/utils";

/**
 * A quiet tab strip so the video and the current module stay one click apart.
 *
 * Tabs are real `<a href>`s (middle-click / copy-link / open-in-new-tab still
 * work) but a plain left click is intercepted and routed through
 * {@link onSelect}, which swaps the module in place via `history.pushState`
 * instead of reloading the rewritten route.
 */
export function ModuleNav({
  projectId,
  active,
  onSelect,
  variant = "page",
  showOverview = true,
}: {
  projectId: string;
  active: StudioModuleId;
  onSelect: (moduleId: StudioModuleId) => void;
  //: `page` is the in-page tab strip with its divider; `header` is the bare strip
  //: rendered inside the app's sticky header.
  variant?: "page" | "header";
  //: The header strip omits Overview (it duplicates the module grid).
  showOverview?: boolean;
}) {
  return (
    <nav
      aria-label="Project modules"
      className={cn(
        "flex items-center gap-1",
        variant === "page"
          ? "flex-wrap border-b pb-3"
          : "flex-nowrap whitespace-nowrap",
      )}
    >
      {showOverview ? (
        <ModuleTab
          projectId={projectId}
          moduleId="overview"
          active={active === "overview"}
          onSelect={onSelect}
          variant={variant}
          icon={<Icon icon={DashboardSquare01Icon} />}
          label="Overview"
        />
      ) : null}
      {STUDIO_MODULES.map((module) => (
        <ModuleTab
          key={module.id}
          projectId={projectId}
          moduleId={module.id}
          active={active === module.id}
          onSelect={onSelect}
          variant={variant}
          icon={<Icon icon={module.icon} />}
          label={module.label}
        />
      ))}
    </nav>
  );
}

function ModuleTab({
  projectId,
  moduleId,
  active,
  onSelect,
  variant,
  icon,
  label,
}: {
  projectId: string;
  moduleId: StudioModuleId;
  active: boolean;
  onSelect: (moduleId: StudioModuleId) => void;
  variant: "page" | "header";
  icon: ReactNode;
  label: string;
}) {
  const inHeader = variant === "header";
  return (
    <Button
      size="sm"
      // In-page keeps a filled pill for the active tab; the header marks it with a
      // signal-coloured icon and border instead.
      variant={active && !inHeader ? "secondary" : "ghost"}
      nativeButton={false}
      className={cn(
        inHeader && "max-md:h-9 max-md:px-3",
        inHeader &&
          (active
            ? "border-signal/60 text-foreground"
            : "border-transparent text-muted-foreground"),
      )}
      render={
        <a
          href={studioModuleHref(projectId, moduleId)}
          aria-label={label}
          aria-current={active ? "page" : undefined}
          onMouseEnter={() => prefetchStudioModule(moduleId)}
          onFocus={() => prefetchStudioModule(moduleId)}
          onClick={(event) => {
            if (event.defaultPrevented) return;
            // Modified clicks (new tab, etc.) keep the native behaviour.
            if (
              event.button !== 0 ||
              event.metaKey ||
              event.ctrlKey ||
              event.shiftKey ||
              event.altKey
            ) {
              return;
            }
            event.preventDefault();
            onSelect(moduleId);
          }}
        />
      }
    >
      <span
        className={cn("flex items-center", inHeader && active && "text-signal")}
      >
        {icon}
      </span>
      {label}
    </Button>
  );
}

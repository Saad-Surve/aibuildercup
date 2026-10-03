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
}: {
  projectId: string;
  active: StudioModuleId;
  onSelect: (moduleId: StudioModuleId) => void;
}) {
  return (
    <nav
      aria-label="Project modules"
      className="flex flex-wrap items-center gap-1 border-b pb-3"
    >
      <ModuleTab
        projectId={projectId}
        moduleId="overview"
        active={active === "overview"}
        onSelect={onSelect}
        icon={<Icon icon={DashboardSquare01Icon} />}
        label="Overview"
      />
      {STUDIO_MODULES.map((module) => (
        <ModuleTab
          key={module.id}
          projectId={projectId}
          moduleId={module.id}
          active={active === module.id}
          onSelect={onSelect}
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
  icon,
  label,
}: {
  projectId: string;
  moduleId: StudioModuleId;
  active: boolean;
  onSelect: (moduleId: StudioModuleId) => void;
  icon: ReactNode;
  label: string;
}) {
  return (
    <Button
      size="sm"
      variant={active ? "secondary" : "ghost"}
      nativeButton={false}
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
      {icon}
      {label}
    </Button>
  );
}

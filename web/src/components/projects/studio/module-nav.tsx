"use client";

import Link from "next/link";
import { DashboardSquare01Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { Button } from "@/components/ui/button";
import { STUDIO_MODULES, type StudioModuleId } from "@/lib/studio";

export function moduleHref(projectId: string, moduleId: StudioModuleId) {
  if (moduleId === "overview") {
    return `/projects/view?projectId=${projectId}`;
  }
  return `/projects/view?projectId=${projectId}&module=${moduleId}`;
}

/**
 * A quiet tab strip so the video and the current module stay one click apart.
 */
export function ModuleNav({
  projectId,
  active,
}: {
  projectId: string;
  active: StudioModuleId;
}) {
  return (
    <nav
      aria-label="Project modules"
      className="flex flex-wrap items-center gap-1 border-b pb-3"
    >
      <Button
        size="sm"
        variant={active === "overview" ? "secondary" : "ghost"}
        render={<Link href={moduleHref(projectId, "overview")} />}
      >
        <Icon icon={DashboardSquare01Icon} />
        Overview
      </Button>
      {STUDIO_MODULES.map((module) => (
        <Button
          key={module.id}
          size="sm"
          variant={active === module.id ? "secondary" : "ghost"}
          render={<Link href={moduleHref(projectId, module.id)} />}
        >
          <Icon icon={module.icon} />
          {module.label}
        </Button>
      ))}
    </nav>
  );
}

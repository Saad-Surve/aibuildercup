"use client";

import { CaptionBurnPanel } from "@/components/projects/caption-burn-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

/**
 * Burn a dub's localized captions onto its dubbed video.
 *
 * Thin wrapper around {@link CaptionBurnPanel} scoped to one localization: the panel already
 * owns the preset picker, customizer, live preview, render list, progress and download. Passing
 * `localizationId` makes it read the dub's video + localized SRT and filter to this dub's renders.
 */
export function DubCaptionsDialog({
  projectId,
  projectName,
  localizationId,
  language,
  open,
  onOpenChange,
}: {
  projectId: string;
  projectName?: string;
  localizationId: string;
  /** Target-language code, used only to describe which dub this is. */
  language?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Caption this dub</DialogTitle>
          <DialogDescription>
            Create a video with localized captions{" "}
            {language ? ` (${language.toUpperCase()})` : ""} from this dub.
          </DialogDescription>
        </DialogHeader>
        <CaptionBurnPanel
          projectId={projectId}
          projectName={projectName}
          localizationId={localizationId}
          enabled={open}
          onClose={() => onOpenChange(false)}
        />
      </DialogContent>
    </Dialog>
  );
}

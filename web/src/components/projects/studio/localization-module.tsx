"use client";

import { DubbingPanel } from "@/components/projects/dubbing-panel";
import { GlossaryEditor } from "@/components/projects/studio/glossary-editor";

export function LocalizationModule({
  projectId,
  targetLanguages,
}: {
  projectId: string;
  targetLanguages: string[];
}) {
  return (
    <div className="space-y-8">
      <GlossaryEditor projectId={projectId} />
      <DubbingPanel projectId={projectId} targetLanguages={targetLanguages} />
    </div>
  );
}

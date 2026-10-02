"use client";

import { ClosedCaptionIcon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { CaptionBurnPanel } from "@/components/projects/caption-burn-dialog";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export function CaptionsModule({
  projectId,
  projectName,
}: {
  projectId: string;
  projectName: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon icon={ClosedCaptionIcon} className="text-muted-foreground" />
          Burn captions
        </CardTitle>
        <CardDescription>
          Render a new MP4 with styled captions from this transcript. The
          original file is never changed.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <CaptionBurnPanel projectId={projectId} projectName={projectName} />
      </CardContent>
    </Card>
  );
}

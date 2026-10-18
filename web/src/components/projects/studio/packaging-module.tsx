"use client";

import {
  ImageAdd01Icon,
  SearchList01Icon,
  // VideoReplayIcon, // restore with the Visual inserts card below
} from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { WORKSPACE_SNAP_TARGET } from "@/lib/workspace";
import { ListingPanel } from "@/components/projects/studio/listing-panel";
// import { VisualInsertsPanel } from "@/components/projects/studio/visual-inserts-panel";
import { ThumbnailPanel } from "@/components/projects/studio/thumbnail-panel";

export function PackagingModule({
  projectId,
  projectName,
  thumbnailConcept,
}: {
  projectId: string;
  projectName: string;
  thumbnailConcept: string;
}) {
  return (
    <div className="space-y-8">
      <Card className={WORKSPACE_SNAP_TARGET}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Icon icon={ImageAdd01Icon} className="text-muted-foreground" />
            Thumbnail concepts
          </CardTitle>
          <CardDescription>
            Concepts cite the moment they came from, keep your face, and are
            scored on legibility, honesty, and fit. Edit in plain language, then
            apply the winner.
          </CardDescription>
          {thumbnailConcept ? (
            <p className="text-xs text-muted-foreground">
              Current promise:{" "}
              <span className="text-foreground">{thumbnailConcept}</span>
            </p>
          ) : null}
        </CardHeader>
        <CardContent>
          <ThumbnailPanel projectId={projectId} projectName={projectName} />
        </CardContent>
      </Card>

      {/* Visual inserts card hidden for now.
      <Card className={WORKSPACE_SNAP_TARGET}>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2">
              <Icon icon={VideoReplayIcon} className="text-muted-foreground" />
              Visual inserts
            </CardTitle>
          </div>
          <CardDescription>
            Add context where it helps: a grounded chart, a clear explanation,
            or illustrative footage suggested from this video.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <VisualInsertsPanel projectId={projectId} />
        </CardContent>
      </Card>
      */}

      <Card className={WORKSPACE_SNAP_TARGET}>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2">
              <Icon icon={SearchList01Icon} className="text-muted-foreground" />
              Title, description & tags
            </CardTitle>
          </div>
          <CardDescription>
            An honest listing in your voice, grounded in the transcript and your
            creator library. Edit and save it to fill the YouTube upload fields.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ListingPanel projectId={projectId} projectName={projectName} />
        </CardContent>
      </Card>
    </div>
  );
}

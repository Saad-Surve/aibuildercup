"use client";

import {
  ImageAdd01Icon,
  PlayIcon,
  SearchList01Icon,
  VideoReplayIcon,
} from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { WORKSPACE_SNAP_TARGET } from "@/lib/workspace";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ThumbnailPanel } from "@/components/projects/studio/thumbnail-panel";

function Sample() {
  return (
    <Badge
      variant="outline"
      className="border-border bg-muted text-muted-foreground"
    >
      Coming soon
    </Badge>
  );
}

/** A believable infographic clip mock: a chart with a callout. */
function ClipSample({
  label,
  time,
  bars,
  callout,
}: {
  label: string;
  time: string;
  bars: number[];
  callout: string;
}) {
  return (
    <div className="space-y-2">
      <div className="relative flex aspect-video items-end gap-2 overflow-hidden rounded-lg bg-slate-900 p-4 shadow-sm ring-1 ring-foreground/10">
        <span className="absolute top-2 left-3 text-[10px] font-medium tracking-wide text-white/60 uppercase">
          {label}
        </span>
        <div className="flex h-full w-full items-end gap-2 pt-6">
          {bars.map((height, index) => (
            <div
              key={index}
              className="flex-1 rounded-t bg-signal/80"
              style={{ height: `${height}%` }}
            />
          ))}
        </div>
        <span className="absolute right-3 bottom-2 rounded bg-black/50 px-1.5 py-0.5 text-[10px] text-white/80 tabular">
          {callout}
        </span>
      </div>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <span className="flex size-5 items-center justify-center rounded-full bg-muted">
          <Icon icon={PlayIcon} className="size-3" />
        </span>
        <span className="tabular">{time}</span>
      </div>
    </div>
  );
}

/**
 * Packaging: live thumbnail concepts (grounded in the transcript and review findings),
 * then the infographic-clip and listing sections, which are still mocks.
 */
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
            Options grounded in what the video actually says: each one cites the
            moment it came from, keeps your real face, and is scored on
            legibility, honesty, and platform fit. Edit any concept in plain
            language, then apply the winner.
          </CardDescription>
          {thumbnailConcept ? (
            <p className="text-xs text-muted-foreground">
              Current packaging promise:{" "}
              <span className="text-foreground">{thumbnailConcept}</span>
            </p>
          ) : null}
        </CardHeader>
        <CardContent>
          <ThumbnailPanel projectId={projectId} projectName={projectName} />
        </CardContent>
      </Card>

      <Card className={WORKSPACE_SNAP_TARGET}>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2">
              <Icon icon={VideoReplayIcon} className="text-muted-foreground" />
              Infographic clips
            </CardTitle>
            <Sample />
          </div>
          <CardDescription>
            Turn the strongest findings into short, loopable clips with a chart
            or callout burned in.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <ClipSample
            label="Hook"
            time="0:00 – 0:12"
            bars={[38, 55, 30, 72, 44]}
            callout="retention +18%"
          />
          <ClipSample
            label="Proof"
            time="2:41 – 2:58"
            bars={[62, 40, 78, 52, 88]}
            callout="68% drop-off"
          />
        </CardContent>
      </Card>

      <Card className={WORKSPACE_SNAP_TARGET}>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2">
              <Icon icon={SearchList01Icon} className="text-muted-foreground" />
              Title, description & tags
            </CardTitle>
            <Sample />
          </div>
          <CardDescription>
            A listing built from the transcript, ready to paste into the upload
            screen.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label
              htmlFor="seo-title"
              className="text-xs text-muted-foreground"
            >
              Title
            </Label>
            <Input
              id="seo-title"
              readOnly
              value="Why Most Side Projects Stall in Week 3 (And How to Fix It)"
            />
          </div>
          <div className="space-y-1.5">
            <Label
              htmlFor="seo-description"
              className="text-xs text-muted-foreground"
            >
              Description
            </Label>
            <Textarea
              id="seo-description"
              readOnly
              rows={4}
              value={
                "Most projects don't fail from a lack of ideas — they fail from a lack of a finish line.\n\n00:00 The week-3 wall\n01:12 Why motivation fades\n02:41 The one-sentence finish line\n04:05 Your next step"
              }
            />
          </div>
          <div className="space-y-1.5">
            <span className="text-xs text-muted-foreground">Tags</span>
            <div className="flex flex-wrap gap-1.5">
              {[
                "side projects",
                "productivity",
                "founders",
                "shipping",
                "motivation",
              ].map((tag) => (
                <Badge key={tag} variant="secondary">
                  {tag}
                </Badge>
              ))}
            </div>
          </div>
          <Button type="button" disabled>
            Generate listing
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

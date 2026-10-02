"use client";

import {
  ImageAdd01Icon,
  MagicWand01Icon,
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

function Sample() {
  return (
    <Badge
      variant="outline"
      className="border-border bg-muted text-muted-foreground"
    >
      Sample preview
    </Badge>
  );
}

/** A believable thumbnail mock: gradient, oversized hook, and a face bubble. */
function ThumbSample({
  headline,
  kicker,
  className,
}: {
  headline: string;
  kicker: string;
  className: string;
}) {
  return (
    <div
      className={`relative flex aspect-video flex-col justify-between overflow-hidden rounded-lg p-3 text-white shadow-sm ring-1 ring-foreground/10 ${className}`}
    >
      <span className="w-fit rounded bg-black/30 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide uppercase backdrop-blur-sm">
        {kicker}
      </span>
      <p className="max-w-[80%] font-heading text-lg leading-tight font-extrabold uppercase drop-shadow-md">
        {headline}
      </p>
      <div
        aria-hidden
        className="absolute -right-4 -bottom-6 size-24 rounded-full bg-white/20 ring-4 ring-white/30"
      />
    </div>
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
 * Packaging placeholder: thumbnail concepts, infographic clips, and a
 * search-ready listing. Everything is inert, but the content is realistic so the
 * finished module can be judged at a glance.
 */
export function PackagingModule() {
  return (
    <div className="space-y-8">
      <Card className={WORKSPACE_SNAP_TARGET}>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2">
              <Icon icon={ImageAdd01Icon} className="text-muted-foreground" />
              Thumbnail options
            </CardTitle>
            <Sample />
          </div>
          <CardDescription>
            Three concepts that match the hook, with the text sized to survive a
            phone screen.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-3">
          <ThumbSample
            headline="Stop wasting week 3"
            kicker="Mistake"
            className="bg-gradient-to-br from-rose-500 via-red-500 to-orange-500"
          />
          <ThumbSample
            headline="The 3-week rule"
            kicker="Framework"
            className="bg-gradient-to-br from-sky-500 via-indigo-500 to-violet-600"
          />
          <ThumbSample
            headline="Why projects die"
            kicker="Truth"
            className="bg-gradient-to-br from-emerald-500 via-teal-500 to-cyan-600"
          />
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
            <Icon icon={MagicWand01Icon} />
            Generate listing
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

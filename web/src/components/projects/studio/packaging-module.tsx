"use client";

import {
  ImageAdd01Icon,
  MagicWand01Icon,
  SearchList01Icon,
  SparklesIcon,
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

function Soon() {
  return (
    <Badge
      variant="outline"
      className="border-border bg-muted text-muted-foreground"
    >
      Coming soon
    </Badge>
  );
}

function PlaceholderTile({
  icon,
  label,
  className,
}: {
  icon: typeof ImageAdd01Icon;
  label: string;
  className?: string;
}) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border bg-muted/30 p-4 text-center text-muted-foreground ${className ?? ""}`}
    >
      <Icon icon={icon} className="size-5" />
      <span className="text-xs">{label}</span>
    </div>
  );
}

/**
 * Packaging placeholder: thumbnail concepts, infographic clips, and a
 * search-ready listing. Every control is inert until the generators land, but
 * the shape of the module is fixed now so it slots in without a redesign.
 */
export function PackagingModule() {
  return (
    <div className="space-y-10">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2">
              <Icon icon={ImageAdd01Icon} className="text-muted-foreground" />
              Thumbnail options
            </CardTitle>
            <Soon />
          </div>
          <CardDescription>
            Three concepts that match the hook, with the text sized to survive a
            phone screen.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-3">
          <PlaceholderTile
            icon={SparklesIcon}
            label="Concept A"
            className="aspect-video"
          />
          <PlaceholderTile
            icon={SparklesIcon}
            label="Concept B"
            className="aspect-video"
          />
          <PlaceholderTile
            icon={SparklesIcon}
            label="Concept C"
            className="aspect-video"
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2">
              <Icon icon={VideoReplayIcon} className="text-muted-foreground" />
              Infographic clips
            </CardTitle>
            <Soon />
          </div>
          <CardDescription>
            Turn the strongest findings into short, loopable clips with a chart
            or callout burned in.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <PlaceholderTile
            icon={VideoReplayIcon}
            label="Hook clip · 0:00–0:12"
            className="aspect-video"
          />
          <PlaceholderTile
            icon={VideoReplayIcon}
            label="Proof clip · 2:41–2:58"
            className="aspect-video"
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2">
              <Icon icon={SearchList01Icon} className="text-muted-foreground" />
              Title, description & tags
            </CardTitle>
            <Soon />
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
              disabled
              placeholder="A title will appear here"
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
              disabled
              rows={3}
              placeholder="A description with chapters and links will appear here"
            />
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

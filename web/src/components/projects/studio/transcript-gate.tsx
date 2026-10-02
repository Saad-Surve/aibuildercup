"use client";

import {
  CheckmarkCircle02Icon,
  CircleIcon,
  Loading03Icon,
  SparklesIcon,
  Upload01Icon,
} from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Marker, MarkerContent, MarkerIcon } from "@/components/ui/marker";
import type { StudioModule } from "@/lib/studio";

/**
 * The "generate the transcript first" gate.
 *
 * Some modules — review, captions, localization — are meaningless without a
 * transcript. Instead of hiding them, this states the one required step as a
 * short numbered rail (shadcn `Marker`) with the actual action inline, so the
 * creator can clear the prerequisite without leaving the module.
 */
export function TranscriptGate({
  module,
  hasVideo,
  processing,
  generating,
  failureMessage,
  onGenerate,
}: {
  module: StudioModule;
  hasVideo: boolean;
  processing: boolean;
  generating: boolean;
  failureMessage?: string | null;
  onGenerate: () => void;
}) {
  const working = processing || generating;
  return (
    <Card>
      <CardHeader>
        <CardTitle>{module.label} needs a transcript</CardTitle>
        <CardDescription>
          Two quick steps and this module opens with your video&apos;s words.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-1">
        <Marker>
          <MarkerIcon
            className={hasVideo ? "text-sev-good" : "text-muted-foreground"}
          >
            <Icon icon={hasVideo ? CheckmarkCircle02Icon : Upload01Icon} />
          </MarkerIcon>
          <MarkerContent>
            {hasVideo
              ? "Source video uploaded"
              : "Upload the source video first"}
          </MarkerContent>
        </Marker>

        <Marker>
          <MarkerIcon className={working ? "text-signal" : undefined}>
            <Icon
              icon={working ? Loading03Icon : SparklesIcon}
              className={working ? "animate-spin" : undefined}
            />
          </MarkerIcon>
          <MarkerContent>
            {working
              ? "Generating the transcript…"
              : "Generate the timestamped transcript"}
          </MarkerContent>
          <Button
            type="button"
            size="sm"
            className="ml-auto shrink-0"
            onClick={onGenerate}
            disabled={working || !hasVideo || generating}
          >
            <Icon icon={SparklesIcon} />
            {working ? "Generating…" : "Generate transcript"}
          </Button>
        </Marker>

        <Marker variant="separator" className="py-1">
          <MarkerContent>then {module.label} unlocks</MarkerContent>
        </Marker>

        <Marker className="opacity-60">
          <MarkerIcon>
            <Icon icon={CircleIcon} />
          </MarkerIcon>
          <MarkerContent>{module.description}</MarkerContent>
        </Marker>

        {failureMessage ? (
          <p className="pt-2 text-sm text-destructive" role="alert">
            {failureMessage}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

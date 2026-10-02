"use client";

import {
  ClosedCaptionIcon,
  LanguageSquareIcon,
  Mic02Icon,
  VolumeHighIcon,
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
import { languageLabel } from "@/lib/onboarding";

function LanguageChips({ languages }: { languages: string[] }) {
  if (languages.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No target languages yet. Add them from Edit project.
      </p>
    );
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {languages.map((language) => (
        <Badge key={language} variant="secondary">
          {languageLabel(language)}
        </Badge>
      ))}
    </div>
  );
}

/**
 * Localization placeholder: transcript translation and video dubbing, both
 * shaped around the project's target languages and the shared glossary corpus.
 */
export function LocalizationModule({
  primaryLanguage,
  targetLanguages,
}: {
  primaryLanguage: string;
  targetLanguages: string[];
}) {
  return (
    <div className="space-y-10">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2">
              <Icon
                icon={ClosedCaptionIcon}
                className="text-muted-foreground"
              />
              Transcript translation
            </CardTitle>
            <Badge
              variant="outline"
              className="border-border bg-muted text-muted-foreground"
            >
              Coming soon
            </Badge>
          </div>
          <CardDescription>
            Translate the transcript into each target language, holding names
            and product terms to the project glossary.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <p className="text-xs text-muted-foreground">
              From {languageLabel(primaryLanguage)}
            </p>
            <LanguageChips languages={targetLanguages} />
          </div>
          <Button type="button" disabled>
            <Icon icon={LanguageSquareIcon} />
            Translate transcript
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2">
              <Icon icon={Mic02Icon} className="text-muted-foreground" />
              Video dubbing
            </CardTitle>
            <Badge
              variant="outline"
              className="border-border bg-muted text-muted-foreground"
            >
              Coming soon
            </Badge>
          </div>
          <CardDescription>
            Synthesize each translation in a matching voice and mux it onto the
            source video.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <LanguageChips languages={targetLanguages} />
          <Button type="button" disabled>
            <Icon icon={VolumeHighIcon} />
            Dub video
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

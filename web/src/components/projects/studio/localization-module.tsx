"use client";

import {
  ClosedCaptionIcon,
  LanguageSquareIcon,
  Mic02Icon,
  PlayIcon,
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
import { WORKSPACE_SNAP_TARGET } from "@/lib/workspace";
import { languageLabel } from "@/lib/onboarding";

/** Fallback sample languages when the project has no targets yet. */
const SAMPLE_LANGUAGES = ["hi", "es", "fr"];

const SAMPLE_SOURCE =
  "Most projects don't fail from a lack of ideas — they fail from a lack of a finish line.";

const SAMPLE_TRANSLATIONS: Record<string, string> = {
  hi: "ज़्यादातर प्रोजेक्ट आइडियाज़ की कमी से नहीं, बल्कि एक फ़िनिश लाइन की कमी से रुकते हैं।",
  es: "La mayoría de los proyectos no fracasan por falta de ideas, sino por falta de una meta clara.",
  fr: "La plupart des projets n'échouent pas par manque d'idées, mais par manque d'une ligne d'arrivée.",
  de: "Die meisten Projekte scheitern nicht an fehlenden Ideen, sondern an einer fehlenden Ziellinie.",
  pt: "A maioria dos projetos não falha por falta de ideias, mas por falta de uma linha de chegada.",
  ja: "ほとんどのプロジェクトはアイデア不足ではなく、ゴールの欠如で止まります。",
  ar: "معظم المشاريع لا تفشل بسبب نقص الأفكار، بل بسبب غياب هدف واضح.",
};

function translationFor(language: string): string {
  return (
    SAMPLE_TRANSLATIONS[language] ??
    `[${languageLabel(language)}] ${SAMPLE_SOURCE}`
  );
}

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

/** Static waveform mock for the dubbing preview. */
function Waveform() {
  const bars = [30, 55, 40, 72, 48, 85, 60, 38, 66, 52, 78, 44, 58, 34, 70];
  return (
    <div className="flex h-12 items-center gap-0.5" aria-hidden="true">
      {bars.map((height, index) => (
        <span
          key={index}
          className="w-1 rounded-full bg-signal/60"
          style={{ height: `${height}%` }}
        />
      ))}
    </div>
  );
}

/**
 * Localization placeholder: transcript translation and video dubbing, shaped
 * around the project's target languages and the shared glossary corpus. The
 * sample lines show exactly what a translated/dubbed row will look like.
 */
export function LocalizationModule({
  primaryLanguage,
  targetLanguages,
}: {
  primaryLanguage: string;
  targetLanguages: string[];
}) {
  const languages =
    targetLanguages.length > 0 ? targetLanguages : SAMPLE_LANGUAGES;

  return (
    <div className="space-y-8">
      <Card className={WORKSPACE_SNAP_TARGET}>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2">
              <Icon
                icon={ClosedCaptionIcon}
                className="text-muted-foreground"
              />
              Transcript translation
            </CardTitle>
            <Sample />
          </div>
          <CardDescription>
            Translate the transcript into each target language, holding names
            and product terms to the project glossary.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5 rounded-lg border bg-muted/40 p-3">
            <span className="text-xs text-muted-foreground">
              Source · {languageLabel(primaryLanguage)}
            </span>
            <p className="text-sm">{SAMPLE_SOURCE}</p>
          </div>

          <ul className="space-y-2">
            {languages.map((language) => (
              <li
                key={language}
                className="flex items-start gap-3 rounded-lg border p-3"
              >
                <Badge variant="secondary" className="mt-0.5 shrink-0">
                  {languageLabel(language)}
                </Badge>
                <p className="min-w-0 flex-1 text-sm">
                  {translationFor(language)}
                </p>
              </li>
            ))}
          </ul>

          <Button type="button" disabled>
            <Icon icon={LanguageSquareIcon} />
            Translate transcript
          </Button>
        </CardContent>
      </Card>

      <Card className={WORKSPACE_SNAP_TARGET}>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle className="flex items-center gap-2">
              <Icon icon={Mic02Icon} className="text-muted-foreground" />
              Video dubbing
            </CardTitle>
            <Sample />
          </div>
          <CardDescription>
            Synthesize each translation in a matching voice and mux it onto the
            source video.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-4 rounded-lg border p-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-signal text-signal-foreground">
              <Icon icon={PlayIcon} className="size-5" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">
                  {languageLabel(languages[0] ?? "hi")} dub
                </span>
                <Badge variant="outline">Voice: Aarav</Badge>
              </div>
              <Waveform />
            </div>
            <span className="shrink-0 tabular text-xs text-muted-foreground">
              0:04 / 4:28
            </span>
          </div>

          <div className="flex flex-wrap gap-1.5">
            {languages.map((language) => (
              <Badge key={language} variant="secondary">
                {languageLabel(language)}
              </Badge>
            ))}
          </div>

          <Button type="button" disabled>
            <Icon icon={VolumeHighIcon} />
            Dub video
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

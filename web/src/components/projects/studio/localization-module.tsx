"use client";

import {
  ClosedCaptionIcon,
  LanguageSquareIcon,
} from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { DubbingPanel } from "@/components/projects/dubbing-panel";
import { GlossaryEditor } from "@/components/projects/studio/glossary-editor";
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

/**
 * Localization: transcript translation (still a preview) and the real dubbing
 * pipeline. {@link DubbingPanel} translates the transcript, re-voices it with
 * Text-to-Speech, and muxes the dubbed track back onto the source video — the
 * languages and voices come from the backend catalog, not this file.
 */
export function LocalizationModule({
  projectId,
  primaryLanguage,
  targetLanguages,
}: {
  projectId: string;
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

      <GlossaryEditor projectId={projectId} />

      <DubbingPanel
        projectId={projectId}
        targetLanguages={targetLanguages}
      />
    </div>
  );
}

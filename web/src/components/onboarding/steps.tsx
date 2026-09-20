"use client";

import { ChipSelect, type ChipOption } from "@/components/common/chip-select";
import { PersonaText } from "@/components/common/persona-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
  FieldTitle,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  CAPTION_PREFERENCES,
  FORMAT_OPTIONS,
  HOOK_STYLES,
  KNOWLEDGE_LEVELS,
  LANGUAGE_OPTIONS,
  LENGTH_OPTIONS,
  PLATFORM_OPTIONS,
  TIMEZONE_OPTIONS,
  TONE_OPTIONS,
  TOPIC_OPTIONS,
  type OnboardingAnswers,
} from "@/lib/onboarding";
import type { Persona } from "@/lib/types";

interface DataStepProps {
  answers: OnboardingAnswers;
  update: (patch: Partial<OnboardingAnswers>) => void;
}

function RequiredMark() {
  return (
    <span aria-hidden="true" className="text-destructive">
      *
    </span>
  );
}

function ChipField({
  label,
  hint,
  options,
  value,
  onChange,
  multiple = true,
}: {
  label: string;
  hint?: string;
  options: ChipOption[];
  value: string[];
  onChange: (value: string[]) => void;
  multiple?: boolean;
}) {
  return (
    <Field>
      <FieldTitle>{label}</FieldTitle>
      <ChipSelect
        options={options}
        value={value}
        onChange={onChange}
        multiple={multiple}
      />
      {hint ? <FieldDescription>{hint}</FieldDescription> : null}
    </Field>
  );
}

export function WelcomeStep() {
  const points = [
    "Your voice and audience, so suggestions sound like you.",
    "How reviewers should weigh clarity, truth, and structure.",
    "Where you publish, so platform fit is scored correctly.",
  ];

  return (
    <div className="space-y-6">
      <ul className="space-y-3">
        {points.map((point) => (
          <li key={point} className="flex gap-3 text-sm text-muted-foreground">
            <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-signal" />
            {point}
          </li>
        ))}
      </ul>
      <p className="text-sm text-muted-foreground">
        It takes about two minutes, and you can change all of it later.
      </p>
    </div>
  );
}

export function IdentityStep({ answers, update }: DataStepProps) {
  return (
    <FieldGroup>
      <Field>
        <FieldLabel htmlFor="creatorName">
          Creator name
          <RequiredMark />
        </FieldLabel>
        <Input
          id="creatorName"
          value={answers.creatorName ?? ""}
          onChange={(event) => update({ creatorName: event.target.value })}
          placeholder="Priya Sharma"
          autoComplete="name"
          aria-required="true"
        />
        <FieldDescription>
          Shown on your profile and used by the persona.
        </FieldDescription>
      </Field>

      <div className="grid gap-5 sm:grid-cols-2">
        <Field>
          <FieldLabel htmlFor="location">Location</FieldLabel>
          <Input
            id="location"
            value={answers.location ?? ""}
            onChange={(event) => update({ location: event.target.value })}
            placeholder="Mumbai, India"
          />
        </Field>

        <Field>
          <FieldLabel htmlFor="timezone">Timezone</FieldLabel>
          <Select
            value={answers.timezone ?? "Asia/Kolkata"}
            onValueChange={(value) => update({ timezone: String(value) })}
          >
            <SelectTrigger id="timezone" className="w-full">
              <SelectValue placeholder="Select timezone" />
            </SelectTrigger>
            <SelectContent>
              {TIMEZONE_OPTIONS.map((zone) => (
                <SelectItem key={zone} value={zone}>
                  {zone}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Field>
      </div>

      <Field>
        <FieldLabel htmlFor="primaryLanguage">Primary language</FieldLabel>
        <Select
          value={answers.primaryLanguage ?? "en"}
          onValueChange={(value) => update({ primaryLanguage: String(value) })}
        >
          <SelectTrigger id="primaryLanguage" className="w-full sm:w-64">
            <SelectValue placeholder="Select language" />
          </SelectTrigger>
          <SelectContent>
            {LANGUAGE_OPTIONS.map((language) => (
              <SelectItem key={language.value} value={language.value}>
                {language.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </Field>

      <Field>
        <FieldLabel htmlFor="bio">Short bio</FieldLabel>
        <Textarea
          id="bio"
          value={answers.bio ?? ""}
          onChange={(event) => update({ bio: event.target.value })}
          placeholder="What you make and why people watch."
          className="min-h-24"
        />
      </Field>
    </FieldGroup>
  );
}

export function TopicsStep({ answers, update }: DataStepProps) {
  return (
    <FieldGroup>
      <ChipField
        label="Main topics"
        hint="Pick as many as you actually cover."
        options={TOPIC_OPTIONS}
        value={answers.topics ?? []}
        onChange={(value) => update({ topics: value })}
      />
      <ChipField
        label="Formats"
        options={FORMAT_OPTIONS}
        value={answers.contentFormats ?? []}
        onChange={(value) => update({ contentFormats: value })}
      />
      <ChipField
        label="Typical length"
        options={LENGTH_OPTIONS}
        value={answers.typicalLength ? [answers.typicalLength] : []}
        onChange={(value) => update({ typicalLength: value[0] })}
        multiple={false}
      />
    </FieldGroup>
  );
}

export function AudienceStep({ answers, update }: DataStepProps) {
  return (
    <FieldGroup>
      <Field>
        <FieldLabel htmlFor="audience">Who are they?</FieldLabel>
        <Textarea
          id="audience"
          value={answers.audience ?? ""}
          onChange={(event) => update({ audience: event.target.value })}
          placeholder="Indian students and early-career professionals."
          className="min-h-24"
        />
        <FieldDescription>
          One or two sentences is plenty. This is the audience reviewers judge
          fit against.
        </FieldDescription>
      </Field>

      <div className="grid gap-5 sm:grid-cols-2">
        <Field>
          <FieldLabel htmlFor="audienceLocation">Where are they?</FieldLabel>
          <Input
            id="audienceLocation"
            value={answers.audienceLocation ?? ""}
            onChange={(event) =>
              update({ audienceLocation: event.target.value })
            }
            placeholder="India, metro and tier-2"
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="primaryGoal">What do they want?</FieldLabel>
          <Input
            id="primaryGoal"
            value={answers.primaryGoal ?? ""}
            onChange={(event) => update({ primaryGoal: event.target.value })}
            placeholder="Practical, actionable advice"
          />
        </Field>
      </div>

      <ChipField
        label="Knowledge level"
        options={KNOWLEDGE_LEVELS}
        value={answers.knowledgeLevel ? [answers.knowledgeLevel] : []}
        onChange={(value) => update({ knowledgeLevel: value[0] })}
        multiple={false}
      />
    </FieldGroup>
  );
}

export function StyleStep({ answers, update }: DataStepProps) {
  return (
    <FieldGroup>
      <ChipField
        label="Tone"
        options={TONE_OPTIONS}
        value={answers.tone ?? []}
        onChange={(value) => update({ tone: value })}
      />
      <ChipField
        label="Preferred hook"
        options={HOOK_STYLES}
        value={answers.hookStyle ? [answers.hookStyle] : []}
        onChange={(value) => update({ hookStyle: value[0] })}
        multiple={false}
      />
      <ChipField
        label="Caption density"
        hint="How much of the video should be on-screen text."
        options={CAPTION_PREFERENCES}
        value={answers.captionPreferences ? [answers.captionPreferences] : []}
        onChange={(value) => update({ captionPreferences: value[0] })}
        multiple={false}
      />
      <div className="grid gap-5 sm:grid-cols-2">
        <Field>
          <FieldLabel htmlFor="wordsToAvoid">Words to avoid</FieldLabel>
          <Input
            id="wordsToAvoid"
            value={answers.wordsToAvoid ?? ""}
            onChange={(event) => update({ wordsToAvoid: event.target.value })}
            placeholder="Jargon, hype, clickbait"
          />
        </Field>
        <Field>
          <FieldLabel htmlFor="regionalPreferences">Regional notes</FieldLabel>
          <Input
            id="regionalPreferences"
            value={answers.regionalPreferences ?? ""}
            onChange={(event) =>
              update({ regionalPreferences: event.target.value })
            }
            placeholder="Hinglish is fine, avoid slang"
          />
        </Field>
      </div>
    </FieldGroup>
  );
}

export function PlatformsStep({ answers, update }: DataStepProps) {
  return (
    <FieldGroup>
      <ChipField
        label="Publishing platforms"
        hint="Account connections for analytics come later. For now, just tell us where you post."
        options={PLATFORM_OPTIONS}
        value={answers.platforms ?? []}
        onChange={(value) => update({ platforms: value })}
      />
    </FieldGroup>
  );
}

export function PersonaStep({ persona }: { persona: Persona | null }) {
  if (!persona) {
    return (
      <p className="text-sm text-muted-foreground">Generating your persona…</p>
    );
  }

  return (
    <div className="space-y-4">
      <Badge variant="secondary">Version {persona.version}</Badge>

      <div className="rounded-xl bg-card p-5 ring-1 ring-foreground/10">
        <PersonaText content={persona.content} />
      </div>

      <p className="text-xs text-muted-foreground">
        Want to change this? Go back and edit your answers — the persona is
        generated from them.
      </p>
    </div>
  );
}

export function DoneStep({
  name,
  onFinish,
  mode = "onboarding",
}: {
  name?: string;
  onFinish: () => void;
  mode?: "onboarding" | "edit";
}) {
  const isEdit = mode === "edit";

  return (
    <div className="space-y-6">
      <p className="max-w-[60ch] text-sm text-muted-foreground">
        {isEdit
          ? "Your persona is updated. The reviewers will use the new version on your next run."
          : `${name ? `${name}, your` : "Your"} persona is saved and the reviewers are calibrated to it. Upload a video to see your first heatmap.`}
      </p>
      <Button size="lg" onClick={onFinish}>
        {isEdit ? "Back to profile" : "Go to dashboard"}
      </Button>
    </div>
  );
}

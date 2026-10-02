"use client";

import { useState } from "react";
import { SparklesIcon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { ChipSelect } from "@/components/common/chip-select";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { DRAFT_FORMAT_OPTIONS } from "@/lib/drafts";
import { LANGUAGE_OPTIONS, languageLabel } from "@/lib/onboarding";
import type { DraftBrief, DraftFormat } from "@/lib/types";

const FORMAT_CHIPS = DRAFT_FORMAT_OPTIONS.map((option) => ({
  value: option.value,
  label: option.label,
}));

/**
 * Captures (or re-captures) the brief that seeds a draft. Also the empty-state
 * generator: when a project has no draft yet, the same form produces the first
 * version.
 */
export function DraftBriefDialog({
  open,
  onOpenChange,
  initial,
  pending,
  onSubmit,
  title,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initial: DraftBrief;
  pending: boolean;
  onSubmit: (brief: DraftBrief) => void;
  title: string;
}) {
  const [brief, setBrief] = useState<DraftBrief>(initial);

  function update(patch: Partial<DraftBrief>) {
    setBrief((previous) => ({ ...previous, ...patch }));
  }

  const canSubmit = brief.topic.trim().length > 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            The brief is the only thing the writing partner needs. You can
            change it any time.
          </DialogDescription>
        </DialogHeader>

        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="brief-topic">What is it about?</FieldLabel>
            <Input
              id="brief-topic"
              value={brief.topic}
              onChange={(event) => update({ topic: event.target.value })}
              placeholder="e.g. Why most side projects stall in week three"
              maxLength={300}
            />
          </Field>

          <Field>
            <FieldLabel>Format</FieldLabel>
            <ChipSelect
              options={FORMAT_CHIPS}
              value={[brief.format]}
              multiple={false}
              onChange={(values) => {
                const next = values[0] as DraftFormat | undefined;
                if (next) update({ format: next });
              }}
            />
          </Field>

          <Field>
            <FieldLabel htmlFor="brief-audience">Who is it for?</FieldLabel>
            <Input
              id="brief-audience"
              value={brief.audience}
              onChange={(event) => update({ audience: event.target.value })}
              placeholder="e.g. first-time founders"
              maxLength={300}
            />
          </Field>

          <Field>
            <FieldLabel htmlFor="brief-tone">Tone</FieldLabel>
            <Input
              id="brief-tone"
              value={brief.tone}
              onChange={(event) => update({ tone: event.target.value })}
              placeholder="e.g. direct and a little funny"
              maxLength={200}
            />
          </Field>

          <Field>
            <FieldLabel htmlFor="brief-platform">Platform</FieldLabel>
            <Input
              id="brief-platform"
              value={brief.platform}
              onChange={(event) => update({ platform: event.target.value })}
              placeholder="e.g. YouTube, LinkedIn, newsletter"
              maxLength={120}
            />
          </Field>

          <Field>
            <FieldLabel htmlFor="brief-language">Language</FieldLabel>
            <Select
              value={brief.language}
              onValueChange={(value) => update({ language: String(value) })}
            >
              <SelectTrigger id="brief-language" className="w-full">
                <SelectValue placeholder="Select language">
                  {(value: unknown) =>
                    typeof value === "string"
                      ? languageLabel(value)
                      : "Select language"
                  }
                </SelectValue>
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
            <FieldLabel htmlFor="brief-instructions">Extra notes</FieldLabel>
            <Textarea
              id="brief-instructions"
              value={brief.instructions}
              onChange={(event) => update({ instructions: event.target.value })}
              placeholder="Anything the draft must include or avoid."
              rows={3}
            />
          </Field>
        </FieldGroup>

        <DialogFooter className="mt-5">
          <DialogClose
            render={
              <Button type="button" variant="outline" disabled={pending} />
            }
          >
            Cancel
          </DialogClose>
          <Button
            type="button"
            onClick={() => onSubmit(brief)}
            disabled={pending || !canSubmit}
          >
            <Icon icon={SparklesIcon} />
            {pending ? "Writing…" : "Generate draft"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

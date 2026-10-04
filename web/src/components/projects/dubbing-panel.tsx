"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ClosedCaptionIcon,
  Delete02Icon,
  FileAudioIcon,
  Loading03Icon,
  TranslationIcon,
} from "@hugeicons/core-free-icons";
import { toast } from "sonner";

import { Icon } from "@/components/common/icon";
import { DisabledReason } from "@/components/common/disabled-reason";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api-client";
import {
  createLocalization,
  deleteLocalization,
  listLocalizations,
  listLocalizationVoices,
} from "@/lib/dubbing";
import { formatBytes, getJob } from "@/lib/projects";
import type { Localization, LocalizationStatus } from "@/lib/types";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";
import { WORKSPACE_PANE_SNAP } from "@/lib/workspace";

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}

function statusVariant(status: LocalizationStatus) {
  if (status === "ready") return "default" as const;
  if (status === "failed") return "destructive" as const;
  return "secondary" as const;
}

function statusLabel(status: LocalizationStatus): string {
  switch (status) {
    case "translating":
      return "Translating";
    case "synthesizing":
      return "Synthesizing";
    case "muxing":
      return "Muxing";
    default:
      return status;
  }
}

function languageLabel(code: string): string {
  return code.toUpperCase();
}

/** Compare language codes by base tag, so `hi-IN` matches `hi`. */
function baseLanguage(code: string | null | undefined): string {
  return (code ?? "").replace("_", "-").split("-")[0].toLowerCase();
}

function downloadName(
  projectName: string | undefined,
  item: Localization,
  extension: string,
): string {
  const slug = (projectName ?? "video")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-");
  return `${slug}-${item.targetLanguage}-${item.localizationId.slice(0, 6)}.${extension}`;
}

export function DubbingPanel({
  projectId,
  projectName,
  targetLanguages,
}: {
  projectId: string;
  projectName?: string;
  targetLanguages?: string[];
}) {
  const queryClient = useQueryClient();
  const readOnly = useReadOnly();
  const [open, setOpen] = useState(false);

  const localizationsQuery = useQuery({
    queryKey: ["localizations", projectId],
    queryFn: () => listLocalizations(projectId),
    // Keep refreshing while any dub is in flight; stop once none are.
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some(
        (item) => item.status !== "ready" && item.status !== "failed",
      )
        ? 3000
        : false;
    },
    retry: false,
  });

  const localizations = localizationsQuery.data?.items ?? [];
  const active = localizations.find(
    (item) => item.status !== "ready" && item.status !== "failed",
  );

  const jobQuery = useQuery({
    queryKey: ["job", active?.jobId],
    queryFn: () => getJob(active?.jobId as string),
    enabled: Boolean(active?.jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "succeeded" ||
        status === "failed" ||
        status === "cancelled"
        ? false
        : 2000;
    },
    retry: false,
  });

  const deleteMutation = useMutation({
    mutationFn: (localizationId: string) =>
      deleteLocalization(projectId, localizationId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["localizations", projectId],
      });
      toast.success("Dub deleted");
    },
    onError: (error) =>
      toast.error(errorMessage(error, "Could not delete the dub.")),
  });

  const progress = jobQuery.data?.progress;
  const activePercent = progress?.percent ?? 5;

  return (
    <Card className={WORKSPACE_PANE_SNAP}>
      <CardHeader className="shrink-0">
        <div className="flex items-center gap-2">
          <Icon icon={TranslationIcon} className="text-muted-foreground" />
          <CardTitle>Dubbing</CardTitle>
        </div>
        <CardDescription>
          Re-voice this video in another language, keeping the original timing.
        </CardDescription>
        <div className="pt-2">
          <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
            <Button size="sm" onClick={() => setOpen(true)} disabled={readOnly}>
              <Icon icon={TranslationIcon} />
              Dub video
            </Button>
          </DisabledReason>
        </div>
      </CardHeader>
      <CardContent className="scroll-fade-y min-h-0 flex-1 overflow-y-auto overscroll-y-contain py-2">
        {localizationsQuery.isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : localizations.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            No dubs yet. Dub this video to reach viewers in another language.
          </p>
        ) : (
          <ul className="space-y-2">
            {localizations.map((item) => (
              <li
                key={item.localizationId}
                className="space-y-2 rounded-lg border p-2.5"
              >
                <div className="flex items-center gap-2">
                  <Icon
                    icon={FileAudioIcon}
                    className="shrink-0 text-muted-foreground"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm">
                        {item.fileName ??
                          `Dub · ${languageLabel(item.targetLanguage)}`}
                      </span>
                      <Badge variant={statusVariant(item.status)}>
                        {statusLabel(item.status)}
                      </Badge>
                    </div>
                    <p className="tabular text-xs text-muted-foreground">
                      {item.status === "ready"
                        ? `${item.width}×${item.height} · ${formatBytes(
                            item.sizeBytes,
                          )} · ${Math.round(item.durationMs / 1000)}s · ${languageLabel(
                            item.targetLanguage,
                          )}`
                        : (item.error?.message ?? "Working…")}
                    </p>
                    {item.status === "ready" ? (
                      <p className="text-xs text-muted-foreground/70">
                        Corpus v{item.corpusVersion} · Glossary v
                        {item.glossaryVersion}
                      </p>
                    ) : null}
                  </div>
                  {item.status === "ready" && item.downloadUrl ? (
                    <Button
                      size="sm"
                      variant="outline"
                      nativeButton={false}
                      render={
                        <a
                          href={item.downloadUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label="Download dubbed video"
                          download={downloadName(projectName, item, "mp4")}
                        />
                      }
                    >
                      <Icon icon={FileAudioIcon} />
                      Download
                    </Button>
                  ) : null}
                  {item.status === "ready" && item.captionsUrl ? (
                    <Button
                      size="sm"
                      variant="outline"
                      nativeButton={false}
                      render={
                        <a
                          href={item.captionsUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          aria-label="Download localized captions"
                          download={downloadName(projectName, item, "srt")}
                        />
                      }
                    >
                      <Icon icon={ClosedCaptionIcon} />
                      SRT
                    </Button>
                  ) : null}
                  <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label="Delete dub"
                      disabled={deleteMutation.isPending || readOnly}
                      onClick={() => deleteMutation.mutate(item.localizationId)}
                    >
                      <Icon icon={Delete02Icon} />
                    </Button>
                  </DisabledReason>
                </div>
                {active?.localizationId === item.localizationId ? (
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Icon
                        icon={Loading03Icon}
                        className="animate-spin text-signal"
                      />
                      <span>{progress?.message ?? "Working…"}</span>
                      <span className="ml-auto tabular">{activePercent}%</span>
                    </div>
                    <Progress value={activePercent} />
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        {localizationsQuery.error ? (
          <p className="pt-3 text-sm text-destructive" role="alert">
            {errorMessage(localizationsQuery.error, "Could not load dubs.")}
          </p>
        ) : null}
      </CardContent>

      <DubDialog
        projectId={projectId}
        preferredLanguage={targetLanguages?.[0]}
        open={open}
        onOpenChange={setOpen}
        onQueued={() =>
          void queryClient.invalidateQueries({
            queryKey: ["localizations", projectId],
          })
        }
      />
    </Card>
  );
}

function DubDialog({
  projectId,
  preferredLanguage,
  open,
  onOpenChange,
  onQueued,
}: {
  projectId: string;
  preferredLanguage?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onQueued: () => void;
}) {
  const readOnly = useReadOnly();
  const [language, setLanguage] = useState(preferredLanguage ?? "en");
  const [voiceId, setVoiceId] = useState<string | null>(null);
  const [keepOriginal, setKeepOriginal] = useState(false);

  const voicesQuery = useQuery({
    queryKey: ["localization-voices"],
    queryFn: listLocalizationVoices,
    enabled: open,
    staleTime: Infinity,
    retry: false,
  });

  const languages = voicesQuery.data?.items ?? [];
  const selectedLanguage =
    languages.find(
      (item) => baseLanguage(item.language) === baseLanguage(language),
    ) ?? languages[0];
  const voices = selectedLanguage?.voices ?? [];
  const selectedVoice =
    voices.find((voice) => voice.id === voiceId) ?? voices[0];

  const createMutation = useMutation({
    mutationFn: () =>
      createLocalization(projectId, {
        targetLanguage: selectedLanguage?.language ?? language,
        voice: selectedVoice?.id ?? null,
        keepOriginalAudio: keepOriginal,
      }),
    onSuccess: (accepted) => {
      toast.success("Dubbing started", {
        description: `Job ${accepted.jobId.slice(0, 8)} is running.`,
      });
      onQueued();
      onOpenChange(false);
    },
    onError: (error) =>
      toast.error(errorMessage(error, "Could not start the dub.")),
  });

  function handleLanguageChange(value: string | null) {
    if (!value) return;
    setLanguage(value);
    setVoiceId(null);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Dub into another language</DialogTitle>
          <DialogDescription>
            The transcript is translated, re-voiced with Text-to-Speech, and muxed
            back onto the video at the original timing.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Language</Label>
            <Select
              value={selectedLanguage?.language ?? ""}
              onValueChange={handleLanguageChange}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Choose a language" />
              </SelectTrigger>
              <SelectContent>
                {languages.map((item) => (
                  <SelectItem key={item.language} value={item.language}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Voice</Label>
            <Select
              value={selectedVoice?.id ?? ""}
              onValueChange={setVoiceId}
              disabled={voices.length === 0}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Choose a voice" />
              </SelectTrigger>
              <SelectContent>
                {voices.map((voice) => (
                  <SelectItem key={voice.id} value={voice.id}>
                    {voice.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              With multiple speakers, later speakers borrow other voices
              automatically.
            </p>
          </div>

          <label className="flex cursor-pointer items-center gap-2">
            <Checkbox
              checked={keepOriginal}
              onCheckedChange={(value) => setKeepOriginal(Boolean(value))}
            />
            <span className="text-sm">
              Keep the original audio quietly underneath
            </span>
          </label>

          <div className="flex items-center justify-end gap-2 pt-1">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Cancel
            </Button>
            <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
              <Button
                type="button"
                onClick={() => createMutation.mutate()}
                disabled={
                  createMutation.isPending ||
                  voicesQuery.isLoading ||
                  !selectedLanguage ||
                  readOnly
                }
              >
                <Icon
                  icon={
                    createMutation.isPending ? Loading03Icon : TranslationIcon
                  }
                  className={createMutation.isPending ? "animate-spin" : undefined}
                />
                {createMutation.isPending ? "Starting…" : "Start dubbing"}
              </Button>
            </DisabledReason>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

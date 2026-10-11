"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CloudUploadIcon,
  Delete02Icon,
  FileVideoIcon,
  ImageAdd01Icon,
  Link01Icon,
  Loading03Icon,
  Refresh01Icon,
} from "@hugeicons/core-free-icons";
import { format } from "date-fns";
import { toast } from "sonner";

import { Icon } from "@/components/common/icon";
import { DisabledReason } from "@/components/common/disabled-reason";
import { YouTubeConnections } from "@/components/projects/studio/youtube-connections";
import { ProjectSchedules } from "@/components/projects/studio/project-schedules";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api-client";
import { languageLabel } from "@/lib/onboarding";
import {
  listCaptionRenders,
  listAssets,
  listThumbnails,
  pickSourceAsset,
} from "@/lib/projects";
import { listLocalizations } from "@/lib/dubbing";
import {
  createPublish,
  deletePublish,
  listPublishes,
  retryPublish,
} from "@/lib/publishes";
import type {
  Localization,
  Publish,
  PublishCaptionFormat,
  PublishVisibility,
  ThumbnailConcept,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";
import { WORKSPACE_SNAP_TARGET } from "@/lib/workspace";

const CATEGORY_OPTIONS = [
  { value: "22", label: "People & Blogs" },
  { value: "27", label: "Education" },
  { value: "28", label: "Science & Technology" },
  { value: "24", label: "Entertainment" },
  { value: "26", label: "Howto & Style" },
  { value: "20", label: "Gaming" },
  { value: "23", label: "Comedy" },
  { value: "10", label: "Music" },
  { value: "17", label: "Sports" },
  { value: "25", label: "News & Politics" },
  { value: "19", label: "Travel & Events" },
  { value: "1", label: "Film & Animation" },
];

const PRIVACY_OPTIONS: { value: PublishVisibility; label: string }[] = [
  { value: "private", label: "Private" },
  { value: "unlisted", label: "Unlisted" },
  { value: "public", label: "Public" },
];

const CAPTION_OPTIONS: { value: PublishCaptionFormat; label: string }[] = [
  { value: "srt", label: "SRT (SubRip)" },
  { value: "vtt", label: "VTT (WebVTT)" },
  { value: "none", label: "No captions" },
];

function describe(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}

function padDateTimePart(part: number): string {
  return part.toString().padStart(2, "0");
}

function toDateTimeLocalInput(value: Date): string {
  return (
    `${value.getFullYear()}-${padDateTimePart(value.getMonth() + 1)}-${padDateTimePart(value.getDate())}` +
    `T${padDateTimePart(value.getHours())}:${padDateTimePart(value.getMinutes())}`
  );
}

function statusTone(status: Publish["status"]): string {
  if (status === "published")
    return "border-sev-good/40 bg-sev-good/10 text-sev-good";
  if (status === "failed")
    return "border-sev-high/40 bg-sev-high/10 text-sev-high";
  return "border-border bg-muted text-muted-foreground";
}

function PublishStatusBadge({ status }: { status: Publish["status"] }) {
  const label =
    status === "processing"
      ? "YouTube processing"
      : status.charAt(0).toUpperCase() + status.slice(1);
  return <Badge className={statusTone(status)}>{label}</Badge>;
}

export function PublishingModule({
  projectId,
  projectName,
  primaryLanguage,
  activeSourceId,
  onJobId,
}: {
  projectId: string;
  projectName: string;
  primaryLanguage: string;
  activeSourceId: string | null;
  onJobId?: (jobId: string) => void;
}) {
  const queryClient = useQueryClient();
  const readOnly = useReadOnly();

  const [connectionId, setConnectionId] = useState<string | null>(null);
  const [videoValue, setVideoValue] = useState("source");
  const [title, setTitle] = useState(projectName);
  const [description, setDescription] = useState("");
  const [tagsInput, setTagsInput] = useState("");
  const [categoryId, setCategoryId] = useState("22");
  const [privacy, setPrivacy] = useState<PublishVisibility>("private");
  const [madeForKids, setMadeForKids] = useState(false);
  const [notifySubscribers, setNotifySubscribers] = useState(true);
  const [captionFormat, setCaptionFormat] =
    useState<PublishCaptionFormat>("srt");
  const [captionLanguage, setCaptionLanguage] = useState(
    primaryLanguage || "en",
  );
  const [thumbnailId, setThumbnailId] = useState<string | null>(null);
  const [scheduleLater, setScheduleLater] = useState(false);
  const [goPublicAt, setGoPublicAt] = useState("");

  const assetsQuery = useQuery({
    queryKey: ["assets", projectId],
    queryFn: () => listAssets(projectId),
  });
  const rendersQuery = useQuery({
    queryKey: ["caption-renders", projectId],
    queryFn: () => listCaptionRenders(projectId),
  });
  const dubsQuery = useQuery({
    queryKey: ["localizations", projectId],
    queryFn: () => listLocalizations(projectId),
  });
  const thumbnailsQuery = useQuery({
    queryKey: ["thumbnails", projectId],
    queryFn: () => listThumbnails(projectId),
  });
  const publishesQuery = useQuery({
    queryKey: ["publishes", projectId],
    queryFn: () => listPublishes(projectId),
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      const active = items.some(
        (item) =>
          item.status === "queued" ||
          item.status === "uploading" ||
          item.status === "processing",
      );
      return active ? 4000 : false;
    },
    refetchIntervalInBackground: true,
  });

  const sourceAsset = pickSourceAsset(assetsQuery.data?.items, activeSourceId);
  const readyRenders = useMemo(
    () =>
      (rendersQuery.data?.items ?? []).filter(
        (render) => render.status === "ready" && render.storagePath,
      ),
    [rendersQuery.data],
  );
  const readyDubs = useMemo(
    () =>
      (dubsQuery.data?.items ?? []).filter(
        (dub) => dub.status === "ready" && dub.videoStoragePath,
      ),
    [dubsQuery.data],
  );
  const readyThumbnails = useMemo(
    () =>
      (thumbnailsQuery.data?.items ?? []).filter(
        (concept) => concept.status === "ready" && concept.previewUrl,
      ),
    [thumbnailsQuery.data],
  );

  const selectedThumbnail = readyThumbnails.find(
    (concept) => concept.thumbnailId === thumbnailId,
  );

  function resolvePublishAt(): string | null {
    if (!scheduleLater) return null;
    if (!goPublicAt) throw new Error("Pick a go-public date and time.");
    const when = new Date(goPublicAt).getTime();
    if (Number.isNaN(when)) throw new Error("Pick a go-public date and time.");
    if (when <= Date.now()) {
      throw new Error("The go-public time must be in the future.");
    }
    return new Date(when).toISOString();
  }

  const createMutation = useMutation({
    mutationFn: () => {
      if (!connectionId) throw new Error("Connect and choose a channel first.");
      const publishAt = resolvePublishAt();
      const [kind, id] = videoValue.includes(":")
        ? (videoValue.split(":", 2) as [
            "captionRender" | "localization",
            string,
          ])
        : (["source", null] as const);
      return createPublish(projectId, {
        connectionId,
        video: { kind, id },
        title: title.trim(),
        description,
        tags: tagsInput
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
        categoryId,
        // YouTube only accepts a scheduled go-public time on a private video;
        // the upload path forces private as well, so the listing matches it.
        privacyStatus: publishAt ? "private" : privacy,
        madeForKids,
        notifySubscribers,
        captionFormat,
        captionLanguage,
        captionName: languageLabel(captionLanguage),
        thumbnail: thumbnailId ? { thumbnailId } : null,
        publishAt,
      });
    },
    onSuccess: (accepted) => {
      toast.success(
        scheduleLater ? "Upload scheduled" : "Publishing to YouTube…",
        scheduleLater && goPublicAt
          ? {
              description: `Goes public ${format(new Date(goPublicAt), "d MMM, HH:mm")}.`,
            }
          : undefined,
      );
      onJobId?.(accepted.jobId);
      void queryClient.invalidateQueries({
        queryKey: ["publishes", projectId],
      });
      void queryClient.invalidateQueries({ queryKey: ["job", accepted.jobId] });
    },
    onError: (error) => toast.error(describe(error, "Publishing failed.")),
  });

  const retryMutation = useMutation({
    mutationFn: (publishId: string) => retryPublish(projectId, publishId),
    onSuccess: (accepted) => {
      onJobId?.(accepted.jobId);
      void queryClient.invalidateQueries({
        queryKey: ["publishes", projectId],
      });
    },
    onError: (error) => toast.error(describe(error, "Could not retry.")),
  });

  const deleteMutation = useMutation({
    mutationFn: (publishId: string) => deletePublish(projectId, publishId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["publishes", projectId],
      });
    },
    onError: (error) => toast.error(describe(error, "Could not delete.")),
  });

  const publishes = publishesQuery.data?.items ?? [];
  const canSubmit =
    Boolean(connectionId) &&
    title.trim().length > 0 &&
    !createMutation.isPending;

  return (
    <div className="space-y-8">
      <Card className={WORKSPACE_SNAP_TARGET}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Icon icon={Link01Icon} className="text-muted-foreground" />
            YouTube channel
          </CardTitle>
          <CardDescription>
            Connect the Gmail account that owns the channel you publish to.
            Google shows its account chooser, so you can pick a different
            account than the one you signed in with.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <YouTubeConnections
            redirectPath={
              typeof window === "undefined"
                ? undefined
                : window.location.pathname
            }
            selectable
            selectedId={connectionId}
            onSelect={setConnectionId}
          />
        </CardContent>
      </Card>

      <Card className={WORKSPACE_SNAP_TARGET}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Icon icon={FileVideoIcon} className="text-muted-foreground" />
            What to upload
          </CardTitle>
          <CardDescription>
            Pick the cut, the thumbnail, and the caption track. Everything is
            resolved now, so a later edit cannot change an upload that is
            already running.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Video</Label>
            <Select
              value={videoValue}
              onValueChange={(value) => setVideoValue(value ?? "source")}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="source">
                  {sourceAsset
                    ? "Original source video"
                    : "Original source video (missing)"}
                </SelectItem>
                {readyRenders.map((render) => (
                  <SelectItem
                    key={render.captionRenderId}
                    value={`captionRender:${render.captionRenderId}`}
                  >
                    Captioned video ·{" "}
                    {format(new Date(render.createdAt), "d MMM, HH:mm")}
                  </SelectItem>
                ))}
                {readyDubs.map((dub: Localization) => (
                  <SelectItem
                    key={dub.localizationId}
                    value={`localization:${dub.localizationId}`}
                  >
                    Dubbed · {languageLabel(dub.targetLanguage)} ·{" "}
                    {format(new Date(dub.createdAt), "d MMM, HH:mm")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label className="text-xs text-muted-foreground">
              Thumbnail (optional)
            </Label>
            {readyThumbnails.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                No ready thumbnails yet. Generate one in the packaging module.
              </p>
            ) : (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {readyThumbnails.map((concept: ThumbnailConcept) => {
                  const selected = thumbnailId === concept.thumbnailId;
                  return (
                    <button
                      key={concept.thumbnailId}
                      type="button"
                      onClick={() =>
                        setThumbnailId(selected ? null : concept.thumbnailId)
                      }
                      className={cn(
                        "group relative overflow-hidden rounded-lg border text-left",
                        selected
                          ? "border-signal ring-2 ring-signal/40"
                          : "border-border",
                      )}
                    >
                      {concept.previewUrl ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={concept.previewUrl}
                          alt={concept.headline}
                          className="aspect-video w-full object-cover"
                        />
                      ) : null}
                      <span className="block truncate px-2 py-1.5 text-xs">
                        {concept.headline || "Thumbnail"}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
            {selectedThumbnail ? (
              <p className="text-xs text-muted-foreground">
                Selected:{" "}
                <span className="text-foreground">
                  {selectedThumbnail.headline}
                </span>
              </p>
            ) : null}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Captions</Label>
              <Select
                value={captionFormat}
                onValueChange={(value) =>
                  setCaptionFormat(value as PublishCaptionFormat)
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CAPTION_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">
                Caption language
              </Label>
              <Input
                value={captionLanguage}
                onChange={(event) => setCaptionLanguage(event.target.value)}
                placeholder="en"
                disabled={captionFormat === "none"}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className={WORKSPACE_SNAP_TARGET}>
        <CardHeader>
          <CardTitle>Listing</CardTitle>
          <CardDescription>
            How the video appears on YouTube. You can change all of it later in
            Studio.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label
              htmlFor="publish-title"
              className="text-xs text-muted-foreground"
            >
              Title
            </Label>
            <Input
              id="publish-title"
              value={title}
              maxLength={100}
              onChange={(event) => setTitle(event.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label
              htmlFor="publish-description"
              className="text-xs text-muted-foreground"
            >
              Description
            </Label>
            <Textarea
              id="publish-description"
              value={description}
              rows={4}
              onChange={(event) => setDescription(event.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <Label
              htmlFor="publish-tags"
              className="text-xs text-muted-foreground"
            >
              Tags (comma separated)
            </Label>
            <Input
              id="publish-tags"
              value={tagsInput}
              onChange={(event) => setTagsInput(event.target.value)}
              placeholder="side projects, productivity, founders"
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">Category</Label>
              <Select
                value={categoryId}
                onValueChange={(value) => setCategoryId(value ?? "22")}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORY_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs text-muted-foreground">
                Visibility
              </Label>
              <Select
                value={privacy}
                onValueChange={(value) =>
                  setPrivacy(value as PublishVisibility)
                }
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PRIVACY_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-2 text-sm">
            <label className="flex items-start gap-2">
              <Checkbox
                checked={madeForKids}
                onCheckedChange={(value) => setMadeForKids(Boolean(value))}
              />
              <span>
                Made for kids
                <span className="block text-xs text-muted-foreground">
                  YouTube requires this declaration. Most creator content is not
                  made for kids.
                </span>
              </span>
            </label>
            <label className="flex items-start gap-2">
              <Checkbox
                checked={notifySubscribers}
                onCheckedChange={(value) =>
                  setNotifySubscribers(Boolean(value))
                }
              />
              <span>Notify subscribers when it publishes</span>
            </label>
            <label className="flex items-start gap-2">
              <Checkbox
                checked={scheduleLater}
                onCheckedChange={(value) => setScheduleLater(Boolean(value))}
              />
              <span>
                Schedule for later
                <span className="block text-xs text-muted-foreground">
                  Uploads now as private, goes public at the chosen time.
                </span>
              </span>
            </label>
            {scheduleLater ? (
              <div className="space-y-1.5 pl-6">
                <Label
                  htmlFor="publish-go-public"
                  className="text-xs text-muted-foreground"
                >
                  Go-public time
                </Label>
                <Input
                  id="publish-go-public"
                  type="datetime-local"
                  value={goPublicAt}
                  min={toDateTimeLocalInput(new Date())}
                  onChange={(event) => setGoPublicAt(event.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Scheduled videos stay private until then. The slot also
                  appears on the calendar.
                </p>
              </div>
            ) : null}
          </div>

          <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
            <Button
              type="button"
              onClick={() => createMutation.mutate()}
              disabled={
                !canSubmit || readOnly || (scheduleLater && !goPublicAt)
              }
            >
              {createMutation.isPending ? (
                <Icon icon={Loading03Icon} className="animate-spin" />
              ) : (
                <Icon icon={CloudUploadIcon} />
              )}
              {scheduleLater ? "Schedule upload" : "Publish to YouTube"}
            </Button>
          </DisabledReason>
          {!connectionId ? (
            <p className="text-xs text-muted-foreground">
              Choose a connected channel above first.
            </p>
          ) : null}
        </CardContent>
      </Card>

      <ProjectSchedules
        projectId={projectId}
        projectName={projectName}
        publishes={publishes}
      />

      <Card className={WORKSPACE_SNAP_TARGET}>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Icon icon={ImageAdd01Icon} className="text-muted-foreground" />
            Publish history
          </CardTitle>
          <CardDescription>
            Every upload attempt for this project.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {publishes.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Nothing published yet.
            </p>
          ) : (
            publishes.map((publish) => (
              <div
                key={publish.publishId}
                className="space-y-2 rounded-lg border border-border p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">
                      {publish.title}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {publish.connectionDisplayName ?? "YouTube"} ·{" "}
                      {format(new Date(publish.createdAt), "d MMM, HH:mm")}
                      {publish.publishAt ? (
                        <>
                          {" "}
                          · Goes public{" "}
                          {format(new Date(publish.publishAt), "d MMM, HH:mm")}
                        </>
                      ) : null}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <PublishStatusBadge status={publish.status} />
                    {publish.status === "failed" ? (
                      <DisabledReason
                        reason={readOnly ? READ_ONLY_REASON : null}
                      >
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() =>
                            retryMutation.mutate(publish.publishId)
                          }
                          disabled={retryMutation.isPending || readOnly}
                        >
                          <Icon icon={Refresh01Icon} />
                          Retry
                        </Button>
                      </DisabledReason>
                    ) : null}
                    {publish.youtubeUrl ? (
                      <a
                        href={publish.youtubeUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-signal hover:underline"
                      >
                        Open on YouTube
                      </a>
                    ) : null}
                    <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
                      <Button
                        type="button"
                        size="icon-sm"
                        variant="ghost"
                        aria-label="Delete publish record"
                        onClick={() => deleteMutation.mutate(publish.publishId)}
                        disabled={deleteMutation.isPending || readOnly}
                      >
                        <Icon icon={Delete02Icon} />
                      </Button>
                    </DisabledReason>
                  </div>
                </div>
                {publish.status === "uploading" ||
                publish.status === "queued" ? (
                  <Progress value={publish.uploadProgress} />
                ) : null}
                {publish.status === "failed" && publish.error?.message ? (
                  <p className="text-xs text-destructive">
                    {publish.error.message}
                  </p>
                ) : null}
                {publish.steps.length > 0 ? (
                  <p className="text-xs text-muted-foreground">
                    {publish.steps[publish.steps.length - 1]}
                  </p>
                ) : null}
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}

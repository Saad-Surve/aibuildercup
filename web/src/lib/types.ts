export interface Preferences {
  timezone: string;
  defaultLanguage: string;
}

export interface AvatarState {
  seed: string | null;
  selections: Record<string, string>;
  colors: Record<string, string>;
}

export interface Me {
  uid: string;
  displayName: string | null;
  email: string | null;
  onboardingCompleted: boolean;
  personaVersion: number | null;
  preferences: Preferences;
  avatar: AvatarState | null;
  /** True for the read-only demo account; the API refuses its writes. */
  readOnly: boolean;
}

export interface Persona {
  version: number;
  content: string;
  storagePath: string;
}

export interface PersonaRef {
  onboardingCompleted: boolean;
  personaVersion: number;
  personaStoragePath: string;
}

export interface OnboardingState {
  status: "not_started" | "in_progress" | "completed";
  currentStep: string | null;
  answers: Record<string, unknown>;
}

export interface OnboardingResearchSource {
  title: string;
  url: string;
}

export interface OnboardingResearch {
  /** Full merged answers after research; load straight into the form. */
  answers: Record<string, unknown>;
  sources: OnboardingResearchSource[];
  queries: string[];
  /** Google Search Suggestions HTML; must be rendered exactly as returned. */
  searchSuggestions: string;
}

export type ProjectStatus =
  | "draft"
  | "uploading"
  | "processing"
  | "ready"
  | "partial_failure"
  | "failed"
  | "archived";

export type ProjectKind = "video" | "draft";

export type DraftFormat = "written" | "script";

export interface DraftSummary {
  title: string;
  preview: string;
  wordCount: number;
  blockCount: number;
  versionCount: number;
}

export interface Project {
  projectId: string;
  name: string;
  description: string;
  thumbnailConcept: string;
  primaryLanguage: string;
  targetLanguages: string[];
  targetPlatforms: string[];
  isDemo: boolean;
  demoProfileId: string | null;
  status: ProjectStatus;
  progress: {
    stage: string | null;
    percent: number;
    message: string | null;
  } | null;
  /** The project's active source-video asset. */
  sourceAssetId: string | null;
  /** Revision number of the active source video; null if none uploaded. */
  sourceRevision: number | null;
  /** Number of source-video revisions uploaded for this project. */
  revisionCount: number;
  /** Applied thumbnail object path, if any. */
  posterStoragePath: string | null;
  /** Signed cover URL minted on read; use it as the project card/player poster. */
  posterUrl: string | null;
  /** `video` runs the upload pipeline; `draft` opens the writing studio. */
  kind: ProjectKind;
  draftFormat: DraftFormat;
  /** Denormalised draft stats for cards; null for video projects. */
  draftSummary: DraftSummary | null;
  /** Script source: the draft project this video is based on, if any. */
  sourceDraftId: string | null;
  /** Draft title snapshotted at link time, so the lineage renders without a join. */
  sourceDraftName: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface CreateProjectInput {
  name: string;
  description?: string;
  thumbnailConcept?: string;
  primaryLanguage?: string;
  targetLanguages?: string[];
  targetPlatforms?: string[];
  kind?: ProjectKind;
  sourceDraftId?: string;
  draftFormat?: DraftFormat;
  draftBrief?: DraftBrief;
}

export interface ProjectList {
  items: Project[];
  nextPageToken: string | null;
}

// ----------------------------------------------------------------------- draft

export type DraftBlockType = "heading" | "paragraph";
export type DraftStatus = "empty" | "generating" | "ready" | "failed";
export type DraftAssistMode = "chat" | "rewrite" | "alternatives" | "continue";

export interface DraftBrief {
  topic: string;
  format: DraftFormat;
  audience: string;
  tone: string;
  platform: string;
  language: string;
  instructions: string;
  targetWords: number;
}

export interface DraftVersion {
  versionId: string;
  text: string;
  label: string;
  origin: "assistant" | "user";
  createdAt: string;
}

export interface DraftBlock {
  blockId: string;
  type: DraftBlockType;
  versions: DraftVersion[];
  activeVersionId: string;
}

export interface DraftMessage {
  messageId: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
}

export interface DraftGroundingSource {
  title: string;
  url: string;
}

export interface DraftGrounding {
  queries: string[];
  sources: DraftGroundingSource[];
  /** Google Search Suggestions HTML; must be rendered exactly as returned. */
  searchSuggestions: string;
  updatedAt: string | null;
}

export interface Draft {
  projectId: string;
  title: string;
  status: DraftStatus;
  brief: DraftBrief;
  blocks: DraftBlock[];
  messages: DraftMessage[];
  error: string | null;
  summary: DraftSummary;
  /** Latest grounded research (generation or assist); null when the draft used none. */
  grounding: DraftGrounding | null;
  /** Platform drafts posted from here, one per platform (Substack links are syncable). */
  linkedPosts: LinkedExternalPost[];
  createdAt: string | null;
  updatedAt: string | null;
}

export type AssetStatus =
  | "pending"
  | "uploading"
  | "uploaded"
  | "processing"
  | "ready"
  | "failed"
  | "deleted";

export interface Asset {
  assetId: string;
  projectId: string;
  type: string;
  status: AssetStatus;
  storagePath: string;
  mimeType: string;
  sizeBytes: number;
  durationMs: number | null;
  /** Source-video revision number; null for non-source and legacy assets. */
  revision: number | null;
  createdAt: string;
  updatedAt: string;
}

export interface AssetList {
  items: Asset[];
}

export interface Revision {
  revision: number;
  assetId: string;
  status: AssetStatus;
  mimeType: string;
  sizeBytes: number;
  durationMs: number | null;
  storagePath: string;
  isActive: boolean;
  /** The newest transcript built from this revision, if any. */
  transcriptId: string | null;
  transcriptVersion: number | null;
  /** How many analysis runs were built from this revision. */
  analysisRunCount: number;
  createdAt: string;
}

export interface RevisionList {
  items: Revision[];
}

export interface RevisionActivation {
  assetId: string;
  revision: number;
  /** The transcript made active, or null when one had to be generated. */
  transcriptId: string | null;
  /** The queued transcribe job when the revision had no transcript yet. */
  jobId: string | null;
}

export interface UploadSession {
  assetId: string;
  storagePath: string;
  uploadUrl: string;
  expiresAt: string;
  requiredHeaders: Record<string, string>;
}

export interface DownloadUrl {
  url: string;
  expiresAt: string;
}

export type JobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export interface Job {
  jobId: string;
  type: string;
  status: JobStatus;
  progress: {
    percent: number;
    step: string | null;
    message: string | null;
  };
  error: Record<string, unknown> | null;
  createdAt: string;
  updatedAt: string;
}

export interface AcceptedJob {
  jobId: string;
  status: string;
}

export interface TranscriptSegment {
  segmentId: string;
  index: number;
  startMs: number;
  endMs: number;
  text: string;
  speaker?: number | null;
}

export interface Transcript {
  transcriptId: string;
  language: string;
  durationMs: number;
  segments: TranscriptSegment[];
  /** Speaker index -> inferred role/name, e.g. { "0": "Host" }. */
  speakerLabels?: Record<string, string>;
}

export interface TranscriptVersion {
  transcriptId: string;
  version: number;
  language: string;
  durationMs: number;
  wordCount: number;
  createdAt: string | null;
}

export const ANALYSIS_DIMENSIONS = [
  "truth_evidence",
  "clarity",
  "pacing_retention",
  "legal_safety",
  "cultural_localization",
  "platform_fit",
  "audience_brand",
  "emotional_impact",
  "conversion_cta",
] as const;

export type AnalysisDimension = (typeof ANALYSIS_DIMENSIONS)[number];

/** API minimum; the studio requests all nine ANALYSIS_DIMENSIONS. */
export const CORE_DIMENSIONS: AnalysisDimension[] = [
  "truth_evidence",
  "clarity",
  "pacing_retention",
  "legal_safety",
  "cultural_localization",
  "platform_fit",
];

export type Severity = "none" | "low" | "medium" | "high" | "critical";

export type HeatmapColor = "green" | "yellow" | "orange" | "red";

export type AnalysisRunStatus =
  | "queued"
  | "running"
  | "ready"
  | "partial_failure"
  | "failed";

export type ReviewerRunStatus = "queued" | "running" | "succeeded" | "failed";

export interface TokenUsage {
  input: number;
  output: number;
}

export interface AnalysisRun {
  analysisRunId: string;
  jobId: string;
  status: AnalysisRunStatus;
  transcriptId: string;
  sourceAssetId: string | null;
  personaVersion: number | null;
  fanoutStrategy: string;
  chunkCount: number;
  requestedDimensions: AnalysisDimension[];
  completedDimensions: AnalysisDimension[];
  overallScore: number | null;
  scoreByDimension: Record<string, number>;
  findingCounts: Record<string, number>;
  modelConfigVersion: string;
  promptVersion: string;
  costEstimateUsd: number;
  error: { code: string; message: string } | null;
  createdAt: string;
  updatedAt: string;
}

export interface ReviewerToolCall {
  tool: "extract_frame" | "cut_clip" | string;
  timestampMs: number;
  label: string;
  mimeType: string;
  /** Cloud Storage object for the fetched frame/clip; empty when the call failed. */
  contentPath: string;
  ok: boolean;
}

export interface ReviewerGroundingSource {
  title: string;
  url: string;
}

export interface ReviewerRun {
  reviewerRunId: string;
  dimension: AnalysisDimension;
  status: ReviewerRunStatus;
  findingCount: number;
  costEstimateUsd: number;
  durationMs: number;
  model: string | null;
  inputSegmentCount: number;
  /** Footage the reviewer fetched through the function-calling tools. */
  toolCalls: ReviewerToolCall[];
  /** Web search queries the grounded reviewer ran (truth_evidence only). */
  groundingQueries: string[];
  /** Sources the grounded reviewer verified claims against. */
  groundingSources: ReviewerGroundingSource[];
  /** Google-provided Search Suggestions HTML; must be displayed when non-empty. */
  groundingSearchSuggestions: string;
  tokenUsage: TokenUsage;
  error: { code: string; message: string } | null;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface FindingEvidence {
  quote: string;
  critique_and_reasoning: string;
}

export interface FindingCitation {
  title?: string;
  url?: string;
}

export interface Finding {
  findingId: string;
  dimension: AnalysisDimension;
  reviewerRunId: string | null;
  segmentId: string | null;
  startMs: number;
  endMs: number;
  score: number;
  confidence: number;
  severity: Severity;
  findingType: string;
  evidence: FindingEvidence;
  suggestion: string;
  citations: FindingCitation[];
}

export interface HeatmapBin {
  binId: string;
  dimension: AnalysisDimension;
  startMs: number;
  endMs: number;
  score: number;
  severity: Severity;
  color: HeatmapColor;
  findingIds: string[];
}

/** A span of the video one reviewer dimension actually read (bins only exist where it flagged). */
export interface HeatmapCoverage {
  dimension: AnalysisDimension;
  startMs: number;
  endMs: number;
}

export interface InterestPoint {
  startMs: number;
  endMs: number;
  /** Relative interest within this video, 0 lowest to 1 highest. Not retention. */
  value: number;
  /** Typical drop-off at this point in a video, on the same scale as `value`. */
  baseline?: number;
  driversUp?: string[];
  driversDown?: string[];
  /** wpm, speechRatio, pauseMs, novelty, plus 1-5 Gemini ratings when that pass ran. */
  signals?: Record<string, number>;
}

/** A stretch that most beats (peak) or falls short of (dip) the typical drop-off. */
export interface InterestMoment {
  kind: "peak" | "dip";
  startMs: number;
  endMs: number;
  value: number;
  drivers?: string[];
  findingIds?: string[];
}

export interface InterestCalibration {
  label?: string;
  videos?: number;
  channels?: number;
  testVideos?: number;
  heldOutSpearman?: number;
  positionBaselineSpearman?: number;
  /** Correlation of predicted and true deviation from the typical drop-off. */
  liftSpearman?: number;
  peakPrecision?: number;
  dipPrecision?: number;
  trainedAt?: string;
}

export interface InterestCurve {
  analysisRunId: string;
  status: "ready" | "failed";
  modelVersion?: string;
  featureSource?: "transcript+gemini" | "transcript";
  binMs?: number;
  durationMs?: number;
  points: InterestPoint[];
  peaks?: InterestMoment[];
  dips?: InterestMoment[];
  calibration?: InterestCalibration | null;
  costEstimateUsd?: number;
  error?: Record<string, unknown> | null;
  createdAt?: string;
}

export interface StartAnalysisInput {
  dimensions?: AnalysisDimension[];
  platform?: string;
  includeVisualReview?: boolean;
  transcriptVersion?: number;
}

export interface StartAnalysisResponse {
  analysisRunId: string;
  jobId: string;
  status: string;
}

// --------------------------------------------------------------------- captions

export type CaptionFontFamily = "Montserrat" | "Poppins";
export type CaptionBackground = "outline" | "box" | "none";
export type CaptionPosition = "top" | "middle" | "bottom";
export type CaptionRenderStatus = "queued" | "rendering" | "ready" | "failed";

/**
 * How burned captions look. Sized in pixels at a 1080-tall reference frame; the
 * backend scales them to the real video, so one style fits landscape and vertical.
 */
export interface CaptionStyle {
  preset: string;
  fontFamily: CaptionFontFamily;
  fontSize: number;
  bold: boolean;
  italic: boolean;
  uppercase: boolean;
  textColor: string;
  outlineColor: string;
  outlineWidth: number;
  shadow: number;
  background: CaptionBackground;
  backgroundColor: string;
  backgroundOpacity: number;
  position: CaptionPosition;
  marginV: number;
  maxCharsPerLine: number;
  maxLines: number;
  /** Karaoke: spoken words fill with `highlightColor`. */
  highlightEnabled: boolean;
  highlightColor: string;
  /** Prefix each cue with the speaker name when there is more than one voice. */
  speakerLabels: boolean;
}

export interface CaptionPreset {
  id: string;
  label: string;
  description: string;
  style: CaptionStyle;
}

export interface CaptionRender {
  captionRenderId: string;
  projectId: string;
  status: CaptionRenderStatus;
  style: CaptionStyle;
  sourceAssetId: string | null;
  sourceTranscriptId: string | null;
  transcriptVersion: number | null;
  /** Set when this render burns a dub's localized captions onto its dubbed video. */
  localizationId: string | null;
  fileName: string | null;
  storagePath: string | null;
  assStoragePath: string | null;
  mimeType: string;
  sizeBytes: number;
  durationMs: number;
  width: number;
  height: number;
  jobId: string | null;
  error: { code?: string; message?: string } | null;
  downloadUrl: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface CaptionRenderAccepted {
  captionRenderId: string;
  jobId: string;
  status: string;
}

// ------------------------------------------------------------------- thumbnails

export type ThumbnailAspect = "16:9" | "9:16" | "1:1";
export type ThumbnailStatus = "queued" | "generating" | "ready" | "failed";

export interface ThumbnailCritique {
  legibility: number;
  promise: number;
  platformFit: number;
  summary: string;
  suggestions: string[];
}

export interface ThumbnailVersion {
  versionId: string;
  version: number;
  storagePath: string | null;
  mimeType: string;
  width: number;
  height: number;
  sizeBytes: number;
  instruction: string;
  headline: string;
  rationale: string;
  referenceTimestampsMs: number[];
  critique: ThumbnailCritique | null;
  model: string;
  costUsd: number;
  createdAt: string;
}

export interface ThumbnailConcept {
  thumbnailId: string;
  projectId: string;
  status: ThumbnailStatus;
  aspect: ThumbnailAspect;
  headline: string;
  rationale: string;
  sourceTimestampMs: number | null;
  referenceTimestampsMs: number[];
  activeVersionId: string | null;
  versions: ThumbnailVersion[];
  isApplied: boolean;
  jobId: string | null;
  error: { code?: string; message?: string } | null;
  previewUrl: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface GenerateThumbnailsInput {
  count?: number;
  aspect?: ThumbnailAspect;
  imageSize?: string;
  brief?: string;
  useRealFrames?: boolean;
  useProModel?: boolean;
}

export interface ThumbnailBatchAccepted {
  thumbnailIds: string[];
  jobId: string;
  status: string;
}

export interface ThumbnailRevisionAccepted {
  thumbnailId: string;
  jobId: string;
  status: string;
}

export type LocalizationStatus =
  | "queued"
  | "translating"
  | "synthesizing"
  | "muxing"
  | "ready"
  | "failed";

export interface LocalizationVoice {
  id: string;
  name: string;
  label: string;
  gender: "male" | "female" | "neutral";
}

export interface LocalizationLanguage {
  language: string;
  label: string;
  voices: LocalizationVoice[];
}

export interface LocalizationVoiceList {
  items: LocalizationLanguage[];
}

export interface Localization {
  localizationId: string;
  projectId: string;
  status: LocalizationStatus;
  sourceAssetId: string | null;
  sourceTranscriptId: string | null;
  transcriptVersion: number | null;
  sourceLanguage: string | null;
  targetLanguage: string;
  voice: string | null;
  speakerVoices: Record<string, string>;
  keepOriginalAudio: boolean;
  fileName: string | null;
  videoStoragePath: string | null;
  audioStoragePath: string | null;
  captionsStoragePath: string | null;
  mimeType: string;
  sizeBytes: number;
  durationMs: number;
  width: number;
  height: number;
  jobId: string | null;
  error: { code?: string; message?: string } | null;
  downloadUrl: string | null;
  captionsUrl: string | null;
  corpusVersion: number;
  glossaryVersion: number;
  createdAt: string;
  updatedAt: string;
}

export interface LocalizationList {
  items: Localization[];
}

export interface LocalizationAccepted {
  localizationId: string;
  jobId: string;
  status: string;
}

export interface GlossaryTerm {
  source: string;
  target: string;
  /** Short target-language code (`hi`). Empty means the term applies to any target. */
  targetLanguage: string;
}

export interface Glossary {
  projectId: string;
  sourceLanguage: string;
  terms: GlossaryTerm[];
  version: number;
  updatedAt: string | null;
}

export interface GlossaryUpdate {
  sourceLanguage?: string;
  terms: GlossaryTerm[];
  expectedVersion?: number | null;
}

export interface CorpusLanguagePair {
  sourceLanguage: string;
  targetLanguage: string;
}

/** The bundled global corpus: its version and the pairs it covers. */
export interface GlobalCorpus {
  version: number;
  pairs: CorpusLanguagePair[];
}

/* ------------------------------------------------------------------ connections */

export type ConnectionPlatform = "youtube" | "medium" | "substack" | "reddit";

export type ConnectionStatus =
  | "pending"
  | "connected"
  | "needs_reauth"
  | "revoked"
  | "error";

export interface Connection {
  connectionId: string;
  platform: ConnectionPlatform;
  accountType: string;
  displayName: string;
  externalAccountId: string;
  externalHandle: string | null;
  uploadsPlaylistId: string | null;
  googleAccountEmail: string | null;
  avatarUrl: string | null;
  profileUrl: string | null;
  subscriberCount: number | null;
  videoCount: number | null;
  status: ConnectionStatus;
  scopes: string[];
  lastSyncAt: string | null;
  lastSyncStatus: string | null;
  lastErrorCode: string | null;
  contentSyncedAt: string | null;
  contentItemCount: number | null;
  createdAt: string;
  updatedAt: string;
}

export interface ConnectionList {
  items: Connection[];
}

export interface OAuthStartRequest {
  loginHint?: string | null;
  redirectPath?: string | null;
}

export interface OAuthStartResponse {
  authorizationUrl: string;
  state: string;
}

export type CrosspostPlatform = "medium" | "substack" | "reddit";

export interface CrosspostInput {
  platform: CrosspostPlatform;
  connectionId: string;
  title: string;
  body: string;
  options?: Record<string, unknown>;
}

export interface CrosspostResult {
  platform: string;
  connectionId: string;
  externalId: string;
  url: string;
  status: "draft" | "published" | "scheduled";
  title: string;
}

export interface SyncCrosspostInput {
  platform: CrosspostPlatform;
  title: string;
  body: string;
}

export interface LinkedExternalPost {
  platform: string;
  connectionId: string;
  externalId: string;
  url: string | null;
  status: string;
  updatedAt: string | null;
}

export interface ContentItem {
  videoId: string;
  title: string;
  description: string;
  tags: string[];
  publishedAt: string | null;
  durationSeconds: number | null;
  viewCount: number | null;
  likeCount: number | null;
  commentCount: number | null;
  thumbnailUrl: string | null;
  hasCustomThumbnail: boolean | null;
  language: string | null;
}

export interface ContentStyleSummary {
  videoCount: number;
  avgTitleWords: number;
  titleWithNumberPct: number;
  titleWithEmojiPct: number;
  avgDescriptionChars: number;
  descriptionWithHashtagPct: number;
  videosPerMonth: number;
  commonTitleOpeners: string[];
  topTags: string[];
}

export interface ChannelContentProfile {
  connectionId: string;
  syncedAt: string | null;
  itemCount: number;
  style: ContentStyleSummary;
  topVideos: ContentItem[];
  recentItems: ContentItem[];
}

export interface MetricValue {
  metric: string;
  value: number;
}

export interface BreakdownRow {
  label: string;
  value: number;
}

export interface AudienceBreakdown {
  dimension: string;
  rows: BreakdownRow[];
}

export interface AudienceProfile {
  connectionId: string;
  syncedAt: string | null;
  periodDays: number;
  summary: MetricValue[];
  demographics: AudienceBreakdown | null;
  trafficSources: AudienceBreakdown | null;
  topCountries: AudienceBreakdown | null;
  topVideos: ContentItem[];
}

export interface CreatorContextExample {
  videoId: string;
  title: string;
  tags: string[];
  viewCount: number | null;
  likeCount: number | null;
  commentCount: number | null;
  publishedAt: string | null;
  thumbnailUrl: string | null;
  transcriptExcerpt: string | null;
}

export interface CreatorContextAudience {
  periodDays: number;
  summary: MetricValue[];
  demographics: AudienceBreakdown | null;
  trafficSources: AudienceBreakdown | null;
}

export interface CreatorContext {
  available: boolean;
  sourceType: "youtube" | "folder_import";
  creatorName: string | null;
  creatorBio: string | null;
  writtenExamples: CreatorWrittenExample[];
  generatedAt: string | null;
  connectionId: string | null;
  connectionDisplayName: string | null;
  style: ContentStyleSummary | null;
  examples: CreatorContextExample[];
  audience: CreatorContextAudience | null;
}

export interface CreatorWrittenExample {
  itemId: string;
  title: string;
  url: string | null;
  excerpt: string;
}

/* ------------------------------------------------------------------ publishing */

export type PublishSourceKind = "source" | "captionRender" | "localization";

export interface PublishVideoSource {
  kind: PublishSourceKind;
  id: string | null;
}

export type PublishCaptionFormat = "srt" | "vtt" | "none";
export type PublishVisibility = "private" | "unlisted" | "public";

export type PublishStatus =
  | "queued"
  | "uploading"
  | "processing"
  | "published"
  | "failed"
  | "deleted";

export interface PublishThumbnailRef {
  thumbnailId: string;
  version?: number | null;
}

export interface PublishRequest {
  connectionId: string;
  video?: PublishVideoSource;
  title: string;
  description?: string;
  tags?: string[];
  categoryId?: string;
  privacyStatus?: PublishVisibility;
  madeForKids?: boolean;
  notifySubscribers?: boolean;
  captionFormat?: PublishCaptionFormat;
  captionLanguage?: string;
  captionName?: string;
  thumbnail?: PublishThumbnailRef | null;
  publishAt?: string | null;
}

export type PublishWarningCode =
  | "THUMBNAIL_FORBIDDEN"
  | "THUMBNAIL_MISSING"
  | "THUMBNAIL_FAILED"
  | "CAPTIONS_SKIPPED"
  | "CAPTIONS_FAILED";

/** A non-fatal publish outcome: the video is up but the thumbnail/captions are not. */
export interface PublishWarning {
  code: PublishWarningCode;
  message: string;
  step: "thumbnail" | "captions";
}

export interface Publish {
  publishId: string;
  projectId: string;
  connectionId: string;
  connectionDisplayName: string | null;
  platform: string;
  status: PublishStatus;
  video: PublishVideoSource;
  title: string;
  description: string;
  tags: string[];
  categoryId: string;
  privacyStatus: PublishVisibility;
  madeForKids: boolean;
  notifySubscribers: boolean;
  captionFormat: PublishCaptionFormat;
  captionLanguage: string;
  captionName: string;
  thumbnailId: string | null;
  thumbnailVersion: number | null;
  youtubeVideoId: string | null;
  youtubeUrl: string | null;
  uploadProgress: number;
  steps: string[];
  warnings: PublishWarning[];
  jobId: string | null;
  /** Go-public time; rescheduling a linked calendar slot moves it. */
  publishAt: string | null;
  error: { code?: string; message?: string } | null;
  createdAt: string;
  updatedAt: string;
}

export interface PublishList {
  items: Publish[];
}

export interface PublishAccepted {
  publishId: string;
  jobId: string;
  status: string;
}

/* ------------------------------------------------------------------ scheduling */

export type ScheduleStatus =
  | "planned"
  | "scheduled"
  | "published"
  | "failed"
  | "cancelled";

export interface Schedule {
  scheduleId: string;
  projectId: string;
  /** Snapshot of the project name at create time, so the calendar renders without a join. */
  projectName: string | null;
  title: string;
  notes: string;
  platform: string;
  scheduledAt: string;
  status: ScheduleStatus;
  /** Why a planned/failed slot is not uploading; null while on track. */
  statusDetail: string | null;
  /** Link to a publish attempt; rescheduling also moves the publish's `publishAt`. */
  publishId: string | null;
  connectionId: string | null;
  connectionDisplayName: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ScheduleCreateInput {
  title: string;
  notes?: string;
  platform?: string;
  scheduledAt: string;
  publishId?: string | null;
  connectionId?: string | null;
}

export interface ScheduleUpdateInput {
  title?: string;
  notes?: string;
  platform?: string;
  scheduledAt?: string;
  publishId?: string | null;
  connectionId?: string | null;
}

export interface ScheduleList {
  items: Schedule[];
}

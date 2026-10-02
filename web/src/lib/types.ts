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
  /** `video` runs the upload pipeline; `draft` opens the writing studio. */
  kind: ProjectKind;
  draftFormat: DraftFormat;
  /** Denormalised draft stats for cards; null for video projects. */
  draftSummary: DraftSummary | null;
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
  draftFormat?: DraftFormat;
  draftBrief?: DraftBrief;
}

export interface ProjectList {
  items: Project[];
  nextPageToken: string | null;
}

// ----------------------------------------------------------------------- draft

export type DraftBlockType = "heading" | "paragraph" | "scene";
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

export interface Draft {
  projectId: string;
  title: string;
  status: DraftStatus;
  brief: DraftBrief;
  blocks: DraftBlock[];
  messages: DraftMessage[];
  error: string | null;
  summary: DraftSummary;
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

/** The first six dimensions always run; the rest are opt-in. */
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

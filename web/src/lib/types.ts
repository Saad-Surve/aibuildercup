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

export interface Project {
  projectId: string;
  name: string;
  description: string;
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
  createdAt: string;
  updatedAt: string;
}

export interface CreateProjectInput {
  name: string;
  description?: string;
  primaryLanguage?: string;
  targetLanguages?: string[];
  targetPlatforms?: string[];
}

export interface ProjectList {
  items: Project[];
  nextPageToken: string | null;
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
  createdAt: string;
  updatedAt: string;
}

export interface AssetList {
  items: Asset[];
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
}

export interface Transcript {
  transcriptId: string;
  language: string;
  durationMs: number;
  segments: TranscriptSegment[];
}

export const ANALYSIS_DIMENSIONS = [
  "truth_evidence",
  "clarity",
  "structure_pacing",
  "legal_safety",
  "cultural_localization",
  "platform_fit",
  "audience_fit",
  "brand_voice",
  "engagement_retention",
  "emotional_impact",
  "seo_discoverability",
  "visual_accessibility",
  "conversion_cta",
] as const;

export type AnalysisDimension = (typeof ANALYSIS_DIMENSIONS)[number];

/** The first six dimensions always run; the rest are opt-in. */
export const CORE_DIMENSIONS: AnalysisDimension[] = [
  "truth_evidence",
  "clarity",
  "structure_pacing",
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

export interface ReviewerRun {
  reviewerRunId: string;
  dimension: AnalysisDimension;
  status: ReviewerRunStatus;
  findingCount: number;
  costEstimateUsd: number;
  durationMs: number;
  model: string | null;
  inputSegmentCount: number;
  tokenUsage: TokenUsage;
  error: { code: string; message: string } | null;
  startedAt: string | null;
  finishedAt: string | null;
}

export interface FindingEvidence {
  quote: string;
  explanation: string;
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
  citations: Record<string, unknown>[];
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

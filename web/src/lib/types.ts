export interface Preferences {
  timezone: string;
  defaultLanguage: string;
}

export interface Me {
  uid: string;
  displayName: string | null;
  email: string | null;
  onboardingCompleted: boolean;
  personaVersion: number | null;
  preferences: Preferences;
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

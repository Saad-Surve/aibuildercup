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

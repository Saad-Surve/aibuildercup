export type StepId =
  | "welcome"
  | "import"
  | "identity"
  | "topics"
  | "audience"
  | "style"
  | "platforms"
  | "persona"
  | "connections"
  | "done";

export interface StepMeta {
  id: StepId;
  label: string;
  title: string;
  description: string;
}

/*
 * Onboarding is a real sequence, so numbering it is information, not decoration.
 * The rail shows where you are and what remains.
 */
export const ONBOARDING_STEPS: StepMeta[] = [
  {
    id: "welcome",
    label: "Welcome",
    title: "Let's set up your studio",
    description:
      "A few questions so the reviewers understand your voice, audience, and goals.",
  },
  {
    id: "import",
    label: "Research",
    title: "Start with your public profiles",
    description:
      "Add profile links to prefill your answers, or continue to tell us about yourself.",
  },
  {
    id: "identity",
    label: "You",
    title: "Who is the creator?",
    description: "The basics we use to address you and set defaults.",
  },
  {
    id: "topics",
    label: "Content",
    title: "What do you make?",
    description:
      "Topics and formats shape how structure and clarity are judged.",
  },
  {
    id: "audience",
    label: "Audience",
    title: "Who are you making it for?",
    description:
      "Reviewers score fit against the audience you actually have in mind.",
  },
  {
    id: "style",
    label: "Voice",
    title: "How should it sound?",
    description: "Tone and hook preferences tune the suggestions you'll get.",
  },
  {
    id: "platforms",
    label: "Platforms",
    title: "Where do you publish?",
    description: "Platform fit checks aspect, length, and policy expectations.",
  },
  {
    id: "persona",
    label: "Persona",
    title: "Your creator persona",
    description: "Generated from your answers. Edit anything that isn't right.",
  },
  {
    id: "connections",
    label: "Connections",
    title: "Connect your accounts",
    description:
      "Your persona is ready. Bring in your published work to help the studio learn your voice and visual style. You can also connect later in Settings.",
  },
  {
    id: "done",
    label: "Done",
    title: "You're all set",
    description: "Your studio is ready for its first project.",
  },
];

export interface OnboardingAnswers {
  creatorName?: string;
  location?: string;
  timezone?: string;
  primaryLanguage?: string;
  bio?: string;
  topics?: string[];
  contentFormats?: string[];
  typicalLength?: string;
  audience?: string;
  audienceLocation?: string;
  knowledgeLevel?: string;
  primaryGoal?: string;
  tone?: string[];
  wordsToAvoid?: string;
  hookStyle?: string;
  captionPreferences?: string;
  regionalPreferences?: string;
  platforms?: string[];
  /** Public profile links the creator gave for grounded research. */
  creatorLinks?: string[];
}

export const LANGUAGE_OPTIONS = [
  { value: "en", label: "English" },
  { value: "hi", label: "Hindi" },
  { value: "mr", label: "Marathi" },
  { value: "ta", label: "Tamil" },
  { value: "te", label: "Telugu" },
  { value: "bn", label: "Bengali" },
  { value: "es", label: "Spanish" },
];

/** Display name for a language code; falls back to the code when unknown. */
export function languageLabel(code: string | null | undefined): string {
  if (!code) return "Select language";
  return (
    LANGUAGE_OPTIONS.find((language) => language.value === code)?.label ?? code
  );
}

export const TIMEZONE_OPTIONS = [
  "Asia/Kolkata",
  "Asia/Dubai",
  "Asia/Singapore",
  "Europe/London",
  "Europe/Berlin",
  "America/New_York",
  "America/Los_Angeles",
  "UTC",
];

export const TOPIC_OPTIONS = [
  { value: "finance", label: "Finance" },
  { value: "career", label: "Career" },
  { value: "technology", label: "Technology" },
  { value: "education", label: "Education" },
  { value: "health_fitness", label: "Health & fitness" },
  { value: "lifestyle", label: "Lifestyle" },
  { value: "gaming", label: "Gaming" },
  { value: "travel", label: "Travel" },
  { value: "food", label: "Food" },
  { value: "business", label: "Business" },
  { value: "culture", label: "Culture" },
  { value: "entertainment", label: "Entertainment" },
];

export const FORMAT_OPTIONS = [
  { value: "talking_head", label: "Talking head" },
  { value: "tutorial", label: "Tutorial" },
  { value: "vlog", label: "Vlog" },
  { value: "interview", label: "Interview" },
  { value: "review", label: "Review" },
  { value: "listicle", label: "Listicle" },
  { value: "documentary", label: "Documentary" },
  { value: "shorts", label: "Shorts" },
];

export const LENGTH_OPTIONS = [
  { value: "under_5", label: "Under 5 min" },
  { value: "5_15", label: "5–15 min" },
  { value: "15_30", label: "15–30 min" },
  { value: "over_30", label: "Over 30 min" },
];

export const KNOWLEDGE_LEVELS = [
  { value: "beginner", label: "Beginners" },
  { value: "intermediate", label: "Some experience" },
  { value: "advanced", label: "Advanced" },
  { value: "mixed", label: "A mix" },
];

export const TONE_OPTIONS = [
  { value: "direct", label: "Direct" },
  { value: "friendly", label: "Friendly" },
  { value: "analytical", label: "Analytical" },
  { value: "motivational", label: "Motivational" },
  { value: "humorous", label: "Humorous" },
  { value: "calm", label: "Calm" },
  { value: "authoritative", label: "Authoritative" },
];

export const HOOK_STYLES = [
  { value: "question", label: "Open with a question" },
  { value: "bold_claim", label: "Open with a bold claim" },
  { value: "story", label: "Open with a story" },
  { value: "statistic", label: "Open with a number" },
];

export const CAPTION_PREFERENCES = [
  { value: "minimal", label: "Minimal" },
  { value: "standard", label: "Standard" },
  { value: "verbose", label: "Verbose" },
];

export const PLATFORM_OPTIONS = [
  { value: "youtube", label: "YouTube" },
  { value: "youtube_shorts", label: "YouTube Shorts" },
  { value: "instagram", label: "Instagram" },
  { value: "facebook", label: "Facebook" },
  { value: "linkedin", label: "LinkedIn" },
  { value: "tiktok", label: "TikTok" },
  { value: "x", label: "X" },
];

const STEP_KEYS: Record<StepId, (keyof OnboardingAnswers)[]> = {
  welcome: [],
  import: ["creatorLinks"],
  identity: ["creatorName", "location", "timezone", "primaryLanguage", "bio"],
  topics: ["topics", "contentFormats", "typicalLength"],
  audience: ["audience", "audienceLocation", "knowledgeLevel", "primaryGoal"],
  style: [
    "tone",
    "wordsToAvoid",
    "hookStyle",
    "captionPreferences",
    "regionalPreferences",
  ],
  platforms: ["platforms"],
  persona: [],
  connections: [],
  done: [],
};

export function answersForStep(
  step: StepId,
  answers: OnboardingAnswers,
): Partial<OnboardingAnswers> {
  const slice: Partial<OnboardingAnswers> = {};
  for (const key of STEP_KEYS[step]) {
    const value = answers[key];
    if (value !== undefined) {
      (slice as Record<string, unknown>)[key] = value;
    }
  }
  return slice;
}

export function stepIsComplete(
  step: StepId,
  answers: OnboardingAnswers,
): boolean {
  if (step === "identity") {
    return Boolean(answers.creatorName?.trim());
  }
  return true;
}

/** Split a textarea of profile links into a clean, de-duplicated list. */
export function parseProfileLinks(text: string): string[] {
  const links: string[] = [];
  for (const part of text.split(/[\n,\s]+/)) {
    const value = part.trim();
    if (value && !links.includes(value)) links.push(value);
  }
  return links;
}

const RESEARCH_KEYS: (keyof OnboardingAnswers)[] = [
  "creatorName",
  "location",
  "primaryLanguage",
  "bio",
  "topics",
  "contentFormats",
  "typicalLength",
  "audience",
  "audienceLocation",
  "knowledgeLevel",
  "primaryGoal",
  "tone",
  "wordsToAvoid",
  "hookStyle",
  "captionPreferences",
  "regionalPreferences",
  "platforms",
];

/**
 * Merge grounded research into the current answers without clobbering anything the creator
 * already typed. Returns the merged answers and the keys research actually filled.
 */
export function mergeResearchAnswers(
  current: OnboardingAnswers,
  researched: Record<string, unknown>,
): { answers: OnboardingAnswers; filled: (keyof OnboardingAnswers)[] } {
  const merged: Record<string, unknown> = { ...current };
  const filled: (keyof OnboardingAnswers)[] = [];
  for (const key of RESEARCH_KEYS) {
    const next = researched[key];
    if (next === undefined || next === null) continue;
    const existing = current[key];
    const isEmpty =
      existing === undefined ||
      existing === null ||
      (Array.isArray(existing) && existing.length === 0) ||
      (typeof existing === "string" && !existing.trim());
    if (isEmpty) {
      merged[key] = next;
      filled.push(key);
    }
  }
  return { answers: merged as OnboardingAnswers, filled };
}

const LANGUAGE_FALLBACKS: Record<string, string> = {
  ar: "Arabic",
  bn: "Bengali",
  de: "German",
  en: "English",
  es: "Spanish",
  fil: "Filipino",
  fr: "French",
  gu: "Gujarati",
  hi: "Hindi",
  id: "Indonesian",
  ja: "Japanese",
  kn: "Kannada",
  ko: "Korean",
  ml: "Malayalam",
  mr: "Marathi",
  ms: "Malay",
  pa: "Punjabi",
  pt: "Portuguese",
  ta: "Tamil",
  te: "Telugu",
  th: "Thai",
  ur: "Urdu",
  vi: "Vietnamese",
  yue: "Cantonese",
  zh: "Chinese",
};

let englishLanguageNames: Intl.DisplayNames | null | undefined;

function displayNames(): Intl.DisplayNames | null {
  if (englishLanguageNames !== undefined) return englishLanguageNames;

  try {
    englishLanguageNames = new Intl.DisplayNames(["en"], {
      type: "language",
    });
  } catch {
    englishLanguageNames = null;
  }

  return englishLanguageNames;
}

/** Return an English display name without changing the language code sent to APIs. */
export function languageLabel(code: string | null | undefined): string {
  const original = code?.trim();
  if (!original) return "Select language";

  const normalized = original.replaceAll("_", "-");
  const base = normalized.split("-", 1)[0]?.toLowerCase() ?? normalized;
  // `ja` is the ISO 639 language code. Treat the common country-code mix-up
  // as a display alias only so persisted and backend-facing values stay intact.
  const displayCode = base === "jp" ? "ja" : normalized;

  try {
    const label = displayNames()?.of(displayCode);
    if (label && label.toLowerCase() !== displayCode.toLowerCase())
      return label;
  } catch {
    // Fall through for malformed or unsupported language tags.
  }

  return LANGUAGE_FALLBACKS[base === "jp" ? "ja" : base] ?? original;
}

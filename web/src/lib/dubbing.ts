import { apiFetch } from "@/lib/api-client";
import type {
  GlobalCorpus,
  Glossary,
  GlossaryUpdate,
  LocalizationAccepted,
  LocalizationList,
  LocalizationVoiceList,
} from "@/lib/types";

/** The bundled global corpus: version and the language pairs it covers. */
export function getGlobalCorpus(): Promise<GlobalCorpus> {
  return apiFetch<GlobalCorpus>("/glossaries");
}

/** The project's own terminology, applied during the adaptation pass. */
export function getGlossary(projectId: string): Promise<Glossary> {
  return apiFetch<Glossary>(`/projects/${projectId}/glossary`);
}

export function putGlossary(
  projectId: string,
  input: GlossaryUpdate,
): Promise<Glossary> {
  return apiFetch<Glossary>(`/projects/${projectId}/glossary`, {
    method: "PUT",
    body: JSON.stringify(input),
  });
}

/** Languages and voices the dubbing pipeline supports. */
export function listLocalizationVoices(): Promise<LocalizationVoiceList> {
  return apiFetch<LocalizationVoiceList>("/localization-voices");
}

export function listLocalizations(projectId: string): Promise<LocalizationList> {
  return apiFetch<LocalizationList>(`/projects/${projectId}/localizations`);
}

export function createLocalization(
  projectId: string,
  input: {
    targetLanguage: string;
    voice?: string | null;
    transcriptVersion?: number | null;
    keepOriginalAudio?: boolean;
    fileName?: string | null;
  },
): Promise<LocalizationAccepted> {
  return apiFetch<LocalizationAccepted>(
    `/projects/${projectId}/localizations`,
    { method: "POST", body: JSON.stringify(input) },
  );
}

export function deleteLocalization(
  projectId: string,
  localizationId: string,
): Promise<void> {
  return apiFetch<void>(
    `/projects/${projectId}/localizations/${localizationId}`,
    { method: "DELETE" },
  );
}

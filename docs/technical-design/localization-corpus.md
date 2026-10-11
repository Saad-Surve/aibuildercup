# Resonance localization corpus

Localization is a two-stage pipeline: Cloud Translation produces a literal draft, then
Gemini adapts terms, idioms, code-mixed speech and cultural references. A versioned corpus
and project glossary supply constraints. Translation-quality gains are not measured yet.

## Current data

The runtime bundle is **`backend/app/assets/corpus/global.json`**, loaded by
`services/localization_corpus.py`. It provides terminology and pair-specific/universal
trap handling. Curated pairs are English→Hindi, English→Spanish and English→French.
The voice catalog covers 25 languages; that does not imply equal glossary coverage.

A project-owned glossary lives at `users/{uid}/projects/{projectId}/glossary/main`.
Terms may apply to all targets or one language. Updates increment a version and optionally
check `expectedVersion` to reject a stale edit. A localization snapshots applicable terms
and stores `corpusVersion`/`glossaryVersion`, preventing later glossary edits from changing
in-flight work.

## Runtime

```text
versioned source transcript
  → Cloud Translation Advanced, preserving segment count
  → Gemini adaptation with source, translation, corpus and glossary snapshot
  → localized caption export
  → bounded per-segment Text-to-Speech
  → tempo normalization, padding/trimming and timeline assembly
  → FFmpeg audio/video output
```

The adaptation prompt preserves names, numerical meaning and source intent; units/currency
must not be converted by simply replacing a currency symbol. Translation does not currently
register/use native Cloud Translation glossaries (`glossary_id` is not wired); constraints
are applied in the Gemini pass. If a batch's adaptation fails or returns an invalid line
count, the machine translation draft survives. Missing pair-specific data still allows
translation/adaptation with universal traps.

TTS permits four concurrent requests by default. Voice assignment is per speaker; synthesized
speech is adjusted to the original window, with tempo clamping and padding/trimming as needed.
The user can keep quiet source audio under the dub. Output is timed synthesized narration,
not voice cloning/lip sync. Model/provider errors and shortened speech can affect quality.

## Data lifecycle and expansion

The bundled global corpus is platform data; project glossary/localized artifacts are owned
and covered by project deletion of current records/objects. Noncurrent Storage versions have
separate lifecycle retention. BigQuery/GCS TSV ingestion and native Translation glossary
registration are future work, not current runtime dependencies.

Indic glossaries and parallel corpora are possible expansion sources. Their proposed use
is not evidence they were ingested or that the shipped bundle has benchmarked native-speaker
quality. Check licenses/provenance before importing external material.

[Evaluation methodology](../../evals/README.md) specifies term preservation, native-speaker
meaning/voice ratings, mistranslation counts and clipping/timing measurements. Compare literal
translation against adaptation on identical source segments; record language, model and corpus
version, and retain negative cases. Do not infer improvement from the existence of a second pass.

# Localization Corpus

Terminology and "trap list" data that makes translation better than a raw machine-translate call.
Full design in `../docs/technical-design/localization-corpus.md`.

```text
corpus/
└── global/
    ├── {sourceLang}-{targetLang}/v{n}.tsv      term pairs
    └── trap-list/{sourceLang}-{targetLang}/v{n}.tsv
```

## Primary source for the MVP

AI4Bharat Indic-Glossaries (General, Legal, Education, Healthcare, Automobile, News) across
Indian languages. Ingest as TSV, register as a Cloud Translation Advanced glossary, and keep the
Gemini pass for idioms, brands, code-mixed phrases, units, and honorifics.

Do not commit large corpora blindly — check the license and size first. Small, reviewed files
only.

## MVP bundle

The backend container's build context is `backend/`, so the corpus the runtime reads ships
inside the image at `backend/app/assets/corpus/global.json` (glossary term pairs by language
pair, plus the trap list and a `version`). That is the source of truth for the localization
adaptation pass today. The GCS path above and the BigQuery tables in the design are the
intended ingestion target and remain a follow-up; when they land, the loader in
`backend/app/services/localization_corpus.py` is the one place to change.

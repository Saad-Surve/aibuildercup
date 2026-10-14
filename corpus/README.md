# Localization corpus

The runtime reads `backend/app/assets/corpus/global.json`, bundled in the backend image.
It contains versioned terminology and known translation traps for English→Hindi,
English→Spanish and English→French, plus universal handling rules.

Project glossaries are editable owned data, snapshotted onto each localization. Cloud
Translation produces the first draft; Gemini applies the snapshotted corpus/glossary constraints and
cultural adaptation. Native Translation glossary registration and GCS/BigQuery corpus
loading are not wired into the current pipeline; Terraform defines no BigQuery datasets.

The 25-language TTS catalog is separate from curated glossary coverage. No native-speaker
quality improvement is claimed without evaluation. [Implementation](../docs/technical-design/localization-corpus.md),
[evaluation methods](../evals/README.md) and [costs](../docs/costs.md) describe the actual path.

Future corpus ingestion can use reviewed, appropriately licensed Indic glossaries or
parallel examples. Preserve source/license/version metadata; do not describe proposed
external corpora as already ingested or commit large data blindly.

# Fixtures

`media/` and `seed/` are gitignored local originals. A fresh checkout does not include the
existing workstation videos. Preserve those files; use normal upload/transcription for
bounded live validation. Do not commit third-party media or private transcripts blindly.

| Tracked path | Purpose |
|---|---|
| `creator-import-example/` | Small manifest, subtitle and writing example for validating a supplied creator folder |
| `creator-sources/arun-prabhudesai.json` | Public-source collection configuration and explicitly supplied persona preferences |

[Creator import](../docs/creator-demo-import.md) and
[public corpus](../docs/creator-public-corpus.md) explain preparation/provenance.
The public demo uses copied real workspace data; no generic `backend/scripts/seed.py`
exists. [Evaluation cases/results](../evals/README.md) are separate from source originals
and carry their own hashes, labels and measurement scope.

# Creator Helper Studio — Localization Corpus Design

This is a differentiator, not just a translate call. Generic machine translation mangles
idioms, brand names, code-mixed Hinglish, and culture-specific references. We improve on that
with a versioned terminology corpus plus a Gemini adaptation pass.

Scope note: we are **not** training a translation model. We build a curated terminology and
"known trap" corpus and use it to constrain and correct translation at runtime.

## 1. Two levels

| Level | Owner | Scope | Example |
|---|---|---|---|
| Global corpus | platform | all users | "credit score" -> "क्रेडिट स्कोर", brand names kept in Latin script |
| Project glossary | user | one project | the creator's own terms, product names, catchphrases |

Both are versioned. A localization artifact records `corpusVersion` and `glossaryVersion` so a
result is reproducible and reviewable.

## 2. Global corpus sources

Seed the MVP corpus from open, permissively licensed resources:

- **AI4Bharat Indic-Glossaries** — domain glossaries (General, Legal, Education, Healthcare,
  Automobile, News) across Indian languages. Cleanest fit for the MVP: it is a glossary, not a
  raw parallel dump.
- **Samanantar / BHASHIK (BPCC)** — large English-Indic parallel corpora, used to mine candidate
  term pairs and flag frequent mistranslations.
- **IIT Bombay English-Hindi parallel corpus** and **PMIndia** — additional English-Hindi/Marathi
  term coverage.
- **OPUS** — broad, convenient public parallel data.
- **PHINC / IIIT-H code-mixed corpora** — specifically for Hinglish, which generic MT handles
  badly and which creators use constantly.

For the hackathon, ingest the AI4Bharat glossaries as the primary global corpus and add a
hand-curated trap list. The larger parallel corpora are a stretch source for mining.

## 3. The "trap list" (hand-curated)

The part that makes the demo land. A small reviewed TSV of things generic MT gets wrong:

```text
category          source (en)                  recommended (hi)
idiom             "break a leg"                 "शुभकामनाएं"  (not literal)
brand             "YouTube", "Instagram"        keep Latin script for brand names
false_friend      "gift" vs German "Gift"       context check
code_mix          "thoda buffer do"             preserve code-mixed intent
unit_currency     "$1,299"                       "₹1,299" with local formatting
date_format       "10/12/2026"                  localized as DD/MM
name_honorific    "sir", "ji"                    honorific handling
```

## 4. Storage

```text
GCS:  corpus/global/{sourceLang}-{targetLang}/v{n}.tsv
      corpus/trap-list/{sourceLang}-{targetLang}/v{n}.tsv
      users/{uid}/corpus/{projectId}/glossary-v{n}.tsv
BQ:   creator_studio_ai.glossary_terms        (term, source_lang, target_lang, category, version)
      creator_studio_ai.translation_traps     (category, source, recommended, notes, version)
```

Firestore stores only references and versions (`glossaries/{glossaryId}`, `localizations.corpusVersion`).

## 5. Runtime pipeline

```text
source transcript
  -> segment into translatable units
  -> retrieve corpus + trap entries that match this segment
  -> Cloud Translation Advanced with glossary (term enforcement)
  -> Gemini cultural-adaptation pass:
       input = source + draft translation + retrieved corpus/trap entries
       fix idioms, brands, code-mixed phrases, units, honorifics
  -> produce localized VTT / SRT
  -> Text-to-Speech for dubbing
  -> FFmpeg mux with duration normalization
```

## 6. Cloud Translation glossary

The global and project glossaries are uploaded as TSV and registered as Cloud Translation
Advanced glossaries, so term enforcement happens even before the Gemini pass. Gemini then only
has to fix the things a glossary cannot express (idiom, tone, culture).

## 7. Versioning rules

- Corpus and trap-list changes create a new version; old versions stay for reproducibility.
- A localization never mixes versions.
- The localization comparison UI shows source vs localized captions side by side and lets the
  user flag a wrong phrase, which feeds a candidate corpus entry for review.

## 8. Fallback

If no corpus exists for a language pair, the pipeline degrades gracefully to
`Translate -> Gemini adaptation` with an empty corpus and warns the user that quality may vary.

## 9. Acceptance

- The `regional` demo scenario produces visibly better Hindi output with the corpus than without.
- Every localization records its corpus and glossary versions.
- The user can flag a bad phrase and see it become a candidate corpus entry.

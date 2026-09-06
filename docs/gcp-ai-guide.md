# GCP + Google Cloud AI — Hackathon Playbook (Sept 2026)

> Purpose: single reference for building a **functional GenAI prototype deployed on Cloud Run / GCP / Firebase** that maximizes the judging rubric: Technical Merit & GenAI (40%), Problem Alignment & Impact (25%), Innovation (25%), UX & Design (10%).
> All info validated via web search Sept 2026. Product formerly called **Vertex AI is now Gemini Enterprise Agent Platform**. Use that name in your deck — judges notice.

Source docs in this repo:
- `./requirements.md` — must deploy on Cloud Run/GCP/Firebase + 3-min demo video
- `./problem-statements.md` — 6 themes: BFSI, Retail & Commerce, Manufacturing, Media/Content, Future of Work, Sustainability & Social Impact
- `./judging-criteria.md` — 40/25/25/10 split

---

## 1. TL;DR — Recommended Hackathon Stack

For speed + judging points, pick this:

```
Frontend: Firebase Hosting + Firebase Auth + Firestore
  └─ rewrites → Cloud Run service (backend + AI)

Backend (Cloud Run, scale-to-zero):
  ├─ Python FastAPI OR Node.js + Genkit OR Agent Development Kit (ADK)
  ├─ Gemini 3.5 Flash (stable, cheap, long support) as default
  ├─ Gemini 3.8 Flash (newest, most intelligent Flash) for agentic demo wow-factor
  ├─ Gemini Embedding 2 (multimodal) + Vector Search OR BigQuery Vector Search for RAG
  ├─ Imagen 4 Fast / Nano Banana 2 (Gemini 3.1 Flash Image) for images
  ├─ Veo 3.1 Fast/Lite for video (only if Media theme)
  └─ Cloud Storage + Firestore + BigQuery for data

Agent path (big innovation points):
  ADK (Python/TS/Go/Java) → Agent Engine (managed runtime, sessions, memory)
  + Vertex AI Search for grounding + Model Armor for safety

Observability: Genkit Dev UI + Firebase AI Logic monitoring dashboard + Cloud Logging/Trace
```

Why this wins:
1. Satisfies hard requirement: Cloud Run + Firebase = GCP deployment.
2. `gemini-3.5-flash` is stable until ≥2027-05-19, `gemini-3.1-flash-lite` until 2027-05-07. Avoid `gemini-2.5-pro/flash` — they retire **Oct 20, 2026** (during judging).
3. ADK + Agent Engine + RAG + multimodal = checks all 40% technical boxes without building infra.

---

## 2. Core GenAI Platform

### 2.1 Gemini Enterprise Agent Platform (ex-Vertex AI)

- What it is: unified control plane for 200+ Google, third-party (Anthropic Claude family), and open models (Gemma, Llama, Mistral) via **Model Garden**, plus build/scale/govern/optimize tooling.
- Console: `console.cloud.google.com/agent-platform/model-garden`
- Key services under it:
  - Model Garden + Generative AI APIs (Gemini, Imagen, Veo, Chirp)
  - Agent Builder: Agent Studio (no-code prototype) → ADK (code) → Agent Engine (runtime) → Agent Gateway/Identity + Model Armor (governance)
  - Vector Search, Vertex AI Search (managed RAG/search), Pipelines, Feature Store, Evals, Grounding
- Docs: `cloud.google.com/products/gemini-enterprise-agent-platform`, `docs.cloud.google.com/gemini-enterprise-agent-platform/`

### 2.2 Gemini Models — What to Use Now (Sept 2026)

Stable family is **Gemini 3.x**. Preview = demo-only, can break.

| Model ID | Status / Date | Best for | Notes |
|---|---|---|---|
| `gemini-3.8-flash` | Stable, newest | Long-horizon SWE agents, autonomous agents, complex enterprise workflows | Most intelligent Flash. Promo pricing through Dec 31 2026. Use for hero demo. |
| `gemini-3.7-flash` | Stable 2026-08-13 | Complex coding, multi-step agents | Short-term availability model — pin version (`gemini-3.7-flash-001` style) |
| `gemini-3.6-flash` | Stable 2026-07-21 | Balanced speed + multimodal | Good fallback |
| `gemini-3.5-flash` | Stable 2026-05-19, supported to ≥2027-05-19 | **Default for prototype**: general chat, RAG, function calling, vision+audio | Best longevity guarantee. Use this in code. |
| `gemini-3.5-flash-lite` | Stable, to 2027-07-21 | High-throughput, cheap classification, rerank, preprocessing | $0.30/1M in, $0.03 cached |
| `gemini-3.1-flash-lite` | Stable 2026-05-07 | Cheapest multimodal ($0.25/1M in) | Upgrade path from retired 2.0 Flash |
| `gemini-2.5-pro / flash / lite` | Stable but **retire Oct 20 2026** | Do NOT use for new work | Migrate to 3.5 Flash / 3.1 Flash-Lite |
| `gemini-3.1-pro` | Preview | Deep reasoning, vibe-coding | Expect change; don't ship on it |
| `gemini-embedding-001` | Stable | Text search, classification, classic RAG |  |
| `gemini-embedding-2` (preview) | Preview | **Multimodal embeddings**: text+image+video+audio+PDF in one space | Best for Retail/Manufacturing multimodal search |
| `gemini-3.5-transcribe` | Stable | Low-latency STT + diarization + word timestamps + language detection | Replaces old Chirp paths for many uses |
| `gemini-3.1-flash-live`, `gemini-3.5-live-translate` (70+ langs) | Preview/New | Realtime voice, speech-to-speech translation | Great for Accessibility / Future of Work demos |
| `gemini-3.1-flash-tts`, `gemini-2.5-flash/pro-tts` | Preview/Stable | Controllable TTS |  |
| `deep-research-preview-04-2026`, `antigravity-preview-05-2026` | Preview agent models | Auto-research reports, sandboxed code+web agent | Call via API if you need deep-research feature |

Capabilities to highlight in deck:
- 1M+ token context (long docs, video, repo), native tool/function calling, JSON mode, image+video+audio in/out, thinking budget (`thinkingConfig`), cached inputs (10x cheaper), batch/flex (50% cheaper async), provisioned/priority throughput.
- Firebase AI Logic exposes same model IDs (`gemini-3.7-flash`, `gemini-3.5-flash`, etc.) client-side.

Pricing (Global endpoint, Sept 2026, USD — check `cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing` before deck):
- 3.5 Flash: $1.50 in / ~$6-9 out per 1M; cached $0.15; Batch/Flex $0.75 in.
- 3.5 Flash-Lite: $0.30 in; Batch $0.15 in.
- 3.1 Flash-Lite: $0.25 in.
- 3.8/3.7/3.6 Flash promo: $0.75 in / $0.075 cached through Dec 31 2026.
- Grounding with your data: ~$2.50 / 1k prompts; Maps grounding extra.

Rule: default to `gemini-3.5-flash` + Batch for bulk + Context Caching for repeated system prompts. Use `3.8-flash` only for live agentic wow moment.

### 2.3 Model Garden + Open Models

- First-party: Gemini, Imagen, Veo, Chirp, Nano Banana image models.
- Open: Gemma 3 / Gemma 4 (announced as 2.5 Flash-Lite replacement path), CodeGemma, PaliGemma, Llama, Mistral, Falcon, BERT/T5/ViT.
- Why it matters: you can claim data-sovereignty / on-prem story (Gemma on Cloud Run GPUs) + mix Claude via Model Garden if needed.
- API: `googleAI.model('gemini-2.5-flash...')` in Genkit, `ai.google.dev/gemini-api/docs/models` for Gemini Developer API vs Vertex path.

### 2.4 Media Generation

| Task | Model (Sept 2026) | Price signal | When to use |
|---|---|---|---|
| Text-to-image fast/cheap | `Imagen 4 Fast` $0.02/img, `Imagen 3 Fast` $0.02 | Posters, thumbnails, Retail try-on mock | Cheapest, 2K clarity |
| Text-to-image quality | `Imagen 4` $0.04/img, `Imagen 4 Ultra` $0.06 | Marketing hero, Media theme |  |
| Native image gen/edit (multimodal reasoning) | `Nano Banana` (Gemini 2.5 Flash Image), `Nano Banana 2` (Gemini 3.1 Flash Image $60/1M img out), `Nano Banana 2 Lite` ($30/1M), `Nano Banana Pro` (Gemini 3 Pro Image $120/1M, 4K + text rendering) | Character consistency across 14 refs, precise edits, text-in-image | **Prefer Nano Banana 2 for hackathon** — understands prompt context better than Imagen |
| Video + audio | `Veo 3.1` $0.40/s with audio ($0.20 video-only) @720p/1080p, $0.60 4K; `Veo 3.1 Fast` $0.10-0.12; `Veo 3.1 Lite` $0.05-0.08; `Veo 2` $0.50 legacy | Cinematic clips, training videos | Use Fast/Lite for demo budget; full Veo 3.1 only for final render |
| New | `Gemini Omni Flash` | Conversational video gen/edit + keyframe interp + native audio | Watch — replaces Veo 3.1 in Gemini app flow |
| Upscale / Recontext / Try-On | Imagen Upscale to 2K/3K/4K $0.06, Product Recontext $0.12, Virtual Try-On $0.06 | Retail & Commerce killer demo |  |

Tip: image/video blows budget fast. Cache outputs in Cloud Storage, show Lite in live demo, link full-quality offline.

---

## 3. Agents — Highest Innovation Leverage

### 3.1 Agent Builder (4 pillars: Build / Scale / Govern / Optimize)

- **Build**: Agent Studio (no-code grounded chat) → **Agent Development Kit (ADK)** (code-first, open source, Python/TS/Go/Java) with supervisor + sub-agents graph orchestration, workflow agents for predictable pipelines, LiteLLM + Model Garden model flexibility, MCP + 100+ tools.
- **Scale**: **Agent Engine** — managed runtime for sessions, memory, scaling, deployment (`adk deploy` → Cloud Run / GKE). Handles multi-turn state you don't want to code.
- **Govern**: Agent Identity, Agent Gateway, **Model Armor** (prompt-injection / PII / jailbreak filtering), VPC-SC, audit logs.
- **Optimize**: Evals, tracing, AI monitoring dashboards (now cover both Genkit + Firebase AI Logic client SDKs).

Same ADK powers Google Agentspace + Customer Engagement Suite — say that in deck for credibility.

ADK vs Genkit:
- **ADK**: complex agents, multi-agent orchestration, memory/sessions, deployment to Agent Engine. Choose if theme needs autonomous workflow (BFSI fraud triage, Manufacturing ops copilot, Future of Work assistant).
- **Genkit**: server-side AI flows (prompt + tools + RAG + evals) in JS/Python/Go, great Dev UI, Firebase integration. Choose if you need quick RAG API + streaming + Firebase Studio prototyping.

You can use both: Genkit flows as ADK tools.

Starter:
```python
# ADK (Python) — same agent.py works for CLI, Web UI, API Server
from google.adk.agents import LlmAgent
agent = LlmAgent(
  model="gemini-3.5-flash",
  instruction="You are an ops copilot. Use tools before answering.",
  tools=[bigquery_tool, vector_search_tool],
)
```
```ts
// Genkit (TS)
import { genkit } from 'genkit';
import { googleAI } from '@genkit-ai/googleai';
const ai = genkit({ plugins: [googleAI()] });
const { text } = await ai.generate({
  model: googleAI.model('gemini-3.5-flash'),
  prompt: 'Hello, Gemini!',
});
```
Docs: `adk.dev`, `docs.cloud.google.com/gemini-enterprise-agent-platform/build/adk`, `genkit.dev`, `firebase.blog/posts/2025/05/building-ai-apps/`

### 3.2 Firebase AI Logic (client) + Firebase Studio

- Evolution of "Vertex AI in Firebase". Call Gemini directly from web/mobile/Unity **without backend** — pick **Gemini Developer API** (quick prototype, AI Studio key) or **Vertex AI Gemini API** (enterprise billing, VPC, quota).
- Unity SDK parity: `FirebaseAI.GetInstance(FirebaseAI.Backend.VertexAI()).GetGenerativeModel("gemini-3.5-flash")` — useful for Media/Accessibility games.
- Monitoring dashboard now covers client SDK traffic (token/latency/error) — screenshot for appendix.
- Firebase Studio: prompt-to-app with Genkit code view — fastest way to get clickable prototype, then export to Cloud Run.

Pattern for judging: client SDK for low-risk tasks (summarize, rewrite) + server (Genkit/ADK on Cloud Run) for privileged tools / PII / payments. Enforce App Check + Auth + Model Armor server-side.

---

## 4. RAG / Search / Grounding (solves hallucination objection)

| Option | What | Use when |
|---|---|---|
| **Vertex AI Search** (managed) | No-code data stores (GCS, BigQuery, Firestore, websites) + hybrid + grounded answers with citations | Fastest credible RAG; supports DIY RAG comparison video pattern |
| **Vector Search** | Managed ANN DB, billions of vectors, ms lookup, now hybrid search (preview) | You bring `gemini-embedding-2` embeddings; full control |
| **BigQuery Vector Search** | `VECTOR_SEARCH()` + `ML.GENERATE_EMBEDDING()` + BigQuery ML LLM (speech/vision/translation/DocAI) | Data already in BigQuery; Manufacturing/Sustainability analytics + Looker Agents |
| **Grounding with Google Search / Maps / your data** | `$2.50/1k` + Maps overage `$14/1k`; adds citations, fresh facts, places | BFSI compliance, Retail store/delivery, Sustainability geo claims |
| **Knowledge Catalog (ex-Dataplex) + BigQuery Graphs (GQL, billions of nodes) + Looker Agents → Gemini Enterprise** | Governed metrics + relationship reasoning for agents | Enterprise-readiness slide |

DIY RAG recipe (Cloud Run):
1. Chunk docs → `gemini-embedding-001` or `gemini-embedding-2` → Vector Search or pgvector/ AlloyDB.
2. Retrieve top-k + hybrid → feed to `gemini-3.5-flash` with citations instruction.
3. Eval with Vertex evals + genkit evals; log traces.

---

## 5. Prebuilt ML APIs (don't rebuild what Google ships)

All have generous Always-Free tiers — perfect for prototype budget slide.

| API | Free tier | Hack use |
|---|---|---|
| Cloud Vision | 1k units/mo | Defect detection (Manufacturing), shelf/OCR (Retail), accessibility alt-text |
| Speech-to-Text (incl. Chirp v2 + Gemini Transcribe) | 60 min/mo | Call-center, classroom, field-worker voice |
| Text-to-Speech (700+ voices, Studio/WaveNet/Neural2) | 4M chars Standard, 1M WaveNet | Accessibility reader, Media dubbing |
| Translation Basic/Advanced (100+ langs, glossaries, batch, doc format preserve) | 500k chars/mo each | BFSI multilingual, Education localization |
| Natural Language (entities/sentiment) | 5k units/mo | Review mining, risk signals |
| Video Intelligence | 1k min/mo | Content moderation, safety |
| Document AI (form/parser/splitter + BigQuery ML integration) | pay-per-page, samples in docs | BFSI KYC, invoices, Manufacturing SOPs |
| Dialogflow CX / Conversational Agents + Contact Center AI | per-request | Prebuilt voice/chat fallback if ADK is overkill |
| Recommendations AI / Retail Search | per-request | Retail personalization without training |

Code pattern: use client libs (`@google-cloud/vision`, `speech`, `translate`) from Cloud Run service account — no keys to leak.

---

## 6. Data, Backend & Deployment (hard requirement)

### 6.1 Cloud Run (primary deploy target)

- Fully managed serverless containers: scale-to-zero, HTTP + Jobs + GPUs.
- **Cloud Run GPUs**: host open LLMs (Llama 3.1, Mistral, Gemma 2) for inference when you need private/offline story. Tutorial: "Host LLMs with Cloud Run GPUs".
- Integrations: connect to Firebase Hosting for custom domain + CDN in one click (Preview path since 2023, now standard via `firebase.json` rewrites).
- Must-haves for submission: `Dockerfile` + `gcloud run deploy --allow-unauthenticated --region=us-central1 --min-instances=0`, Artifact Registry, Cloud Build trigger, Cloud Logging/Trace enabled, budget alert.

```json
// firebase.json — Firebase Hosting → Cloud Run rewrite
{ "hosting": { "rewrites": [{ "source": "**", "run": { "serviceId": "api", "region": "us-central1" } }] } }
```

### 6.2 Firebase

- Hosting: global CDN, SSL, Brotli, preview channels (`firebase hosting:channel:deploy`), GitHub integration, one-click rollback.
- Auth, Firestore, Cloud Storage (5GB free), Cloud Functions (2nd gen = Cloud Run under hood), App Hosting (Next.js/Angular SSR), Remote Config, Performance + Analytics.
- AI Logic monitoring + Genkit Dev UI give you latency/token dashboards for deck.

### 6.3 Data plane

- Firestore: sessions/chat history, user profiles (Agent Engine can also manage sessions — pick one).
- Cloud Storage: raw docs/images/video + generated media cache.
- BigQuery: analytics, vector search, ML.GENERATE_TEXT, Looker Studio dashboards for impact metrics. EdTech/Sustainability impact graphs impress judges.
- Pub/Sub + Cloud Workflows + Scheduler: async ingestion, batch embeddings, nightly evals.
- Knowledge Catalog / Dataplex: governance claim for BFSI/Manufacturing.

---

## 7. Security, Safety & Responsible AI (10% UX + enterprise trust)

- Model Armor: scan prompts/responses for injection, PII, toxicity before Gemini call — one line in Agent Gateway.
- IAM least-privilege service accounts per Cloud Run service; App Check + Firebase Auth on client; no API keys in APK/JS (use backend or Firebase AI Logic with restrictions).
- PII redaction: `redactPII` in scrape/parse paths, DLP API for docs.
- Data residency: pick Global vs non-Global endpoints deliberately (non-Global Gemini 3 pricing enforced from July 1 2026; Global cheaper).
- Evals + red-teaming: Vertex evals, Genkit evals, fairness indicators, model cards. Keep 1 slide: eval set size, pass rate, hallucination mitigation (grounding + citations).
- Accessibility: meet WCAG basics — keyboard, contrast, captions (TTS/STT), localized via Translation. Directly scores UX 10%.

---

## 8. Cost Strategy (show in proposal appendix)

- Prototype can stay near-free: AI Studio free tier for dev, Gemini Flash-Lite for bulk, Batch/Flex 50% off, context caching 10x, Cloud free tiers above, Cloud Run scale-to-zero, Storage 5GB free, e2-micro free.
- Estimate formula: `(input tokens/1M × in-price) + (output/1M × out-price) + (images × $0.02-0.06) + (video sec × Veo rate) + (Run vCPU-GB-s + requests)`. Add budget alert at $10/$50.
- Don't demo on `2.5-pro` (retiring) or Preview Pro (price/lifecycle risk). Pin `gemini-3.5-flash-001` style IDs.

---

## 9. Theme → Blueprint Mapping

1. **BFSI (Risk/Fraud)**: ADK supervisor (triage) + sub-agents (KYC DocAI, transaction BigQuery anomaly, outreach) + Model Armor + grounding with your data + BigQuery Graphs for multi-hop fraud rings. Metrics: false-positive ↓, review time ↓.
2. **Retail & Commerce**: Vertex AI Search for Commerce + Nano Banana Try-On/Recontext + Veo Fast for product video + Translation + Recommendations. Metrics: CTR, conversion, return ↓.
3. **Manufacturing**: Vision defect + Speech field notes (Transcribe+diarization) + BigQuery ML forecasting + Looker Agent ops copilot on Agent Engine. Metrics: downtime ↓, yield ↑.
4. **Media/Content/Education**: Nano Banana 2 consistent characters + Imagen 4 + Veo 3.1 Lite + TTS/Live Translate dubbing + NotebookLM-style grounded tutor (RAG). Metrics: creation time, comprehension.
5. **Future of Work**: ADK + Agent Gateway (Gmail/Drive/Sheets tools via MCP) + Vector Search over wikis + Gemini Live voice + Code Assist pattern. Metrics: task time, search success.
6. **Sustainability & Social Impact**: BigQuery + geospatial + Document AI (permits) + Translation + TTS/STT accessibility + Maps grounding. Metrics: resource saved, accessibility coverage.

Pick ONE theme (requirements §Category Specification) and name it on slide 1.

---

## 10. Submission Checklist (from requirements.md)

- [ ] Deck PDF: problem → users → GenAI differentiation → architecture (show Cloud Run + Firebase + Gemini Enterprise boxes) → impact metrics → scale + cost → risks/safety.
- [ ] Prototype URL (Firebase Hosting → Cloud Run) + GitHub + `gcloud run` deploy proof.
- [ ] 3-min YouTube/Vimeo/Drive video: 0:00 problem, 0:30 live demo (voice + RAG citations + multimodal), 2:00 architecture + safety, 2:30 impact + next.
- [ ] Docs: model IDs + versions pinned, grounding source list, eval results, pricing estimate, responsible-AI note.

---

## 11. Key Links (latest)

- Models: `ai.google.dev/gemini-api/docs/models`, `cloud.google.com/model-garden`, `firebase.google.com/docs/ai-logic/models`
- Pricing: `cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing`, `ai.google.dev/pricing`, `cloud.google.com/products/gemini-enterprise-agent-platform`
- Build: `adk.dev`, `docs.cloud.google.com/gemini-enterprise-agent-platform/build/adk`, `docs.cloud.google.com/agent-builder`, `genkit.dev`, `firebase.google.com/docs/ai-logic`, `firebase.studio`
- Search/RAG: `docs.cloud.google.com/gemini-enterprise-agent-platform/build/vector-search/overview`, `cloud.google.com/blog/products/ai-machine-learning/rag-and-grounding-on-vertex-ai`
- Media: `docs.cloud.google.com/vertex-ai/generative-ai/docs/models/veo/3-0-generate-preview`, `cloud.google.com/vertex-ai/generative-ai/docs/image/overview`
- Deploy: `cloud.google.com/run`, `firebase.google.com/docs/hosting`, `docs.cloud.google.com/run/docs/integrate/firebase-hosting`
- Free tiers: `cloud.google.com/use-cases/free-ai-tools`
- Data/Agentic analytics (Next 2026): BigQuery Graphs + Measures, Looker Agents in Gemini Enterprise, Knowledge Catalog

> Last updated: 2026-09-06. Re-check model retirement table (`docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions`) before freezing code — 2.x retires Oct 2026.

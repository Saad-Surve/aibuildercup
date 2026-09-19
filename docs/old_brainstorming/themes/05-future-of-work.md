# Future of Work & Enterprise Productivity

[← Back to the master idea guide](../ai-builder-hackathon-idea-guide.md)

## What this theme means

Reduce the friction between organizational knowledge, collaboration, decisions, and execution. The assistant should close a loop by creating an artifact, updating a system, or coordinating an approved next step.

## Problems worth solving

- Decisions are scattered across meetings, documents, chats, and tickets.
- Employees search internal knowledge but cannot judge freshness or authority.
- Onboarding repeats the same questions.
- Teams lose time converting conversations into tasks.
- Language, disability, and dense interfaces exclude workers.

## Originality-first concepts

### Organizational disagreement map — CROSS-REGION VALIDATED

Most knowledge systems store answers and erase disagreement. Distinguish settled decisions, unresolved objections, and assumptions never tested. Show how disagreement moved through time and what evidence would close it. The unique value is **institutional memory of uncertainty**.

**Cross-region validation**: Enterprise knowledge Q&A is common in hackathons. The ADK Hackathon's Energy Agent AI had multi-agent orchestration but focused on customer management, not decision memory. Microsoft Agent Academy had proposal → meeting → document flows but no disagreement tracking. Our idea is genuinely novel: no hackathon project has preserved **institutional uncertainty** as a first-class artifact.

**JAPAC angle**: Cross-functional teams across APAC (especially in Japans keiretsu, Koreas chaebols, and Indian conglomerates) have complex decision chains. Build with synthetic multi-stakeholder decision data showing how disagreements evolved.

**Architecture**: Gemini extraction from meeting transcripts/docs + conflict detection + timeline visualization + BigQuery graph + Firebase frontend + Cloud Run.

### Delegation boundary ledger — CROSS-REGION VALIDATED

For every proposed agent action, show data scope, side effects, reversibility, policy basis, and approval level. Let teams pre-approve low-risk actions while routing novel actions to a human. Demo the same request changing from auto-run to approval-required when scope expands.

**Cross-region validation**: Agent governance is an emerging theme. The Gemini Live Agent Challenge had UI navigation agents (Wand, Moonwalk) but no governance layer. Google Cloud's Agent Gateway/Model Armor is new infrastructure, but no hackathon has built a user-facing **boundary ledger** that makes agent governance transparent. This solves the "trust" problem that judges repeatedly ask about.

**JAPAC angle**: APAC enterprises have strict data residency and compliance requirements. Build with JAPAC data sovereignty scenarios to show how boundaries change across jurisdictions.

**Architecture**: ADK + Agent Gateway + Model Armor + action classifier + Cloud Run audit log + Firebase approval UI.

### Attention budget allocator

Given deadlines, dependencies, meetings, and declared focus windows, propose what should be delayed, delegated, or cancelled. Use a deterministic scheduler underneath Gemini and never infer productivity from keystrokes. The output is a negotiated plan, not a surveillance score.

### Skill graph from artifacts, not surveillance

With consent, analyze completed work artifacts—resolved tickets, docs, code reviews, and training outcomes—to infer demonstrated skills and missing support. Recommend a peer, resource, or stretch task with evidence. Keep the graph user-editable.

## Advanced builds

- **Enterprise agent marketplace:** agents publish capability contracts describing tools, data scope, cost, latency, failure modes, and approval requirements; a router composes them safely.
- **Decision futures room:** specialist agents make forecasts with explicit assumptions, preserve dissent, and score predictions after outcomes to build organizational forecasting memory.

See the detailed architecture in the [global AI hackathon research](../global-ai-hackathon-research.md#future-of-work).

## Common baseline patterns — only use with a sharper wedge

### Decision-to-delivery meeting agent

Process a transcript and linked documents, extract decisions and owners, detect conflicts, and prepare tasks or a decision record. Use Speech-to-Text, Gemini, RAG, Firestore, ADK tools, and a mock issue tracker. Require approval before task creation. Measure time from meeting to task and extraction precision.

### Enterprise knowledge answer with freshness

Answer against policies, wikis, PDFs, and project notes with citations, dates, conflicting-document warnings, and an escalation route. Deliberately include conflicting documents in the demo to show trust behavior.

### Accessibility-first work companion

Support voice, translation, dictation, spoken answers, captions, and keyboard-first workflows. Use STT/TTS, Translation, Gemini, Firebase, and Cloud Run. Measure task completion without visual navigation.

### Research-to-brief analyst

Given an approved source set, create a decision brief with citations, contradictions, gaps, and a review checklist. Keep the source boundary explicit.

## Avoid

File-chat without citations or actions, autonomous email/record changes, and productivity claims based only on answer quality.

## Best demo

Meeting/question → source retrieval → conflict surfaced → useful artifact → one approved action.

## Useful links

- [Google Cloud Looker hackathon winner: generated dashboard summaries](https://cloud.google.com/blog/products/business-intelligence/looker-2024-hackathon-winners)
- [Google Cloud Agent Development Kit hackathon results](https://cloud.google.com/blog/products/ai-machine-learning/adk-hackathon-results-winners-and-highlights?hl=en)

# BFSI: Intelligent Risk, Fraud & Financial Experiences

[← Back to the master idea guide](../ai-builder-hackathon-idea-guide.md)

## What this theme means

Build for banking, financial services, insurance, payments, lending, wealth, or personal finance. The strongest products make a high-friction workflow faster and more understandable while keeping consequential decisions explainable and human-reviewed.

## Problems worth solving

- Fraud analysts face alert overload and fragmented evidence.
- Customers cannot understand why a payment, loan, or claim is delayed.
- Claims require manual comparison of forms, photos, policies, and history.
- Compliance teams repeatedly search long policies and produce audit evidence.
- Small businesses need help understanding cash flow without spreadsheet complexity.

## Originality-first concepts

### Scam recovery orchestrator

When someone is scammed, the hard problem is coordinating the next 90 minutes across bank, card, wallet, telecom, police, and family. The user tells the story once by voice; the system builds a verified incident timeline, identifies which credential should be frozen first, generates channel-specific checklists, and prepares evidence packets without contacting anyone automatically. The differentiator is **recovery choreography**, not a chatbot. Demo with synthetic screenshots and measure time to first protective action.

### Fraud ring time machine

Instead of only ranking an alert, let an analyst ask: “If this merchant/device relationship were legitimate, what else becomes unexplained?” Generate two competing hypotheses, replay the transaction graph under each, and highlight the smallest evidence that would change the conclusion. Use deterministic graph traversal plus Gemini narration. The differentiator is **counterfactual investigation**.

### Policy change compiler

Upload an old and new policy circular. The system identifies changed clauses, generates adversarial customer scenarios, tests whether frontline scripts still comply, and produces a “what changed in practice” briefing. This turns compliance into **policy regression testing**.

### Financial consent receipt

Every high-stakes interaction produces a replayable receipt: user intent, data used, assumptions, unknowns, model steps, and user approval. A customer can hand the receipt to a human adviser. The differentiator is a durable **trust artifact** rather than an answer.

## Common baseline patterns — only use with a sharper wedge

### Fraud case investigator and evidence graph

Upload an alert bundle; extract accounts, devices, merchants, and dates; connect related records; retrieve relevant policy rules; and produce an explainable case timeline. Use synthetic transactions, BigQuery/Firestore joins, Gemini structured output, Document AI, and an ADK supervisor with bounded tools. Measure review time, false positives, evidence completeness, and citation coverage.

### Plain-language financial decision companion

Compare two loan, insurance, or savings documents in plain language. Show fees, assumptions, scenarios, and questions for a human adviser. Use Gemini PDF understanding, Document AI, Cloud Run calculations, citations by page/section, and Translation/TTS for accessibility. Never let the model perform the arithmetic or present unverified advice.

### Claims triage assistant

Combine a claim form, damage photos, and a voice note. Identify missing information, classify the case, retrieve coverage language, and draft the next message for an adjuster. Use Gemini vision, Cloud Storage, Speech-to-Text, Firestore, and human approval before a coverage decision.

### Small-business cash-flow coach

Analyze a synthetic transaction and invoice export, explain upcoming cash gaps, draft collection messages, and show deterministic scenarios. Use BigQuery for aggregation and Gemini for explanation, with every insight linked to source rows.

## Avoid

Generic banking chatbots, opaque fraud scores, fabricated rates, and autonomous approval/denial of loans, claims, or account actions.

## Best demo

Alert/document → evidence retrieval → explanation with citations → recommended next step → human approval. End with review-time reduction and the explicit safety boundary.

## Useful links

- [Google Gen AI Exchange program](https://blog.google/intl/en-in/company-news/outreach-initiatives/supercharge-your-skills-google-clouds-gen-ai-exchange-program-is-empowering-indian-developers/)
- [Google Cloud judging-oriented ADK hackathon examples](https://cloud.google.com/blog/products/ai-machine-learning/adk-hackathon-results-winners-and-highlights?hl=en)

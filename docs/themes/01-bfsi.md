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

### Scam recovery orchestrator — CROSS-REGION VALIDATED

When someone is scammed, the hard problem is coordinating the next 90 minutes across bank, card, wallet, telecom, police, and family. The user tells the story once by voice; the system builds a verified incident timeline, identifies which credential should be frozen first, generates channel-specific checklists, and prepares evidence packets without contacting anyone automatically. The differentiator is **recovery choreography**, not a chatbot. Demo with synthetic screenshots and measure time to first protective action.

**Cross-region validation**: No hackathon winner globally has addressed the *recovery* side of fraud. ADK Hackathon winners focused on detection/triage (Energy Agent AI, fraud investigation). The Gemini Live Agent Challenge had NagarDrishti (voice-based emergency reporting) but no financial recovery coordination. Our idea is differentiated because it choreographs a multi-institution response — a coordination problem, not a detection problem.

**JAPAC angle**: Scam losses in Asia-Pacific exceed $10B annually. The 90-minute coordination window is universal but disproportionately affects elderly populations in Japan, Korea, and Southeast Asia. Build with multilingual voice input and local institution formats.

**Architecture**: ADK supervisor + sub-agents (bank freeze, card block, telecom alert, police report, family notification) + Gemini speech-to-text + BigQuery timeline graph + Cloud Run deployment.

### Fraud ring time machine

Instead of only ranking an alert, let an analyst ask: "If this merchant/device relationship were legitimate, what else becomes unexplained?" Generate two competing hypotheses, replay the transaction graph under each, and highlight the smallest evidence that would change the conclusion. Use deterministic graph traversal plus Gemini narration. The differentiator is **counterfactual investigation**.

**Cross-region validation**: The BigQuery AI Hackathon showed TriLink analyzing ticket text + images, but no project used counterfactual reasoning for fraud. Our idea generates competing hypotheses and shows the smallest evidence that would flip the conclusion — this is what investigators actually do, but no AI tool supports it.

### Policy change compiler — CROSS-REGION VALIDATED

Upload an old and new policy circular. The system identifies changed clauses, generates adversarial customer scenarios, tests whether frontline scripts still comply, and produces a "what changed in practice" briefing. This turns compliance into **policy regression testing**.

**Cross-region validation**: Compliance chatbots are common in hackathons (Financial Q&A, policy bots). But no project treats compliance like software testing — generating adversarial scenarios and running them through changed clauses. This is novel because it converts a static review into a dynamic regression test.

**JAPAC angle**: Multi-jurisdiction compliance across APAC is a $50B+ industry pain point. Build with JAPAC financial regulations as the test corpus.

**Architecture**: Gemini PDF understanding + clause diff engine + scenario generator + compliance checker + BigQuery audit log + Cloud Run.

### Financial consent receipt

Every high-stakes interaction produces a replayable receipt: user intent, data used, assumptions, unknowns, model steps, and user approval. A customer can hand the receipt to a human adviser. The differentiator is a durable **trust artifact** rather than an answer.

## Advanced builds

- **Cross-institution fraud kill chain:** simulated banks, wallets, and merchants exchange minimum-necessary event attestations; an agent builds a timeline and proposes a coordinated intervention without sharing raw data.
- **Multi-party financial negotiation room:** customer, lender, insurer, and advocate agents negotiate within declared constraints and produce a consent receipt showing trade-offs and unresolved conflicts.

See the detailed architecture in the [global AI hackathon research](../global-ai-hackathon-research.md#bfsi).

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

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

### Organizational disagreement map

Most knowledge systems store answers and erase disagreement. Distinguish settled decisions, unresolved objections, and assumptions never tested. Show how disagreement moved through time and what evidence would close it. The unique value is **institutional memory of uncertainty**.

### Delegation boundary ledger

For every proposed agent action, show data scope, side effects, reversibility, policy basis, and approval level. Let teams pre-approve low-risk actions while routing novel actions to a human. Demo the same request changing from auto-run to approval-required when scope expands.

### Attention budget allocator

Given deadlines, dependencies, meetings, and declared focus windows, propose what should be delayed, delegated, or cancelled. Use a deterministic scheduler underneath Gemini and never infer productivity from keystrokes. The output is a negotiated plan, not a surveillance score.

### Skill graph from artifacts, not surveillance

With consent, analyze completed work artifacts—resolved tickets, docs, code reviews, and training outcomes—to infer demonstrated skills and missing support. Recommend a peer, resource, or stretch task with evidence. Keep the graph user-editable.

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

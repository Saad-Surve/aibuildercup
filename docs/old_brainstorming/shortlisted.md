### Scam recovery orchestrator — CROSS-REGION VALIDATED

When someone is scammed, the hard problem is coordinating the next 90 minutes across bank, card, wallet, telecom, police, and family. The user tells the story once by voice; the system builds a verified incident timeline, identifies which credential should be frozen first, generates channel-specific checklists, and prepares evidence packets without contacting anyone automatically. The differentiator is **recovery choreography**, not a chatbot. Demo with synthetic screenshots and measure time to first protective action.

**Cross-region validation**: No hackathon winner globally has addressed the *recovery* side of fraud. ADK Hackathon winners focused on detection/triage (Energy Agent AI, fraud investigation). The Gemini Live Agent Challenge had NagarDrishti (voice-based emergency reporting) but no financial recovery coordination. Our idea is differentiated because it choreographs a multi-institution response — a coordination problem, not a detection problem.

**JAPAC angle**: Scam losses in Asia-Pacific exceed $10B annually. The 90-minute coordination window is universal but disproportionately affects elderly populations in Japan, Korea, and Southeast Asia. Build with multilingual voice input and local institution formats.

**Architecture**: ADK supervisor + sub-agents (bank freeze, card block, telecom alert, police report, family notification) + Gemini speech-to-text + BigQuery timeline graph + Cloud Run deployment.

### Comprehension debugger — CROSS-REGION VALIDATED

After an article or video, run a tiny diagnostic conversation to identify the exact concept where audience segments diverge. Suggest an edit or alternate explanation. The editor sees an **understanding heatmap**, not an engagement dashboard.

**Cross-region validation**: EdTech is a popular hackathon theme (Edu.AI, Nexora, Padayon Ko, StoryGrow). Most focus on tutoring or quiz generation. Our idea is different: it's a **diagnostic tool for content creators**, not learners. The "understanding heatmap" visualization is a novel artifact. LitLab.ai does oral reading analysis but doesn't produce concept-level divergence maps.

**JAPAC angle**: APAC education systems have massive language diversity and varying literacy levels. Build with multi-language content and show how comprehension diverges across language groups.

**Architecture**: Gemini adaptive questioning + concept extraction + BigQuery analytics + Firebase visualization + Cloud Run.


### Repairability passport

Photograph a broken product and upload a receipt/manual. Identify likely repair paths, compatible parts, local repair skills, uncertainty, and repair/reuse/replace impact comparisons. The differentiator is a local repair loop rather than generic sustainability advice.

# Creator library: evidence you can explore

Creator-facing purpose: see which supplied or synced material the studio can retrieve, then
find a passage or thumbnail by describing it. Route `/library`, also linked from Settings.

Visual plan: existing studio palette (paper #fafafa, ink #171717, line #e5e5e5, muted #737373,
signal #5b82a6), with existing Schibsted display/body and Geist Mono for counts. A wide map
beside a narrow evidence inspector; below it, keyboard-accessible source rows. The signature
is an evidence constellation: text points and thumbnail tiles occupy an actual two-dimensional
PCA projection of Gemini vectors, passages from the selected source connect with quiet lines. Searching
highlights matching nodes while the inspector shows the exact retrieved passage/source.

Critique before implementation: generic network decoration would imply connections we did
not calculate. Use only shared-source connections, label the projection approximate, show a
list for pending nodes, and keep modality shape as well as color. No ambient movement or
invented topic labels. Responsive map/list stack on small screens. Empty state connects to
Settings and explains the operator folder import; it never invents a creator library.

Model choice: Gemini Embedding 2, GA April 22 2026, supports text and image vectors in the
same space. Use 768 dimensions, documented retrieval prefixes for text and no task_type.
Multimodal accompanying text uses natural titles. Separate each input into its own Content.
Use the existing configured Gemini location (`global` by default); the model card only lists
global/us/eu, so this intentionally follows the application's existing Gemini endpoint, not
the us-central1 Storage/Firestore region. Text $0.20/M tokens, images $0.45/M input tokens
per current pricing page (still labeled Preview there despite the model card's GA status).

Sources checked October 11 2026:
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/embedding-2
- https://ai.google.dev/gemini-api/docs/embeddings
- https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing

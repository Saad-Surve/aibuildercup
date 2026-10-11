# Veo source-style direction — implementation in progress

- Researched Google's official Veo 3.1 prompt formula, image-to-video best practices,
  negative prompts, image input/model/region support and reference-mode constraints.
  Sources and decisions: docs/research/veo-source-style-2026-10-11.md.
- Added local shot direction: three timestamped frames plus a six-second local clip per
  footage idea. Source observation is a separate Gemini call from insert design.
- Initial live combined call hallucinated the proposed mouse shot as the observed source.
  Split the calls so the observer never sees an insert idea; fixed its focus on the center
  frame's scene and camera/edit rhythm rather than presenter gestures.
- Updated OpenAPI and Firestore contracts first. Inserts now expose observed style,
  reference preview/timestamp, generation mode and reason. Reference media stays under
  the existing insert prefix; cancellation/deletion after upload removes it.
- Veo provider accepts actual first-frame bytes and negative prompts. Image shots keep
  source aspect; text shots append transferable source look despite user direction edits.
  Paid caps, ambiguous submission protection and operation resumes remain in place.
- Frontend displays reference, style and mode. Old unsubmitted suggestions require fresh
  planning; legacy operations can still resume. No infrastructure/dependency changes.
- Backend lint/types and web lint/ESLint/build passed at the first implementation checkpoint
  (134 Python files; four existing Library img warnings). More live checks and final
  verification are underway; no paid generation has been submitted in this session yet.
- Next: verify separate observation/direction on fixtures, validate actual first-frame
  conditioning with one capped Veo call, inspect output visually, complete checks and
  commit/push the fix under the user's existing authorization.

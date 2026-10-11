# Veo inserts: source-style research and implementation complete

## Work and structural changes

- Implemented the user's request to research Veo prompting online and fix footage that
  lacked the source video's visual style. Sources/decisions are recorded in
  docs/research/veo-source-style-2026-10-11.md; updated packaging technical design.
- Suggestions still derive facts/timestamps from the transcript. Each footage idea now
  adds a bounded source-only observation call and a separate shot-design call, using
  three nearby JPEGs (up to 1280px) and a local clip (up to six seconds).
- New VisualStyle/OpenAPI fields expose observed look, generation mode, source-reference
  timestamp/preview and reason. Stored internal audit flags guard first-frame eligibility.
  Source frame media lives in the existing user/project/insert prefix; late uploads are
  cleaned after cancellation/deletion, and individual/project deletion covers references.
- Veo provider accepts actual JPEG first-frame input and negative prompts, in us-central1,
  one silent six-second 720p result. Image shots keep source aspect. Text shots carry the
  observed palette, lighting, texture and camera character despite direction edits.
- Exact submitted prompts are saved before submission. Paid limits and ambiguous-submit
  protection remain; retries poll the saved operation. Old unsubmitted footage ideas
  require new suggestions; old submitted operations remain resumable.
- Panel shows the source frame, observed look and detailed direction before rendering.
  No dependencies, infrastructure or test files were added.

## Discoveries and live verification

- Combined observation/design hallucinated the intended mouse scene as source footage.
  Separating observation from the idea corrected this; focusing on the center frame avoids
  mixing two scenes across a cut. An independent frame audit blocked a phone-screen frame
  with visible digits even when the shot designer wanted to use it as an opening image.
- Nine bounded Gemini Flash Lite calls inspected source direction during development.
  Fixture apple-product.mp4 at 91s yielded actual cardboard/warm-tone evidence and text
  fallback for writing; at 28s yielded the actual warm wood/black charging-pad scene and
  correctly classified a clean center frame, neighboring title/person and hand frames.
- EXACTLY ONE paid Veo request was submitted with the clean 28s source JPEG and generated
  1280x720, six-second video with no audio. Saved operation name before polling; no
  submissions retried. Conservative validation bound $2.40, not invoice-backed spend.
- Inspected all six sampled output frames alongside the reference. Wood, palette, lighting,
  object and overhead angle carry through. The end framing widens again despite a steady
  zoom request. Added explicit modest motion, final two-second hold and camera-reset/jump-cut
  exclusions afterward. That temporal refinement has not had another paid generation.
  The sample checks appearance in ONE case, not general quality or seamless motion.
- The live director checks use a clearly labeled validation-only editorial brief, not a
  fabricated transcript attributed to the source. This session did not re-run the full
  upload/STT/suggestion/render UI workflow; the previous session verified that workflow.
- Local artifacts: /tmp/veo-style-verification/{direction.json,reference.jpg,matched-veo.mp4,
  output-sequence.jpg,output-middle.jpg}. No temporary Firebase users, Firestore records,
  GCS objects or credentials were created. Provider operation is the sole external output.

## Checks and next steps

- uv run ruff check . and uv run mypy app passed (134 Python files).
- bun run lint, bun run lint:eslint and bun run build passed. Four existing Library img
  warnings and static-export rewrite warnings remain.
- Four changed/adjacent schemas match runtime OpenAPI; git diff --check passed.
- Source/output comparison preview checked at desktop/mobile with no console errors.
- Commit and push this fix under the user's existing explicit authorization. Push result
  is verified and reported in the assistant response. No deployment was requested.
- Existing suggestions need regeneration to use the director. Pixel conditioning only
  applies when a relevant clean source frame exists; otherwise appearance is text-grounded
  and may drift. Creator review remains necessary for motion and conceptual usefulness.

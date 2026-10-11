# Veo inserts grounded in the source video's look

Researched 11 October 2026, in response to inserts that looked unrelated to the uploaded video.

## Official guidance and implementation choices

- [Google's Veo 3.1 prompting guide](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1): direct a shot with cinematography, subject, action, context and style/ambiance. We compile those components explicitly instead of asking for generic cinematic B-roll. A six-second insert has one action and at most one simple camera move.
- [Video generation best practices](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/best-practice): a clear opening image establishes subject, lighting and artistic style; image-to-video prompts should focus on motion instead of redescribing the image. We send an actual source JPEG to Veo when it already contains the relevant subject/setting. Frames with presenters, visible writing, logos or unrelated subjects remain style evidence only. Camera pacing comes from a short surrounding clip, not a still.
- [Veo prompt guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/video-gen-prompt-guide): explicitly direct framing, camera motion and visual aesthetics; negative prompts list unwanted elements rather than negated commands. We preserve observed palette, lighting and texture. The director adapts source framing and surroundings to the insert's subject. Negative prompts include incompatible aesthetic descriptors plus text, simulated results, morphing and montage exclusions.
- [Image-to-video API guide](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/video/generate-videos-from-an-image) and [Veo 3.1 specifications](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/veo/3-1-generate): `veo-3.1-fast-generate-001` supports image inputs, six-second clips and landscape/portrait in `us-central1`. We use SDK `image=Image(image_bytes=..., mime_type=...)`, one silent 720p output, and padding to preserve composition. This is first-frame conditioning, not `referenceImages.style`. The source aspect is fixed for these shots. Asset-reference workflows have different duration constraints, so we do not substitute them into the six-second path.
- [Prompt rewriter guidance](https://cloud.google.com/vertex-ai/generative-ai/docs/video/turn-the-prompt-rewriter-off?hl=id): its indexed guidance says Veo 3/3.1 rewriting cannot be disabled. The English URL now redirects to the overview. Do not claim `enhance_prompt=False` locks Veo's internal prompt; we omit that unsupported assumption and persist the exact request we submit.

## Implementation

The suggestion planner retains transcript-grounded concepts. For each B-roll idea, the director
extracts three nearby frames at up to 1280px and a local clip of up to six seconds. An observation
call receives footage and insertion timestamp only. A separate shot-design call receives the
observed style plus the idea and footage. The observer also audits each candidate for
people, visible text/logos, clarity and scene continuity; the server checks those flags
before enabling image conditioning. This separation matters: the first live combined
call described the imagined mouse shot as the source scene despite seeing a presenter.

Every insert stores its observed recipe, reference timestamp, mode, plain-language reason,
version and reference JPEG under the existing owned project/insert paths. Text-mode requests
append the transferable color/light/texture/camera recipe even after direction edits; they
avoid copying a presenter's actions into an object shot. Image-mode requests describe motion
and send the actual JPEG. No new imagery is synthesized as an intermediate step and no extra
paid video generation occurs during suggestions. At most three ideas means at most six extra
Flash Lite observation/direction calls. Existing paid reservations and operation-resume rules
remain in force. Older unsubmitted suggestions need regeneration; already submitted operations
resume without changing their request.

Source appearance is an input constraint, not a quality guarantee. Brand/product identity,
real measurements and footage authenticity must not be inferred from illustrative output.
See the session progress note for bounded live verification and remaining limits.

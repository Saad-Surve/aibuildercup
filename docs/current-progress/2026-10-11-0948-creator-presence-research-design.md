# Account-first onboarding and creator-presence research proposal

## Work completed

- Reviewed the latest EmbeddingGemma research handoff and technical-design overview.
- Inspected onboarding steps, the reusable YouTube connection UI, OAuth return-path support,
  channel-content sync, connector caption/analytics access, and persona research.
- Checked primary YouTube API documentation and developer policies for collection limits.
- Developed a concrete proposed flow for the user's idea: account creation -> connect
  accounts/add links -> collect a creator content library -> review the inferred profile.
  Embedding/index selection follows collection, as requested.
- This is design/research only. No application code, contracts, schema, dependencies,
  infrastructure, or cloud data changed; no scraping or inference was run for a real creator.
  User asked for an assessment of the idea; implementation remains a future unit of work.

## Existing building blocks and gaps

- Onboarding already has an optional Import step for creator links before identity/topics/
  audience/style questions. It can become the account-and-presence entry point.
- `YouTubeConnections` and `web/src/lib/connections.ts` already support connecting,
  disconnecting, metadata/content/analytics sync. OAuth supports a same-origin redirectPath,
  so onboarding can resume after OAuth rather than sending the creator to settings/profile.
- Only YouTube is currently a real connected platform. A website/newsletter link is a
  research source, not an OAuth-connected account. Do not label unsupported platforms as
  connected just because a user supplied their URL.
- Current channel sync defaults to up to 50 video metadata records and up to 10 new caption
  downloads per sync. It stores thumbnail URLs, not a persistent collection of 10 images.
  Captions are flattened and truncated to 6000 characters; later passage retrieval needs
  timed, bounded full-source ingestion rather than assuming this is a complete transcript.
- Current PersonaResearchService is one grounded Gemini call over supplied URLs. It saves
  inferred answers and source links, but does not collect/persist the actual page documents
  or image/media evidence that would form an embedding corpus.

## Proposed product flow

1. After account creation/welcome, offer **Connect your accounts** with YouTube and a field
   for website/blog/newsletter links. Explain that selected content informs voice, topics,
   visual references and recommendations. Allow skipping and keep the same management
   surface available in settings. Separate research collection from publishing actions.
2. Resolve explicit connected channel identities and supplied links. Suggest additional
   profiles found through links on known creator sites, but have the user confirm ambiguous
   matches rather than merging people by display name.
3. Show the collection batch and start a bounded background research job. Proposed defaults:
   up to 50 video metadata records, 10 representative thumbnails, up to 10 available caption
   tracks, and up to 10 written pieces plus the site's about/bio page. These are proposed
   upper bounds, not guarantees of source availability. Sample recent and established work,
   avoiding only recent items or only the largest view counts.
4. Display real counts and statuses by source: content found, imported, unavailable, failed,
   or still fetching. Partial results are useful; continue onboarding with them. Support
   retry/refresh and incremental collection without unlimited recursive crawling.
5. Produce an editable creator profile linked to evidence: topics, formats, language,
   spoken/written voice, visual patterns, recurring brand terms, stated goals and audience.
   Mark observed facts, model inferences and user assertions separately. User corrections
   override inferred defaults. Keep actual audience analytics separate from an audience
   inferred from content. Do not turn a sample of past work into a fixed creative identity.
6. Let the creator inspect/delete sources and refresh the research from settings later.

## Collection pipeline recommendation

- Use deterministic platform connectors for authenticated API collection; introduce a
  crawler provider for supported website/feed sources. Fetch feeds/sitemaps/explicit links
  within page, byte, duration and cost budgets. Respect source access rules. Do not send an
  unconstrained agent to collect everything on the internet about a name.
- Use a researcher to select useful sources and synthesize a cited profile after collection.
  Search grounding helps discover links, but is not proof that complete page text was fetched.
- Keep authored posts/transcripts separate from audience comments and third-party mentions.
  A commenter’s tone must not become the creator's writing voice. Third-party reporting may
  support a biography only with explicit provenance and careful identity resolution.
- Store raw permitted source content/media plus normalized records with ownerUid, source id,
  connection id, canonical URL, author/channel identity, content type, language, publication
  and fetch timestamps, content hash, collection method, visibility and retention policy.
- Collect public creator-facing content by default. Include private/unlisted connected-account
  work only through an explicit selection in the product. Never embed OAuth credentials.
- Use source-scoped lineage so removing a source removes its chunks/media/embeddings and
  invalidates or regenerates summaries derived from it. Account deletion must remove all
  creator-level research, not just project records. Fix the known non-recursive connection
  disconnect before expanding connection-scoped storage.
- User-provided URL fetching needs normal server-side URL controls: reject local/private
  network targets and recheck redirects; bound request time and response sizes.

## Embedding design, after collection

- The user's shared-space idea is appropriate for a multimodal model such as EmbeddingGemma 2.
  One space means compatible vectors for individual passages, images and timed media windows,
  not one vector containing the entire creator or a shared searchable index across users.
- Preserve each item and its metadata. Apply tenant/source/content-type filters and normalize
  rankings across modalities as needed. Query/doc vectors must use compatible model/dimensions.
- Keep a small structured, editable profile alongside the retrievable evidence library.
  Dates, statistics, settings, targets, explicit preferences and OAuth data remain structured;
  semantic similarity does not replace accurate numeric queries or access control.
- Example: a thumbnail brief retrieves relevant image references and topic passages; a script
  retrieves comparable authored passages plus current user preferences; audience recommendations
  use actual period-bound analytics. No need to load all collected content into every prompt.
- Decide model/hosting only after the first collection inventory demonstrates what modalities
  and source volumes are actually available. Do not add embedding dependencies in this phase.

## Verified platform constraints

- YouTube's API returns video metadata and thumbnail URLs. Caption downloads require permission
  to edit the relevant video and may fail; mark unavailable captions and accept original video,
  caption or written-content uploads as another ingestion route.
- YouTube developer policies explicitly prohibit scraping YouTube/Google applications and
  obtaining scraped YouTube content. More content coverage does not justify replacing this
  connector with a YouTube page scraper or downloading videos via scraping tools.
- YouTube API data has category-specific refresh/deletion and authorization-verification rules.
  Retention is not an indefinite once-only import. API-derived data/metrics have additional
  restrictions and an amended advanced-analytics approval path. Verify the proposed API-derived
  embedding/synthesis use rather than assuming connecting OAuth approves every downstream use.
  Independently supplied creator originals are a distinct input source, not a relabeling of API
  data. Implement lineage for each source type.

## Structure, verification, and next step

- No production contracts/schema/infra changed. This note records proposed decisions for review,
  not an implemented or approved architecture. Preserve the preceding untracked research note.
- Verified via static code reads and primary-source documentation. No runtime checks were needed
  for this documentation-only work; no test files added and no paid cloud calls made.
- Recommended first implementation slice: adapt onboarding Import to reuse account connection
  controls and creator links; add resumable background collection with source/count/status UI;
  persist a bounded creator library and use it to prefill an editable evidence-backed profile.
- Before building: update API/Firestore/event contracts for jobs and user/connection-scoped
  research; define deletion/refresh behavior; read relevant Next.js bundled docs; verify real
  services using available fixture/content sources and the repository lint/type/build commands.

## Sources

- https://developers.google.com/youtube/v3/docs/videos
- https://developers.google.com/youtube/v3/docs/captions/download
- https://developers.google.com/youtube/terms/developer-policies
- https://developers.google.com/youtube/terms/derived-metrics-policy
- https://ai.google.dev/gemma/docs/embeddinggemma/model_card_2

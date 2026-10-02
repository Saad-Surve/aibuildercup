# Creator Helper Studio — Frontend Implementation Plan

Recommended frontend: Next.js App Router, TypeScript, Tailwind CSS, Firebase Web SDK, TanStack Query, and a timeline library or custom SVG heatmap layer.

## 1. Initialize the application

~~~bash
npx create-next-app@latest creator-studio-web \
  --typescript \
  --eslint \
  --tailwind \
  --app \
  --src-dir \
  --import-alias "@/*"

cd creator-studio-web
npm install firebase @tanstack/react-query zod react-hook-form
npm install lucide-react date-fns
~~~

Environment variables:

~~~text
NEXT_PUBLIC_FIREBASE_API_KEY
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN
NEXT_PUBLIC_FIREBASE_PROJECT_ID
NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET
NEXT_PUBLIC_FIREBASE_APP_ID
NEXT_PUBLIC_API_BASE_URL
~~~

Never place server secrets or OAuth client secrets in NEXT_PUBLIC variables.

The API client and TypeScript types are derived from `contracts/openapi.yaml`, so the frontend
and backend cannot drift. There is no MSW mock layer: the web app calls the real API. See
[mock-and-seed.md](./mock-and-seed.md).

## 2. Frontend directory structure

~~~text
src/
├── app/
│   ├── (auth)/login/page.tsx
│   ├── (app)/layout.tsx
│   ├── (app)/dashboard/page.tsx
│   ├── (app)/onboarding/page.tsx
│   ├── (app)/projects/page.tsx
│   ├── (app)/projects/[projectId]/page.tsx
│   ├── (app)/projects/[projectId]/chat/page.tsx
│   ├── (app)/settings/connections/page.tsx
│   └── api/health/route.ts
├── components/
│   ├── auth/
│   ├── onboarding/
│   ├── layout/
│   ├── projects/
│   ├── timeline/
│   ├── analysis/
│   ├── artifacts/
│   ├── localization/
│   ├── chat/
│   └── common/
├── lib/
│   ├── firebase.ts
│   ├── api-client.ts
│   ├── auth.ts
│   ├── query-client.ts
│   ├── events.ts
│   └── validators.ts
├── generated/
│   └── api/            types + client generated from contracts/openapi.yaml
├── hooks/
├── types/
└── styles/
~~~

## 3. Application shell

Create these shared components first:

~~~text
AppShell
Sidebar
TopBar
UserMenu
Breadcrumbs
PageHeader
LoadingState
ErrorState
EmptyState
ToastProvider
ConfirmDialog
JobProgressBanner
~~~

Sidebar navigation:

~~~text
Dashboard
Projects
Audience Insights
Connections
Persona
Settings
~~~

## 4. Authentication

Create:

~~~text
LoginPage
GoogleSignInButton
EmailSignInForm
AuthLoadingScreen
ProtectedRoute
AuthProvider
~~~

Flow:

1. Initialize Firebase Auth.
2. Subscribe to auth state changes.
3. Obtain a Firebase ID token.
4. Attach the token to every API request.
5. Call GET /me after login.
6. Redirect new users to onboarding.
7. Redirect returning users to the dashboard.

The frontend should not use Firestore directly for sensitive data. Use the API for connections, jobs, analysis, and artifacts.

## 5. Onboarding flow

Route: /onboarding

Component tree:

~~~text
OnboardingShell
├── WelcomeStep
├── CreatorIdentityStep
├── ContentTopicsStep
├── AudienceStep
├── StyleAndLanguageStep
├── PlatformConnectionStep
├── PersonaPreviewStep
└── CompletionStep
~~~

### WelcomeStep

- Explain the studio.
- Explain what data will be accessed.
- Link to privacy and consent information.

### CreatorIdentityStep

- Creator name.
- Location and timezone.
- Preferred language.
- Optional website or bio.

### ContentTopicsStep

- Main topics.
- Content categories.
- Content formats.
- Typical video length.

### AudienceStep

- Intended audience.
- Audience location.
- Knowledge level.
- Primary audience goal.

### StyleAndLanguageStep

- Tone.
- Words to avoid.
- Preferred hook style.
- Caption preferences.
- Regional/cultural preferences.

### PlatformConnectionStep

- Connect YouTube.
- Optionally connect Instagram/Facebook.
- Explain authentication versus analytics permissions.
- Allow skip and connect later.

### PersonaPreviewStep

- Show generated persona summary.
- Allow edits.
- Require explicit confirmation before saving.

Each step calls PUT /onboarding. The final step calls POST /onboarding/complete.

## 6. Dashboard and project creation

Create:

~~~text
DashboardPage
ProjectCard
ProjectGrid
CreateProjectDialog
RecentProjectList
ConnectionStatusCard
AudienceSummaryCard
~~~

Create project fields:

- Project name.
- Description.
- Primary language.
- Target platforms.
- Target output languages.
- Demo project toggle (binds the project to a pinned demo scenario; hidden in the live configuration).

After creation, route to /projects/{projectId}.

## 7. Project workspace

Desktop layout:

~~~text
ProjectWorkspace
├── ProjectHeader
├── VideoPreviewPanel
├── TimelinePanel
│   ├── VideoTimeline
│   ├── TranscriptTrack
│   └── HeatmapTracks
├── FindingDetailsPanel
└── ProjectAssistantPanel
~~~

Mobile behavior:

- Video first.
- Heatmap and transcript as tabs.
- Assistant as a bottom sheet.

## 8. Upload experience

Create:

~~~text
VideoDropzone
VideoRevisions
VideoFilePicker
UploadProgress
UploadValidationError
UploadCompleteState
ProcessingStatusCard
~~~

Flow:

1. Validate file type and size locally.
2. Create an upload session through the API.
3. Upload directly to Cloud Storage.
4. Display resumable progress.
5. Confirm upload.
6. Subscribe to job progress.
7. Enable transcript/timeline when ready.

A project keeps one video but may hold several revisions of it. After the first
upload, `VideoRevisions` in the source-video card shows the active revision, lists the
retained history, and opens the same dropzone to upload a new revision. A new revision
becomes active and is transcribed automatically; once its transcript lands the review
panel nudges the user to re-run the analysis, because the newest run was built from the
previous revision's transcript. The history shows each revision's transcript version and
review count, and can make an earlier revision active again (switching back is lossless).

The browser must not upload the file through the API server.

## 9. Transcript and timeline UI

Create:

~~~text
VideoPlayer
TimelineRuler
TranscriptTrack
TranscriptSegment
WordHighlight
HeatmapTrack
HeatmapBin
FindingPopover
FindingDrawer
JumpToTimestampButton
~~~

Interactions:

- Clicking a transcript segment seeks the video.
- Hovering a heatmap bin shows its score.
- Clicking a bin opens findings.
- Clicking evidence highlights the transcript span.
- Selecting a range creates a clip candidate.

## 10. Analysis controls

Create:

~~~text
AnalysisToolbar
DimensionFilter
SeverityFilter
AnalysisRunSelector
ReviewerStatusList
OverallScoreCard
~~~

Dimensions:

~~~text
Truth & Evidence
Clarity
Structure & Pacing
Legal & Safety
Cultural & Localization
Platform Fit
Audience Fit
Brand Voice
Engagement & Retention
Emotional Impact
SEO & Discoverability
Visual & Accessibility
Conversion & CTA
~~~

If one reviewer fails, show a partial result instead of blocking the whole workspace.

## 11. Artifact gallery

Create:

~~~text
ArtifactGallery
ArtifactCard
ArtifactTypeFilter
ArtifactPreviewModal
DownloadButton
RegenerateDialog
DeleteArtifactDialog
~~~

Artifact tabs:

~~~text
Shorts
Captions
Thumbnails
Social Posts
Blogs
Localized Versions
AI Intros/Outros
~~~

Every generation action shows queued, generating, ready, and failed states with retry.

## 12. Localization UI

Create:

~~~text
LanguageSelector
LocalizationOptions
GlossaryEditor
CorpusVersionBadge
CaptionPreview
DubbedVideoPreview
LocalizationComparisonView
~~~

The comparison view lets the user switch between source and localized captions and flag incorrect phrases.

## 13. Connections and audience insights

Create:

~~~text
ConnectionsPage
PlatformConnectionCard
OAuthRedirectHandler
SyncNowButton
SyncHistoryTable
AudienceInsightsPage
AudienceSummaryChart
ContentPerformanceTable
SentimentBreakdown
~~~

Communicate clearly that audience data is aggregated platform data, not a complete representation of every viewer.

## 14. Project chat

Create:

~~~text
ProjectAssistantPanel
ChatThreadList
ChatMessageList
ChatComposer
StreamingMessage
SuggestedPromptChips
ToolResultCard
ArtifactAttachmentCard
CitationList
~~~

Suggested prompts:

~~~text
Find the weakest section of this video.
Give me three better hooks.
Create a Hindi caption.
Turn the strongest section into a Short.
Explain the legal and safety concerns.
Update my creator preferences based on this choice.
~~~

Show tool activity such as Finding transcript evidence or Creating clip candidate.

## 15. Frontend implementation order

1. Initialize Next.js and shared styling.
2. Add Firebase Auth.
3. Add API client and token interceptor.
4. Build application shell and route guards.
5. Build onboarding and persona preview.
6. Build project list and project creation.
7. Build direct video upload.
8. Build processing status and realtime WebSocket updates.
9. Build video player and transcript view.
10. Build heatmap tracks and findings drawer.
11. Add artifact gallery.
12. Add project chat.
13. Add connections and audience insights.
14. Add localization UI.
15. Add feedback, error states, loading states, and deletion flows.
16. Add responsive layout and accessibility pass.

## 16. Frontend acceptance checklist

- New users cannot access project routes before onboarding.
- Returning users resume at the dashboard.
- Large videos upload directly to Cloud Storage.
- Upload progress survives a temporary page refresh where possible.
- The timeline remains usable for a 30-minute video.
- Heatmap findings link to precise timestamps.
- Failed reviewers do not hide successful reviewer results.
- Every async action has progress, retry, and failure UI.
- Signed download URLs are never persisted in local storage.
- The user can delete a project and see deletion progress.


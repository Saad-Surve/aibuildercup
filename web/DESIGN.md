# Creator Helper Studio — Design System

The reference for anyone building UI in `web/`. Tokens live in `src/app/globals.css`;
primitives live in `src/components/ui` (shadcn) and `src/components/common`.

## 1. Design read

A professional creator-tooling **product UI** (not a marketing site) for solo creators.
Calm, Linear-adjacent, high-contrast, low decoration. Dials: variance 4, motion 3, density 5.

**Thesis: colour is meaning.** The chrome is monochrome. A single desaturated blue (the
"signal") marks anything interactive. The severity / heatmap scale is the only other place
colour appears, because in this product colour _is_ the review signal. No brand gradients, no
glows, no decorative accent colour.

**Signature:** the three-track mark (timeline + heatmap reduced to geometry) and the
track-and-tick motif used in step rails and data rows. The interface stays quiet so the
heatmap can be the loudest thing on screen.

**Exception — the public landing page (`/`).** It is a marketing surface, not product UI. It
uses a scroll-condensing pill nav (transparent bar at top, floating pill with compact logo
after scrolling, links kept exactly centred), a centered hero, a display serif
(Playfair Display, `font-serif`) for the headline, a static peripheral backdrop (haze,
creator-motif vignettes, film grain — no ambient loops), a capability strip, a platform
flow section (derivative chips → studio tile → brand destinations from `public/` SVGs,
marching-dash flow lines, Connected pill),
an asymmetric feature bento with hands-on mini demos (draggable heatmap cursor, SRT block,
clip-cut interaction, translation stepper, send/typing/reply chat, draft→edit→final
pages — no card icons, no hover elevation, per-card accent colours), a dotted three-step
workflow, a gradient CTA panel with a single "Start creating" button, and a footer with a
force-fit SVG outline wordmark (`textLength` + `lengthAdjust="spacing"`). The page owns
its scroll container with hidden scrollbar chrome
(`no-scrollbar`). Motion there is scroll-driven, hover/drag/click interaction, or
reduced-motion-gated ambience. The product-UI rules below apply
everywhere else; do not carry the serif or the marketing sections into the app.

## 2. Tokens

### Colour

| Token                                                                       | Role                                                                                                       |
| --------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `background` / `foreground`                                                 | App surface and text. Off-white / off-black, never pure.                                                   |
| `card` / `popover`                                                          | Raised surfaces (1px `ring-foreground/10`, no heavy shadows).                                              |
| `muted` / `muted-foreground`                                                | Secondary surfaces and text.                                                                               |
| `border` / `input`                                                          | Hairlines and field strokes.                                                                               |
| `primary`                                                                   | The action colour. Blue (`signal`), so buttons, progress, and badges carry colour.                         |
| `signal`                                                                    | The one interactive accent: primary actions, focus rings, active step/nav, links, selected chips.          |
| `destructive`                                                               | Errors and destructive actions.                                                                            |
| `sev-none`, `sev-good`, `sev-low`, `sev-medium`, `sev-high`, `sev-critical` | Severity scale.                                                                                            |
| `heat-green`, `heat-yellow`, `heat-orange`, `heat-red`                      | Heatmap bins per the contract (score ≥8 green, 6–7.99 yellow, 4–5.99 orange, <4 red; critical always red). |

Rule: never introduce a colour outside this list. Severity colour is data, not decoration.

### Type

- **UI:** Schibsted Grotesk (`font-sans`, also `font-heading`).
- **Data:** Geist Mono via the `.tabular` utility — timestamps, scores, IDs, step numbers.
  Always tabular figures.
- Headings: `font-heading` (Geist), `tracking-tight`.
- Body copy: `text-sm`, `text-muted-foreground`, max `65ch`.

### Shape & space

- Radius: `--radius: 0.625rem`. Controls (`button`, `input`, `select`) ≈ 10px; surfaces
  (`card`) ≈ 14px. Do not mix in pill or square corners.
- Spacing: 4px base. Page padding `px-6 py-6` (desktop `px-8 py-8`). Section gaps `space-y-8`.
- Elevation: prefer `ring-1 ring-foreground/10` + borders over drop shadows.

### Modes

Light and dark are both first-class. `next-themes` sets `.dark` from system preference; the
user menu offers Light / Dark / System. Test both before shipping. No pure `#000`/`#fff`.

## 3. Conventions

- Icons: **Hugeicons** (`@hugeicons/core-free-icons`) rendered through the `Icon` wrapper in
  `components/common/icon.tsx`, which standardises size and stroke width. Never hand-roll icon
  paths. The only inline SVG allowed is the Google brand mark on the sign-in button.
- No emoji in UI.
- Loading: skeleton or `Spinner`, never a bare "Loading…". Errors: inline, plain language,
  say what happened and what to do. Empty states: `Empty` with an action.
- Motion is minimal and motivated (opacity/transform, respects reduced motion). No infinite
  ambient loops.
- Copy: sentence case, active voice, one label per action, same name through the flow.

## 4. Future component inventory

Derived from `docs/technical-design/frontend-plan.md`. Status as of the onboarding build.

**Built**

- Landing: `LandingPage` (centered hero, `LandingBackground`), `GoogleSignInButton`
- Auth: `AuthLoadingScreen`, `AuthProvider`, `RequireAuth`, `RequireOnboarded`
- Shell: `AppShell`, sidebar, `UserMenu`, `Logo`, `PageHeader`, `CenteredScreen`
- Onboarding: `OnboardingFlow` (also serves edit mode), `StepRail`, Welcome / Identity / Topics / Audience / Style / Platforms / Persona / Done
- Profile: `ProfilePage` with read-only `PersonaText`, `Edit persona` → `/persona` (same steps, prefilled, returns to profile), and account deletion
- Projects: `ProjectsPage`, `CreateProjectDialog`, `ProjectCard`, `ProjectStatusBadge`, `ProjectWorkspace` (upload + processing state; timeline/heatmap next)
- Upload: `VideoDropzone` (validate + signed-URL upload + progress), `ProcessingStatusCard`
- Common: `Icon`, `ChipSelect`, `PersonaText`, `Empty`, `Spinner`, `Progress`, `Dialog`

**Next**

- Auth: `EmailSignInForm` (needs the Email/Password provider enabled in Firebase)
- Shell: `Breadcrumbs`, `LoadingState`, `ErrorState`, `ToastProvider` (sonner is mounted; a provider wrapper is not), `ConfirmDialog`, `JobProgressBanner`
- Dashboard: `RecentProjectList`, `ConnectionStatusCard`, `AudienceSummaryCard`
- Upload: `VideoFilePicker`, `UploadValidationError`, `UploadCompleteState`
- Workspace: `VideoPreviewPanel`, `TimelinePanel`, `VideoTimeline`, `TranscriptTrack`, `HeatmapTracks`, `FindingDetailsPanel`, `ProjectAssistantPanel`
- Timeline: `VideoPlayer`, `TimelineRuler`, `TranscriptSegment`, `WordHighlight`, `HeatmapTrack`, `HeatmapBin`, `FindingPopover`, `FindingDrawer`, `JumpToTimestampButton`, `DeepReviewButton`
- Analysis: `AnalysisToolbar`, `DimensionFilter`, `SeverityFilter`, `AnalysisRunSelector`, `ReviewerStatusList`, `OverallScoreCard`
- Artifacts: `ArtifactGallery`, `ArtifactCard`, `ArtifactTypeFilter`, `ArtifactPreviewModal`, `DownloadButton`, `RegenerateDialog`, `DeleteArtifactDialog`
- Localization: `LanguageSelector`, `LocalizationOptions`, `GlossaryEditor`, `CorpusVersionBadge`, `CaptionPreview`, `DubbedVideoPreview`, `LocalizationComparisonView`
- Connections / Audience: `ConnectionsPage`, `PlatformConnectionCard`, `OAuthRedirectHandler`, `SyncNowButton`, `SyncHistoryTable`, `AudienceInsightsPage`, `AudienceSummaryChart`, `ContentPerformanceTable`, `SentimentBreakdown`
- Chat: `ChatThreadList`, `ChatMessageList`, `ChatComposer`, `StreamingMessage`, `SuggestedPromptChips`, `ToolResultCard`, `ArtifactAttachmentCard`, `CitationList`
- Settings: `PersonaPage`, `SettingsPage`

## 5. Where things live

```
src/
  app/
    page.tsx              landing page (centered hero + sign-in)
    (onboarding)/onboarding  focused onboarding route (no app chrome)
    (onboarding)/persona  persona edit (same steps, prefilled)
    (app)/dashboard       authed app shell
    (app)/projects        project list + create
    (app)/projects/view   project workspace (static export: projectId is a query param)
    (app)/profile         account + persona + delete
  components/
    ui/                   shadcn primitives (Base UI based) — edit sparingly
    common/               brand + shared primitives (Logo, Icon, PageHeader, ChipSelect, …)
    auth/                 auth provider, guards, sign-in button
    landing/              landing page + atmospheric background
    layout/               app shell, sidebar, user menu
    onboarding/           flow, rail, steps
  lib/
    api-client.ts         fetch with Firebase bearer token
    firebase.ts           Firebase app/auth
    onboarding.ts         step metadata, option lists, answer slicing
    types.ts              contract types (Me, Persona, OnboardingState)
```

## 6. Adding a component

1. Check this inventory and the frontend plan first; reuse before adding.
2. `bunx --bun shadcn@latest add <name>` for primitives; restyle only via tokens.
3. Prefer `components/common` for cross-feature pieces, feature folders for the rest.
4. Every async action needs loading, empty, error, and retry states.

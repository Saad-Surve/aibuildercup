# Resonance web

Next.js 16 App Router, React 19, TypeScript, TanStack Query, Tailwind and Base UI.
Bun is the package manager. Production is a static export served by Firebase Hosting.

## Run

```bash
bun install
cp .env.example .env.local
bun dev
```

Open `http://localhost:3000`; start the API on port 8080 using the
[backend guide](../backend/README.md). The example includes public Firebase identifiers.
Set `NEXT_PUBLIC_API_BASE_URL` to the API prefix, e.g. `http://localhost:8080/api`.
Production WebSockets use the direct Cloud Run URL because Hosting API rewrites do not
proxy WebSocket upgrades. Only public configuration belongs in `NEXT_PUBLIC_*` variables.

## Workspace

| Route | Purpose |
|---|---|
| `/` | Landing page and Google/read-only demo sign-in |
| `/onboarding`, `/persona` | Creator preferences, grounded profile research and persona review |
| `/dashboard`, `/projects` | Video/draft projects and upload/create dialogs |
| `/projects/view/project/{id}/{module}` | Shared project shell: review, transcript, captions, packaging, localization and publishing |
| `/library` | Semantic source map, search, evidence inspector and related material |
| `/calendar` | Month/week schedules |
| `/settings`, `/profile` | Account connections, persona/account controls and avatar |
| `/privacy`, `/terms`, `/data-deletion` | Product policy pages |

Video projects keep the player visible while modules change. Drafts have a versioned
editor, writing chat and alternatives. Project events update React Query over a shared
WebSocket; query caches are cleared when authentication changes. Video/draft workspaces
and avatar artwork load separately. Review includes editor/rubric results, footage checks,
creator decisions, earlier-work examples, rough-cut preview/activation/discard and before/after
re-review comparison. Draft generation/chat can use linked video context; drafts can cross-post
to Substack, Medium and Reddit. YouTube publishing exposes attachment warnings.

All HTTP calls pass through `src/lib/api-client.ts`. Feature-specific TypeScript interfaces
are maintained in `src/lib/types.ts` and must match [OpenAPI](../contracts/openapi.yaml);
there is no code-generation command in the current package scripts.

## Verify and build

```bash
bun run lint
bun run lint:eslint
bun run build
bun run format:check
```

The build exports `out/`. Next rewrites do not apply to static hosting; matching project
shell/API rewrites are in `../firebase.json`. The build's static-export rewrite warning
is expected. Read the bundled Next docs under `node_modules/next/dist/docs/` before
changing framework code; the repository's `AGENTS.md` explains the version-specific rules.

[Architecture](../docs/architecture.md), [benchmarks](../evals/README.md) and
[frontend reference](../docs/technical-design/frontend-plan.md) describe implementation
and limits. Landing-page illustrations are demonstrations, not benchmark results or proof
of live verification.

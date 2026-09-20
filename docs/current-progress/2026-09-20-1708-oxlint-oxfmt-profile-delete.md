# Progress — 2026-09-20 17:08 IST

Status: **oxlint/oxfmt added, onboarding progress bar de-duplicated, persona is read-only text,
profile page with account deletion built and wired. Ready to commit.**

## 1. What I did

### Tooling (web)

- Added `oxlint@1.83` and `oxfmt@0.68` as dev dependencies.
- `.oxlintrc.json`: typescript/unicorn/oxc/react/jsx-a11y/import plugins, `correctness: error`,
  `suspicious: warn`. Disabled `react/react-in-jsx-scope` (new JSX transform),
  `jsx-a11y/prefer-tag-over-role`, `jsx-a11y/label-has-associated-control` (false positives on
  shadcn primitives), `import/no-unassigned-import` (CSS side-effect imports).
- `.oxfmtrc.json`: 80 cols, semicolons, double quotes, trailing commas; ignores `.next`,
  `node_modules`, `public`, `bun.lock`.
- Scripts: `lint` = `oxlint`, `lint:eslint` = `eslint`, `format` = `oxfmt`,
  `format:check` = `oxfmt --check`. Ran `oxfmt` across `src/` (formatted 34+ files, mostly the
  generated shadcn primitives).
- Updated `AGENTS.md` web commands.

### Fixes

- **Duplicate onboarding progress bar**: `Progress` already renders its own track/indicator; I
  was also passing `<ProgressTrack><ProgressIndicator/></ProgressTrack>` as children, producing
  two bars. Now `<Progress value={percent} />`.
- **Persona is no longer an editable Markdown textarea.** `PersonaStep` shows the persona as
  plain readable text via a new `PersonaText` component (renders headings/bullets/paragraphs,
  strips `**`). To change it, the user goes back and edits the answers; leaving the platforms
  step regenerates the persona from the current answers.
- **Base UI runtime error in the user menu**: `DropdownMenuLabel` / `DropdownMenuRadioGroup`
  must live inside `DropdownMenuGroup`. Wrapped them; this was throwing
  "MenuGroupContext is missing" and forcing full reloads.

### Profile page + account deletion

Backend:

- `contracts/openapi.yaml`: added `DELETE /me` (204, permanent).
- `app/auth/firebase.py`: `delete_user(uid)`.
- `FirestoreClient` protocol: `delete_document_tree(path)`; real impl uses
  `Client.recursive_delete`, fake deletes the subtree.
- `UserService.delete_account(uid)`.
- `dependencies.get_identity_deleter()` (injectable so tests can override the Firebase call).
- `app/api/users.py`: `DELETE /me` deletes Firestore data first, then the Auth account
  (idempotent on retry). `tests/test_users_api.py` covers create, delete, and 401.

Frontend:

- `src/app/(app)/profile/page.tsx`: account summary, read-only persona (via `PersonaText`),
  and a danger zone with an `AlertDialog` confirmation that calls `DELETE /me`, signs out, and
  returns to `/login`.
- Added shadcn `alert-dialog`. Sidebar nav: `Profile` is now ready (replaces the placeholder
  `Persona` item).

## 2. Verification

- Backend: `pytest` **61 passed**, `ruff` clean, `mypy` clean.
- Web: `oxlint` exit 0, `eslint` clean, `oxfmt` applied, `bun run build` clean with routes
  `/`, `/login`, `/onboarding`, `/dashboard`, `/profile`.
- Backend restarted: `/healthz` ok, `DELETE /me` without a token → 401, runtime OpenAPI shows
  both `get` and `delete` on `/me`.

## 3. Gotchas

- `shadcn add` prompts before overwriting an existing file even with `-y`; pipe `n` to keep
  files (`printf 'n\n' | bunx ... add <name> -y`).
- Base UI menu/select parts have grouping requirements that Radix did not. Always wrap
  `DropdownMenuLabel` in `DropdownMenuGroup`, and radio items in `DropdownMenuRadioGroup`.

## 4. Not done / next step

- User to confirm the profile delete flow in the browser (it deletes the real Firebase account,
  so it should be a deliberate click).
- Onboarding + persona verification after the storage-path fix from the previous note.
- Next build: dashboard/project list + upload flow, then the transcript + heatmap workspace.
- `web/DESIGN.md` still holds the component inventory checklist.

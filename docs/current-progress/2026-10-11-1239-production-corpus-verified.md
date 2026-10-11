# New-account corpus loading verified in production

- Fix commit `f85f705` was pushed to main. Deployment run `38120282255` succeeded; Cloud Run ready revision is `creator-studio-api-00108-9ck`. Diagnostic logging commit `b2ecd2b` is included.
- Created a fresh temporary Firebase account through normal custom-token sign-in. Production `/api/me` returned 200; first `/api/creator-library` returned 200 with Arun Prabhudesai, 20 source items, 80/80 Gemini Embedding 2 nodes, ten image nodes, and no error.
- A real signed thumbnail URL returned 200. A second library read returned the complete 80-node installed corpus again.
- Production account deletion returned 204 and its Firestore root was confirmed absent. Runtime and local batch verification data were also removed; no token was stored. Shared corpus remains available for new users.
- Library initialization occurs on the first library read, not at Firebase account creation. Intended flow: create account, finish own persona, continue through Connections (YouTube can be skipped), then open Creator library. Flag is enabled in the backend; no connector login is required for this public snapshot. It does not create seeded projects or video analyses.
- Firestore vector installation now uses eight-document transactions because generated array indexes made the previous 80-vector transaction exceed the server size limit. Ownership is rechecked per batch; completion markers follow successful installation. No API/schema changes.
- Ruff, mypy (127 app files), and diff checks passed. Existing CI performed the container deployment; no tests, ESLint, or local full builds were added/run.
- Hosting `/library` returns 200. Use the normal navigation URL without a trailing slash.
- Preserve unrelated `fixtures/seed/.gitkeep` deletion and integration research notes.

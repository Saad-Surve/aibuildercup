# Reduce creator vector installation transaction size

- Runtime-service-account verification reproduced the production failure: Firestore reported `Transaction too big. Decrease transaction size.` while committing 80 vector documents.
- Firestore accounts for generated array index entries as well as document payloads. The previous 400-document bound did not guarantee a safe transaction byte size.
- `set_owned_children` now uses eight-document transactions, checking user and source ownership/existence before every batch. Stable IDs permit retries; preset completion markers are written only after every batch succeeds. No endpoint or stored schema changes.
- Diagnostic verification data was removed. A full library read with the new batching is running; production redeployment/recheck follows.
- Ruff and mypy passed; diff whitespace checks passed. No tests or local web build.
- Previous feature deployment and diagnostic deployment both succeeded; the flag remains enabled.

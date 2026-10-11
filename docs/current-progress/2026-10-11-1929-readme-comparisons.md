# README rewrite: standalone submission with comparisons inline

## Work and structural changes

- Rewrote `README.md` end to end as a standalone submission: problem, what it does, how
  the AI works, embedding philosophy, Google Cloud architecture, evidence, comparisons,
  limitations, run and repository.
- Brought the competitive material into the README as a first-class section
  (`## How Resonance compares`) instead of only linking it: a five-row capability table
  (Descript, OpusClip, YouTube Studio/Ask Studio, ChatGPT, Gemini Apps), an explicit
  "where the other tool is stronger" column, price context, and a "what we claim / what we
  do not" close. Links to the full `docs/competitive-comparison.md` and the
  `evals/creator-comparison.md` protocol.
- Added a `## The embedding philosophy` section that keeps roles distinct (persona =
  preferences, past work = examples, neither = fact) and states plainly that heatmap
  reviewers and inline alternatives do not yet use semantic retrieval.
- Kept all measured numbers and their scope unchanged: retrieval 20/20 vs 11/20
  (MRR 1.000 vs 0.598), probe 49.9–50.4%, embedding median/p95, cosine/PCA medians,
  54% JS, and the $0.1475 / $0.4155 / $0.65925 cost subtotals.

## What changed structurally

- No contracts, schema, infra or code changed. `README.md` and `docs/competitive-comparison.md`
  only, plus this note.
- No external project is named in the submission docs. The comparison is against
  established commercial/consumer creator tools only. Prior research notes that cite an
  external repository as a design source are left untouched as internal provenance; they
  are not part of the submission surface.

## Decisions and gotchas

- Kept the repo's no-overclaim discipline: the comparison is a capability comparison, not
  a benchmark, and the README still says the retrieval result compares Resonance's own
  semantic search against its own lexical fallback.
- README links verified: no broken relative targets and no inconsistent Markdown tables.

## Not done / next step

- Committed and pushed to `main` under the user's explicit request.
- Nothing was deployed. The live app may lag the working tree.

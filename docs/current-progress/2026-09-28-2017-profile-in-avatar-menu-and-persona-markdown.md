# Move Profile into the avatar menu; fix persona Markdown rendering

## What I did

### Profile: sidebar → avatar dropdown

- `components/layout/app-shell.tsx` — removed the `Profile` entry from `NAV` (and the now
  unused `UserIcon` import). This drops it from both the desktop rail and the mobile top nav.
- `components/layout/user-menu.tsx` — added a `Profile` item (links to `/profile`) in the
  top-right avatar dropdown, between the account block and the Theme group.

### Persona Markdown was rendering badly

The profile persona card and the onboarding persona step both render through
`components/common/persona-text.tsx`, a small hand-written Markdown subset renderer. It broke
on the Markdown an LLM actually emits (the persona is generated via the LLM with a template
fallback):

1. **Loose lists.** A blank line flushed the current list, so a list written with a blank line
   between items became one list *per item* — and every ordered item then rendered as `1.`
   (a section that should read 1./2./3. showed 1./1./1.).
2. **Inline links.** `[the RBI](https://rbi.org.in)` is not in the inline grammar, so the raw
   Markdown source was shown verbatim.
3. **Bold section headers.** Models often write `**Identity**` on its own line instead of
   `## Identity`; that rendered as a plain bold paragraph, flattening the whole document.
4. **Nested lists** were flattened (indentation dropped).
5. `####`+ headings fell through to a paragraph.

Fixes in the renderer:

- Blank lines no longer flush a list; a list is only closed by a heading, rule, or paragraph.
  Ordered items keep their real number (`1.`/`2.`/`3.`).
- Inline links render as anchors. Only `http(s):`, `mailto:`, root-relative, and `#` hrefs are
  emitted; anything else stays plain text.
- A line that is only bold text (optional trailing colon) is treated as a level-2 heading.
- Nested items keep a `depth` and are indented (`pl-5`).
- Headings accept `#`–`######` and clamp to three visual levels.
- Horizontal rules (`---`, `***`, `___`) render as `<hr>`.
- Underscore emphasis now requires a non-word boundary on both sides, so `snake_case` is no
  longer mangled into italics.

## Structural changes

UI only. No contract, schema, or backend changes. The renderer is still intentionally a
subset, not CommonMark.

## What I decided / discovered

- The deterministic template persona rendered fine; the breakage only shows for
  LLM-generated personas that use loose lists, bold pseudo-headings, and links. Because the
  template is the fallback, the bug was invisible in template-only test data.
- Verified by running the real component through `react-dom/server`'s `renderToStaticMarkup`
  against representative samples; the temporary probe script was deleted.

## Verification

- `bun run lint` — clean. `bunx tsc --noEmit` — clean. `bun run build` — passes.

## Not done / next step

- Not committed (the user did not ask this time). Say the word and I'll commit + push.
- Optional: replace the hand-written subset with a real CommonMark renderer if personas start
  emitting tables, blockquotes, or images.

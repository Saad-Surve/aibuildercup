"use client";

import { dimensionLabel } from "@/lib/analysis";
import type { EditorSummary, ReviewerRun } from "@/lib/types";

/*
 * Web grounding for the truth reviewer. Shows the search queries it ran and the
 * sources it used, plus Google's Search Suggestions.
 *
 * The suggestions HTML is supplied by the API and Google's terms for Grounding with
 * Google Search require it to be rendered exactly as provided, hence the raw injection.
 * It is model/Google output, never user content.
 */

export function GroundingPanel({
  reviewers,
  editor,
}: {
  reviewers: ReviewerRun[];
  editor?: EditorSummary | null;
}) {
  const grounded = reviewers.filter(
    (reviewer) =>
      (reviewer.groundingQueries?.length ?? 0) > 0 ||
      (reviewer.groundingSources?.length ?? 0) > 0 ||
      Boolean(reviewer.groundingSearchSuggestions),
  );
  if (
    grounded.length === 0 &&
    !editor?.searchQueries.length &&
    !editor?.searchSuggestions
  )
    return null;

  // Search Suggestions stay outside the scrolling region so they are always visible.
  const suggestions = [
    editor?.searchSuggestions,
    ...grounded.map((reviewer) => reviewer.groundingSearchSuggestions),
  ].filter((html): html is string => Boolean(html));

  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <div className="px-3 py-2 text-sm break-words">
        Grounded with Google Search
        <span className="ml-1.5 text-muted-foreground">
          — claims checked against sources
        </span>
      </div>
      <div className="max-h-64 space-y-3 overflow-y-auto border-t border-border p-3">
        {editor &&
          (editor.searchQueries.length > 0 || editor.searchSuggestions) && (
            <div className="space-y-1.5">
              <p className="text-xs text-muted-foreground">Editor</p>
              <div className="flex flex-wrap gap-1.5">
                {editor.searchQueries.map((query, index) => (
                  <span
                    key={index}
                    className="rounded-4xl bg-muted px-2 py-0.5 text-[11px] text-muted-foreground"
                  >
                    {query}
                  </span>
                ))}
              </div>
            </div>
          )}
        {grounded.map((reviewer) => (
          <div key={reviewer.reviewerRunId} className="space-y-1.5">
            <div className="text-xs text-muted-foreground">
              {dimensionLabel(reviewer.dimension)}
            </div>
            {reviewer.groundingQueries.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {reviewer.groundingQueries.map((query) => (
                  <span
                    key={query}
                    className="rounded-4xl bg-muted px-2 py-0.5 text-[11px] text-muted-foreground"
                  >
                    {query}
                  </span>
                ))}
              </div>
            )}
            {reviewer.groundingSources.length > 0 && (
              <ul className="space-y-0.5">
                {reviewer.groundingSources.map((source) => (
                  <li
                    key={source.url || source.title}
                    className="truncate text-xs"
                  >
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-signal underline-offset-2 hover:underline"
                    >
                      {source.title || source.url}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </div>
      {suggestions.length > 0 && (
        <div className="space-y-2 border-t border-border p-3">
          {suggestions.map((html, index) => (
            <div
              key={index}
              className="overflow-hidden break-words [&_*]:max-w-full"
              dangerouslySetInnerHTML={{ __html: html }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

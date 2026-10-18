"use client";

import { GlobalSearchIcon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { DraftGrounding } from "@/lib/types";

/*
 * Web grounding for the draft writer: the searches it ran, the sources it used, and Google's
 * Search Suggestions. Google's terms for Grounding with Google Search require the suggestions
 * HTML to be rendered exactly as provided, hence the raw injection. It is model/Google output,
 * never user content.
 */

export function DraftGroundingPanel({
  grounding,
}: {
  grounding: DraftGrounding | null;
}) {
  if (!grounding) return null;
  const hasSources = grounding.sources.length > 0;
  if (
    !hasSources &&
    grounding.queries.length === 0 &&
    !grounding.searchSuggestions
  ) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon icon={GlobalSearchIcon} className="text-signal" />
          Grounded with Google Search
        </CardTitle>
        <CardDescription>
          Facts the writer checked on the web while working on this draft.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="max-h-64 space-y-3 overflow-y-auto rounded-lg border border-border p-3">
          {grounding.queries.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {grounding.queries.map((query) => (
                <span
                  key={query}
                  className="rounded-4xl bg-muted px-2 py-0.5 text-[11px] text-muted-foreground"
                >
                  {query}
                </span>
              ))}
            </div>
          ) : null}

          {hasSources ? (
            <ul className="space-y-0.5">
              {grounding.sources.map((source) => (
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
          ) : null}
        </div>

        {grounding.searchSuggestions ? (
          <div
            className="overflow-hidden break-words [&_*]:max-w-full"
            dangerouslySetInnerHTML={{ __html: grounding.searchSuggestions }}
          />
        ) : null}
      </CardContent>
    </Card>
  );
}

"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckmarkBadge01Icon,
  LanguageSquareIcon,
  Loading03Icon,
} from "@hugeicons/core-free-icons";
import { toast } from "sonner";

import { Icon } from "@/components/common/icon";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api-client";
import { getGlobalCorpus, getGlossary, putGlossary } from "@/lib/dubbing";
import type { GlossaryTerm } from "@/lib/types";
import { WORKSPACE_SNAP_TARGET } from "@/lib/workspace";

function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return fallback;
}

function formatTerms(terms: GlossaryTerm[]): string {
  return terms.map((term) => `${term.source} = ${term.target}`).join("\n");
}

/** One `source = target` term per line; the first `=` splits the two sides. */
function parseTerms(text: string): GlossaryTerm[] {
  const terms: GlossaryTerm[] = [];
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const index = trimmed.indexOf("=");
    if (index <= 0) continue;
    const source = trimmed.slice(0, index).trim();
    const target = trimmed.slice(index + 1).trim();
    if (source && target) {
      terms.push({ source, target, targetLanguage: "" });
    }
  }
  return terms;
}

/**
 * The project glossary: the creator's own terms, enforced verbatim during the localization
 * adaptation pass. Free-text, one `source = target` per line, so nothing has to be learned.
 * The global corpus version and covered language pairs are shown for context.
 */
export function GlossaryEditor({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<string | null>(null);

  const glossaryQuery = useQuery({
    queryKey: ["glossary", projectId],
    queryFn: () => getGlossary(projectId),
    retry: false,
  });

  const corpusQuery = useQuery({
    queryKey: ["global-corpus"],
    queryFn: getGlobalCorpus,
    staleTime: Infinity,
    retry: false,
  });

  const terms = glossaryQuery.data?.terms ?? [];
  const value = draft ?? formatTerms(terms);
  const parsed = parseTerms(value);
  const dirty = draft !== null && draft !== formatTerms(terms);

  const saveMutation = useMutation({
    mutationFn: () =>
      putGlossary(projectId, {
        sourceLanguage: glossaryQuery.data?.sourceLanguage ?? "en",
        terms: parsed,
        expectedVersion: glossaryQuery.data?.version ?? 0,
      }),
    onSuccess: (saved) => {
      setDraft(null);
      queryClient.setQueryData(["glossary", projectId], saved);
      void queryClient.invalidateQueries({
        queryKey: ["localizations", projectId],
      });
      toast.success("Glossary saved", {
        description: `${saved.terms.length} term${
          saved.terms.length === 1 ? "" : "s"
        } · version ${saved.version}`,
      });
    },
    onError: (error) => {
      toast.error(errorMessage(error, "Could not save the glossary."));
      void queryClient.invalidateQueries({
        queryKey: ["glossary", projectId],
      });
    },
  });

  const pairCount = corpusQuery.data?.pairs.length ?? 0;

  return (
    <Card className={WORKSPACE_SNAP_TARGET}>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2">
            <Icon icon={LanguageSquareIcon} className="text-muted-foreground" />
            Project glossary
          </CardTitle>
          <div className="flex flex-wrap items-center gap-1.5">
            {glossaryQuery.data ? (
              <Badge variant="outline">Version {glossaryQuery.data.version}</Badge>
            ) : null}
            {corpusQuery.data ? (
              <Badge variant="secondary">
                Corpus v{corpusQuery.data.version} · {pairCount} pair
                {pairCount === 1 ? "" : "s"}
              </Badge>
            ) : null}
          </div>
        </div>
        <CardDescription>
          Your own terms, kept verbatim when the transcript is translated. One{" "}
          <code className="text-foreground">source = target</code> per line. Names and
          product terms the whole audience should see the same way belong here.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {glossaryQuery.isLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Icon icon={Loading03Icon} className="animate-spin" />
            Loading glossary…
          </div>
        ) : (
          <>
            <Textarea
              value={value}
              onChange={(event) => setDraft(event.target.value)}
              rows={6}
              spellCheck={false}
              placeholder={"credit score = क्रेडिट स्कोर\nfinancial freedom = आर्थिक आज़ादी"}
              aria-label="Project glossary terms"
            />
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs text-muted-foreground">
                {parsed.length} term{parsed.length === 1 ? "" : "s"}
                {glossaryQuery.data?.sourceLanguage
                  ? ` · source ${glossaryQuery.data.sourceLanguage}`
                  : null}
              </span>
              <Button
                type="button"
                size="sm"
                disabled={!dirty || saveMutation.isPending}
                onClick={() => saveMutation.mutate()}
              >
                <Icon
                  icon={saveMutation.isPending ? Loading03Icon : CheckmarkBadge01Icon}
                  className={saveMutation.isPending ? "animate-spin" : undefined}
                />
                {saveMutation.isPending ? "Saving…" : "Save glossary"}
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

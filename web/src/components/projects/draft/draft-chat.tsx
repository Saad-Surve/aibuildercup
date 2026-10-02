"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  AiChat01Icon,
  Cancel01Icon,
  Loading03Icon,
  SendIcon,
  SparklesIcon,
  UserIcon,
} from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { WORKSPACE_PANE_HEIGHT } from "@/lib/workspace";
import type { DraftMessage } from "@/lib/types";

/**
 * Suggestions follow the state of the draft: an empty document needs an opening,
 * a full one needs tightening, and a selection needs rewriting.
 */
function suggestionsFor(hasContent: boolean, contextText: string): string[] {
  if (contextText.trim()) {
    return [
      "Rewrite the selection",
      "Make the selection punchier",
      "Give three alternatives for the selection",
    ];
  }
  if (hasContent) {
    return [
      "Sharpen the opening line",
      "Make it more concrete",
      "Cut the filler",
      "Add a call to action",
    ];
  }
  return [
    "Write an opening paragraph",
    "Outline three sections",
    "Draft a hook",
  ];
}

export function DraftChat({
  messages,
  pending,
  contextText,
  onClearContext,
  hasContent,
  onSend,
}: {
  messages: DraftMessage[];
  pending: boolean;
  contextText: string;
  onClearContext: () => void;
  hasContent: boolean;
  onSend: (message: string) => void;
}) {
  const [value, setValue] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const suggestions = useMemo(
    () => suggestionsFor(hasContent, contextText),
    [hasContent, contextText],
  );

  useEffect(() => {
    const element = scrollRef.current;
    if (element) element.scrollTop = element.scrollHeight;
    // Re-run only when the conversation changes; the ref is read inside.
    // oxlint-disable-next-line react/exhaustive-effect-dependencies
  }, [messages.length, pending]);

  function submit() {
    const message = value.trim();
    if (!message || pending) return;
    setValue("");
    onSend(message);
  }

  return (
    <Card
      className={`${WORKSPACE_PANE_HEIGHT} flex min-h-0 flex-col lg:sticky lg:top-20 lg:max-h-none lg:h-[min(78vh,44rem)]`}
    >
      <CardHeader className="shrink-0 border-b">
        <CardTitle className="flex items-center gap-2">
          <Icon icon={AiChat01Icon} className="text-muted-foreground" />
          Writing partner
        </CardTitle>
      </CardHeader>

      <CardContent
        ref={scrollRef}
        className="scroll-fade-y min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-y-contain py-(--card-spacing)"
      >
        {messages.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Ask for a rewrite, a shorter cut, or a different angle. Every change
            is saved as a new version you can compare.
          </p>
        ) : null}

        {messages.map((message) => (
          <div
            key={message.messageId}
            className={
              message.role === "user"
                ? "flex justify-end gap-2"
                : "flex justify-start gap-2"
            }
          >
            {message.role === "assistant" ? (
              <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                <Icon icon={SparklesIcon} className="size-3.5" />
              </span>
            ) : null}
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
                message.role === "user"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-foreground"
              }`}
            >
              {message.content}
            </div>
            {message.role === "user" ? (
              <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                <Icon icon={UserIcon} className="size-3.5" />
              </span>
            ) : null}
          </div>
        ))}

        {pending ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Icon
              icon={Loading03Icon}
              className="size-3.5 animate-spin text-signal"
            />
            Thinking…
          </div>
        ) : null}
      </CardContent>

      <div className="shrink-0 space-y-3 border-t p-(--card-spacing)">
        {contextText.trim() ? (
          <div className="flex items-start gap-2 rounded-lg border border-signal/40 bg-signal/5 px-2.5 py-1.5 text-xs">
            <span className="min-w-0 flex-1 text-foreground/90">
              <span className="text-muted-foreground">Context: </span>
              {contextText.length > 140
                ? `${contextText.slice(0, 140)}…`
                : contextText}
            </span>
            <button
              type="button"
              aria-label="Clear context"
              onClick={onClearContext}
              className="mt-0.5 shrink-0 text-muted-foreground hover:text-foreground"
            >
              <Icon icon={Cancel01Icon} className="size-3.5" />
            </button>
          </div>
        ) : null}

        <div className="flex flex-wrap gap-1.5">
          {suggestions.map((suggestion) => (
            <Button
              key={suggestion}
              type="button"
              size="xs"
              variant="outline"
              disabled={pending}
              onClick={() => setValue(suggestion)}
            >
              {suggestion}
            </Button>
          ))}
        </div>
        <div className="flex items-end gap-2">
          <Textarea
            value={value}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            placeholder="Ask for a change…"
            rows={2}
            className="field-sizing-content min-h-9 resize-none"
          />
          <Button
            type="button"
            size="icon"
            aria-label="Send"
            onClick={submit}
            disabled={pending || !value.trim()}
          >
            <Icon icon={SendIcon} />
          </Button>
        </div>
      </div>
    </Card>
  );
}

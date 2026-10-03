"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  AiChat01Icon,
  Cancel01Icon,
  Loading03Icon,
  SendIcon,
  SparklesIcon,
} from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { DisabledReason } from "@/components/common/disabled-reason";
import { UserAvatar } from "@/components/avatar/user-avatar";
import { useAuth } from "@/components/auth/auth-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { useUserAvatar } from "@/lib/avatar";
import { READ_ONLY_REASON } from "@/lib/read-only";
import { cn } from "@/lib/utils";
import { WORKSPACE_PANE_HEIGHT } from "@/lib/workspace";
import type { DraftMessage } from "@/lib/types";

/**
 * Render a chat message with Markdown-style blockquotes: a run of `>` lines
 * becomes a quote (used for the context pulled from the draft), everything else
 * stays plain text.
 */
function MessageBody({
  content,
  role,
}: {
  content: string;
  role: "user" | "assistant";
}) {
  const parts = content.split(/\n{2,}/);
  return (
    <div className="space-y-2">
      {parts.map((part, index) => {
        const lines = part.split("\n");
        if (lines.every((line) => line.startsWith(">") || !line.trim())) {
          const quote = lines
            .map((line) => line.replace(/^>\s?/, ""))
            .join("\n")
            .trim();
          return (
            <blockquote
              key={index}
              className={cn(
                "border-l-2 pl-2.5 text-[0.95em] italic whitespace-pre-wrap opacity-90",
                role === "user"
                  ? "border-primary-foreground/50"
                  : "border-foreground/25",
              )}
            >
              {quote}
            </blockquote>
          );
        }
        return (
          <p key={index} className="whitespace-pre-wrap">
            {part}
          </p>
        );
      })}
    </div>
  );
}

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
  readOnly = false,
}: {
  messages: DraftMessage[];
  pending: boolean;
  contextText: string;
  onClearContext: () => void;
  hasContent: boolean;
  onSend: (message: string) => void;
  readOnly?: boolean;
}) {
  const [value, setValue] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const avatar = useUserAvatar();
  const { profile, user } = useAuth();
  const name = profile?.displayName ?? user?.displayName ?? "You";
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
    if (!message || pending || readOnly) return;
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
                ? "flex items-start justify-end gap-2"
                : "flex items-start justify-start gap-2"
            }
          >
            {message.role === "assistant" ? (
              <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
                <Icon icon={SparklesIcon} className="size-3.5" />
              </span>
            ) : null}
            <div
              className={`min-w-0 break-words rounded-2xl px-3 py-2 text-sm ${
                message.role === "user"
                  ? "max-w-[75%] rounded-br-sm bg-primary text-primary-foreground"
                  : "max-w-[78%] rounded-bl-sm bg-muted text-foreground"
              }`}
            >
              <MessageBody content={message.content} role={message.role} />
            </div>
            {message.role === "user" ? (
              <span className="mt-0.5 shrink-0 rounded-full bg-gradient-to-br from-cyan-400 via-fuchsia-500 to-orange-400 p-[1.5px]">
                <span className="block rounded-full bg-background p-[1.5px]">
                  <UserAvatar state={avatar} size={22} title={name} />
                </span>
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
          <div className="flex items-start gap-2">
            <blockquote className="min-w-0 flex-1 border-l-2 border-signal/50 pl-2.5 text-xs text-muted-foreground italic whitespace-pre-wrap">
              {contextText}
            </blockquote>
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
            readOnly={readOnly}
            placeholder={
              readOnly ? "Read-only demo — chatting is disabled" : "Ask for a change…"
            }
            rows={2}
            className="field-sizing-content min-h-9 resize-none"
          />
          <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
            <Button
              type="button"
              size="icon"
              aria-label="Send"
              onClick={submit}
              disabled={pending || !value.trim() || readOnly}
            >
              <Icon icon={SendIcon} />
            </Button>
          </DisabledReason>
        </div>
      </div>
    </Card>
  );
}

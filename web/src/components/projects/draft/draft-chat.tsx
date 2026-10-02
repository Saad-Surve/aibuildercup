"use client";

import { useEffect, useRef, useState } from "react";
import {
  AiChat01Icon,
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

const SUGGESTIONS = [
  "Sharpen the opening line",
  "Make it more concrete",
  "Cut the filler",
  "Add a call to action",
  "Tighten every paragraph",
];

export function DraftChat({
  messages,
  pending,
  onSend,
}: {
  messages: DraftMessage[];
  pending: boolean;
  onSend: (message: string) => void;
}) {
  const [value, setValue] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = scrollRef.current;
    if (element) element.scrollTop = element.scrollHeight;
    // Re-run only when the conversation changes; the refs are read inside.
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
              className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
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
            Rewriting…
          </div>
        ) : null}
      </CardContent>

      <div className="shrink-0 space-y-3 border-t p-(--card-spacing)">
        <div className="flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((suggestion) => (
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

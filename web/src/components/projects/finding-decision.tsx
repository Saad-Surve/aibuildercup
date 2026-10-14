"use client";

import { useEffect, useId, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { useAuth } from "@/components/auth/auth-provider";
import { DisabledReason } from "@/components/common/disabled-reason";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api-client";
import { decideFinding, type FindingList } from "@/lib/analysis";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";
import type { Finding, FindingDecisionInput } from "@/lib/types";

export function FindingDecisionControls({
  projectId,
  analysisRunId,
  finding,
}: {
  projectId: string;
  analysisRunId: string;
  finding: Finding;
}) {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const readOnly = useReadOnly();
  const formId = useId();
  const actionRef = useRef<HTMLTextAreaElement>(null);
  const [editing, setEditing] = useState(false);
  const [action, setAction] = useState("");
  const [note, setNote] = useState("");
  const key = ["analysis-findings", projectId, analysisRunId];
  const mutationKey = ["finding-decisions", projectId, analysisRunId];
  const mutation = useMutation({
    mutationKey,
    mutationFn: (decision: FindingDecisionInput | null) =>
      decideFinding(projectId, analysisRunId, finding.findingId, decision),
    onMutate: async (decision) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient
        .getQueryData<FindingList>(key)
        ?.items.find((item) => item.findingId === finding.findingId);
      queryClient.setQueryData<FindingList>(key, (current) =>
        current
          ? {
              ...current,
              items: current.items.map((item) =>
                item.findingId === finding.findingId
                  ? {
                      ...item,
                      decision: decision
                        ? {
                            ...decision,
                            decidedAt: new Date().toISOString(),
                            decidedBy: user?.uid ?? "",
                          }
                        : null,
                    }
                  : item,
              ),
            }
          : current,
      );
      return { previous };
    },
    onSuccess: (updated) => {
      queryClient.setQueryData<FindingList>(key, (current) =>
        current
          ? {
              ...current,
              items: current.items.map((item) =>
                item.findingId === updated.findingId
                  ? { ...item, decision: updated.decision }
                  : item,
              ),
            }
          : current,
      );
      setEditing(false);
    },
    onError: (error, _decision, context) => {
      toast.error(
        error instanceof ApiError
          ? error.message
          : "Could not save your decision. Please try again.",
      );
      if (!context?.previous) return;
      // Roll back this row only, preserving concurrent decisions on other findings.
      queryClient.setQueryData<FindingList>(key, (current) =>
        current
          ? {
              ...current,
              items: current.items.map((item) =>
                item.findingId === finding.findingId
                  ? { ...item, decision: context.previous?.decision }
                  : item,
              ),
            }
          : current,
      );
    },
    onSettled: () => {
      if (queryClient.isMutating({ mutationKey }) === 1) {
        void queryClient.invalidateQueries({ queryKey: key });
      }
    },
  });
  const disabled = readOnly || mutation.isPending;
  const decision = finding.decision;
  useEffect(() => {
    if (editing) actionRef.current?.focus();
  }, [editing]);

  function beginRevision() {
    mutation.reset();
    setAction(decision?.revisedAction ?? finding.suggestion);
    setNote(decision?.note ?? "");
    setEditing(true);
  }

  return (
    <div className="space-y-2 border-t border-border/60 px-3 py-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span
          className="text-xs text-muted-foreground"
          role="status"
          aria-live="polite"
        >
          {mutation.isPending
            ? "Saving decision…"
            : decision
              ? `You ${decision.status} this finding`
              : "Your decision"}
        </span>
        <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
          <div className="flex flex-wrap gap-1">
            <Button
              size="xs"
              variant={decision?.status === "accepted" ? "secondary" : "ghost"}
              disabled={disabled}
              onClick={() => {
                mutation.reset();
                mutation.mutate({ status: "accepted" });
              }}
            >
              Accept
            </Button>
            <Button
              size="xs"
              variant={decision?.status === "revised" ? "secondary" : "ghost"}
              disabled={disabled}
              onClick={beginRevision}
            >
              Revise
            </Button>
            <Button
              size="xs"
              variant={decision?.status === "dismissed" ? "secondary" : "ghost"}
              disabled={disabled}
              onClick={() => {
                mutation.reset();
                mutation.mutate({ status: "dismissed" });
              }}
            >
              Dismiss
            </Button>
            {decision && (
              <Button
                size="xs"
                variant="ghost"
                disabled={disabled}
                onClick={() => {
                  mutation.reset();
                  mutation.mutate(null);
                }}
              >
                Undo
              </Button>
            )}
          </div>
        </DisabledReason>
      </div>
      {!editing && decision?.revisedAction && (
        <p className="rounded-md bg-signal/5 px-2.5 py-2 text-sm">
          <span className="mb-1 block text-[11px] text-signal">
            Your revised action
          </span>
          {decision.revisedAction}
        </p>
      )}
      {!editing && decision?.note && (
        <p className="text-xs text-muted-foreground">
          Your note: {decision.note}
        </p>
      )}
      {editing && (
        <form
          className="space-y-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (!action.trim() || disabled) return;
            mutation.mutate({
              status: "revised",
              revisedAction: action.trim(),
              ...(note.trim() ? { note: note.trim() } : {}),
            });
          }}
        >
          <label
            htmlFor={`${formId}-action`}
            className="block text-xs font-medium"
          >
            Your proposed action
          </label>
          <Textarea
            id={`${formId}-action`}
            value={action}
            onChange={(event) => setAction(event.target.value)}
            maxLength={4000}
            required
            ref={actionRef}
            disabled={disabled}
          />
          <label
            htmlFor={`${formId}-note`}
            className="block text-xs text-muted-foreground"
          >
            Note (optional)
          </label>
          <Textarea
            id={`${formId}-note`}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            maxLength={2000}
            disabled={disabled}
            className="min-h-12"
          />
          <div className="flex gap-2">
            <Button
              size="xs"
              type="submit"
              disabled={disabled || !action.trim()}
            >
              Save revision
            </Button>
            <Button
              size="xs"
              variant="ghost"
              type="button"
              disabled={mutation.isPending}
              onClick={() => setEditing(false)}
            >
              Cancel
            </Button>
          </div>
        </form>
      )}
      {mutation.isError && (
        <p role="alert" className="text-xs text-destructive">
          {mutation.error instanceof ApiError
            ? mutation.error.message
            : "Could not save your decision. Please try again."}
        </p>
      )}
    </div>
  );
}

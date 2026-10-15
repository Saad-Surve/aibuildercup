"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Delete02Icon, Edit02Icon } from "@hugeicons/core-free-icons";

import { useAuth } from "@/components/auth/auth-provider";
import { AvatarEditorDialog } from "@/components/avatar/avatar-customizer";
import { Icon } from "@/components/common/icon";
import { DisabledReason } from "@/components/common/disabled-reason";
import { PageHeader } from "@/components/common/page-header";
import { PersonaText } from "@/components/common/persona-text";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, apiFetch } from "@/lib/api-client";
import { READ_ONLY_REASON, useReadOnly } from "@/lib/read-only";
// import { cn } from "@/lib/utils";
import type { Persona } from "@/lib/types";

function describe(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

/*
function Row({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-2.5">
      <dt className="text-muted-foreground">{label}</dt>
      <dd
        className={cn(
          "max-w-[60%] truncate text-right font-medium",
          mono && "tabular",
        )}
      >
        {value}
      </dd>
    </div>
  );
}
*/

export default function ProfilePage() {
  const { signOut } = useAuth();
  const router = useRouter();

  const personaQuery = useQuery({
    queryKey: ["persona"],
    queryFn: () => apiFetch<Persona>("/persona"),
  });
  const persona = personaQuery.data;
  const personaError = personaQuery.error ? describe(personaQuery.error) : null;
  const loadingPersona = personaQuery.isLoading;

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const readOnly = useReadOnly();

  async function deleteAccount() {
    setDeleting(true);
    setDeleteError(null);
    try {
      await apiFetch("/me", { method: "DELETE" });
      await signOut();
      router.replace("/");
    } catch (caught) {
      setDeleteError(describe(caught));
      setDeleting(false);
      setConfirmOpen(false);
    }
  }

  // const name = profile?.displayName ?? user?.displayName ?? "Creator";
  // const email = profile?.email ?? user?.email ?? "—";

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="Profile"
        description="Your account and the persona the reviewers score against."
      />

      {/*
      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
          <CardDescription>Managed by your Google sign-in.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="divide-y text-sm">
            <Row label="Name" value={name} />
            <Row label="Email" value={email} />
            <Row
              label="User ID"
              value={profile?.uid ?? user?.uid ?? "—"}
              mono
            />
            <Row
              label="Onboarding"
              value={profile?.onboardingCompleted ? "Completed" : "In progress"}
            />
            <Row
              label="Persona version"
              value={profile?.personaVersion?.toString() ?? "—"}
              mono
            />
            <Row
              label="Timezone"
              value={profile?.preferences.timezone ?? "UTC"}
            />
          </dl>
        </CardContent>
      </Card>
      */}

      <Card>
        <CardHeader>
          <CardTitle>Avatar</CardTitle>
          <CardDescription>
            A hand-drawn Humation avatar, saved to your account and shown in the
            header.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AvatarEditorDialog />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Creator persona</CardTitle>
          <CardDescription>
            Generated from your onboarding answers.
          </CardDescription>
          {persona ? (
            <CardAction>
              <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => router.push("/persona")}
                  disabled={readOnly}
                >
                  <Icon icon={Edit02Icon} />
                  Edit persona
                </Button>
              </DisabledReason>
            </CardAction>
          ) : null}
        </CardHeader>
        <CardContent>
          {loadingPersona ? (
            <div className="space-y-3">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-4 w-3/4" />
            </div>
          ) : persona ? (
            <PersonaText content={persona.content} />
          ) : (
            <div className="space-y-3 text-sm text-muted-foreground">
              <p>{personaError ?? "No persona yet."}</p>
              <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
                <Button
                  variant="outline"
                  onClick={() => router.push("/onboarding")}
                  disabled={readOnly}
                >
                  Go to onboarding
                </Button>
              </DisabledReason>
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="ring-destructive/20">
        <CardHeader>
          <CardTitle className="text-destructive">Delete account</CardTitle>
          <CardDescription>
            Permanently removes your account and every project, transcript,
            analysis, and artifact you own. This cannot be undone.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {deleteError ? (
            <p className="text-sm text-destructive">{deleteError}</p>
          ) : null}

          <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
            <DisabledReason reason={readOnly ? READ_ONLY_REASON : null}>
              <AlertDialogTrigger
                render={<Button variant="destructive" disabled={readOnly} />}
              >
                <Icon icon={Delete02Icon} />
                Delete account
              </AlertDialogTrigger>
            </DisabledReason>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Delete your account?</AlertDialogTitle>
                <AlertDialogDescription>
                  Everything you have created in Creator Helper Studio will be
                  removed and you will be signed out. This cannot be undone.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel disabled={deleting}>
                  Cancel
                </AlertDialogCancel>
                <AlertDialogAction
                  className="bg-destructive text-white hover:bg-destructive/90"
                  onClick={deleteAccount}
                  disabled={deleting}
                >
                  {deleting ? "Deleting…" : "Delete account"}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </CardContent>
      </Card>
    </div>
  );
}

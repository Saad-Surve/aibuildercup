"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { TrashIcon } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
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
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError, apiFetch } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type { Persona } from "@/lib/types";

function describe(error: unknown): string {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

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

export default function ProfilePage() {
  const { user, profile, signOut } = useAuth();
  const router = useRouter();

  const [persona, setPersona] = useState<Persona | null>(null);
  const [personaError, setPersonaError] = useState<string | null>(null);
  const [loadingPersona, setLoadingPersona] = useState(true);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    apiFetch<Persona>("/persona")
      .then((value) => {
        if (active) setPersona(value);
      })
      .catch((caught) => {
        if (active) setPersonaError(describe(caught));
      })
      .finally(() => {
        if (active) setLoadingPersona(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function deleteAccount() {
    setDeleting(true);
    setDeleteError(null);
    try {
      await apiFetch("/me", { method: "DELETE" });
      await signOut();
      router.replace("/login");
    } catch (caught) {
      setDeleteError(describe(caught));
      setDeleting(false);
      setConfirmOpen(false);
    }
  }

  const name = profile?.displayName ?? user?.displayName ?? "Creator";
  const email = profile?.email ?? user?.email ?? "—";

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="Profile"
        description="Your account and the persona the reviewers score against."
      />

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

      <Card>
        <CardHeader>
          <CardTitle>Creator persona</CardTitle>
          <CardDescription>
            Generated from your onboarding answers.
          </CardDescription>
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
              <Button
                variant="outline"
                onClick={() => router.push("/onboarding")}
              >
                Go to onboarding
              </Button>
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
            <AlertDialogTrigger render={<Button variant="destructive" />}>
              <TrashIcon />
              Delete account
            </AlertDialogTrigger>
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

"use client";

import { useAuth } from "@/components/auth/auth-provider";
import { GoogleSignInButton } from "@/components/auth/google-sign-in-button";
import { Button } from "@/components/ui/button";

function ErrorNotice({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive"
    >
      {message}
    </div>
  );
}

export function SignInPanel() {
  const { status, error, signInWithGoogle, signOut } = useAuth();

  if (status === "error") {
    return (
      <div className="space-y-4">
        <div className="space-y-1">
          <h2 className="font-heading text-lg font-semibold tracking-tight">
            We couldn&apos;t verify your session
          </h2>
          <p className="text-sm text-muted-foreground">
            Your sign-in worked, but the studio API didn&apos;t answer.
          </p>
        </div>
        <ErrorNotice message={error ?? "Unknown error."} />
        <Button variant="outline" onClick={signOut} className="w-full">
          Sign out and try again
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="space-y-1">
        <h2 className="font-heading text-lg font-semibold tracking-tight">
          Sign in to your studio
        </h2>
        <p className="text-sm text-muted-foreground">
          Continue with your Google account to start reviewing.
        </p>
      </div>

      {error ? <ErrorNotice message={error} /> : null}

      <GoogleSignInButton onClick={signInWithGoogle} />

      <p className="text-xs leading-relaxed text-muted-foreground">
        We use your Google account only to identify you. Your token is verified
        by the API, and your video data stays in your project.
      </p>
    </div>
  );
}

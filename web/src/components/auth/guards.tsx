"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AuthLoadingScreen } from "@/components/auth/auth-loading-screen";
import { useAuth } from "@/components/auth/auth-provider";
import { CenteredScreen } from "@/components/common/centered-screen";
import { Button } from "@/components/ui/button";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { status, error, signOut } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "signed_out") {
      router.replace("/");
    }
  }, [status, router]);

  if (status === "error") {
    return (
      <CenteredScreen>
        <div className="w-full max-w-sm space-y-4 text-center">
          <p className="text-sm text-muted-foreground">
            {error ?? "We couldn't load your profile."}
          </p>
          <Button variant="outline" onClick={signOut}>
            Sign out
          </Button>
        </div>
      </CenteredScreen>
    );
  }

  if (status !== "signed_in") {
    return (
      <CenteredScreen>
        <AuthLoadingScreen label="Loading your studio…" />
      </CenteredScreen>
    );
  }

  return <>{children}</>;
}

export function RequireOnboarded({ children }: { children: React.ReactNode }) {
  const { profile } = useAuth();
  const router = useRouter();
  const completed = profile?.onboardingCompleted ?? false;

  useEffect(() => {
    if (profile && !completed) {
      router.replace("/onboarding");
    }
  }, [profile, completed, router]);

  if (!profile || !completed) {
    return (
      <CenteredScreen>
        <AuthLoadingScreen label="Setting up your studio…" />
      </CenteredScreen>
    );
  }

  return <>{children}</>;
}

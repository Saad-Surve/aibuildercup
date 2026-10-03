"use client";

import { useState } from "react";
import { Key01Icon } from "@hugeicons/core-free-icons";
import { toast } from "sonner";

import { Icon } from "@/components/common/icon";
import { Button } from "@/components/ui/button";
import { auth } from "@/lib/firebase";

/**
 * Copies the signed-in user's current Firebase ID token to the clipboard, prefixed with
 * `Bearer `, ready to paste into a REST client or an `Authorization` header.
 *
 * Rendered in the app header behind the `copyAuthToken` feature flag.
 */
export function CopyTokenButton() {
  const [copying, setCopying] = useState(false);

  async function copyToken() {
    setCopying(true);
    try {
      const user = auth.currentUser;
      if (!user) throw new Error("You are not signed in.");
      const token = await user.getIdToken();
      await navigator.clipboard.writeText(`Bearer ${token}`);
      toast.success("Auth token copied", {
        description: 'Copied the full "Bearer …" header to your clipboard.',
      });
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Could not copy the token.",
      );
    } finally {
      setCopying(false);
    }
  }

  return (
    <Button
      type="button"
      variant="ghost"
      size="icon-sm"
      aria-label="Copy auth token"
      title="Copy auth token"
      onClick={() => void copyToken()}
      disabled={copying}
    >
      <Icon icon={Key01Icon} />
    </Button>
  );
}

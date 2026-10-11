"use client";

import Link from "next/link";

import { PageHeader } from "@/components/common/page-header";
import { YouTubeConnections } from "@/components/projects/studio/youtube-connections";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import {
  FEATURE_FLAGS,
  setFeatureFlag,
  useFeatureFlags,
} from "@/lib/feature-flags";

/**
 * Settings: connected accounts (the home for the YouTube connector) and the UI feature-flag
 * toggles.
 */
export default function SettingsPage() {
  const flags = useFeatureFlags();

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="Settings"
        description="Connections, publishing, and experiments."
      />

      <Card>
        <CardHeader>
          <CardTitle>Connections</CardTitle>
          <CardDescription>
            Connect the YouTube channels you publish to. Sign in with any Gmail
            account; every channel under it becomes a connection.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <YouTubeConnections redirectPath="/settings" />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Creator library</CardTitle>
          <CardDescription>
            Explore synced videos, imported writing and thumbnails. Find source
            material by meaning and use it as context for your drafts.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Link href="/library" className="text-sm text-signal hover:underline">
            Open your library →
          </Link>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Feature flags</CardTitle>
          <CardDescription>
            Experiments you can turn on. Stored in this browser.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {FEATURE_FLAGS.map((flag) => (
            <div
              key={flag.id}
              className="flex items-start justify-between gap-4"
            >
              <div className="space-y-0.5">
                <label
                  htmlFor={`flag-${flag.id}`}
                  className="text-sm font-medium"
                >
                  {flag.label}
                </label>
                <p className="max-w-[48ch] text-xs text-muted-foreground">
                  {flag.description}
                </p>
              </div>
              <Switch
                id={`flag-${flag.id}`}
                checked={flags[flag.id]}
                onCheckedChange={(value) => setFeatureFlag(flag.id, value)}
              />
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

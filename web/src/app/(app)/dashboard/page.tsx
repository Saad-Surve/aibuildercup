"use client";

import { UploadIcon } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { PageHeader } from "@/components/common/page-header";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";

export default function DashboardPage() {
  const { profile } = useAuth();
  const firstName = profile?.displayName?.split(" ")[0];

  return (
    <div className="mx-auto max-w-5xl space-y-8">
      <PageHeader
        title={firstName ? `Welcome, ${firstName}` : "Welcome"}
        description="Your studio is set up. Create a project to upload a video and run the reviewers."
      />

      <Empty className="border py-16">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <UploadIcon />
          </EmptyMedia>
          <EmptyTitle>No projects yet</EmptyTitle>
          <EmptyDescription>
            Upload a video to get a timestamped transcript and a multi-reviewer
            heatmap under the timeline.
          </EmptyDescription>
        </EmptyHeader>
        <EmptyContent>
          <Button disabled>New project</Button>
          <p className="text-xs text-muted-foreground">
            The upload flow is the next build.
          </p>
        </EmptyContent>
      </Empty>
    </div>
  );
}

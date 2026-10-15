"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowLeft01Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { PageHeader } from "@/components/common/page-header";
import {
  TranscriptEditor,
  TranscriptEditorSkeleton,
} from "@/components/projects/transcript-editor";

function TranscriptEditRoute() {
  const searchParams = useSearchParams();
  const projectId = searchParams.get("projectId");

  if (!projectId) {
    return (
      <div className="mx-auto max-w-4xl space-y-4">
        <PageHeader title="Transcript not found" />
        <p className="text-sm text-muted-foreground">
          This link is missing a project.
        </p>
        <Link
          href="/projects"
          className="inline-flex items-center gap-1.5 text-sm text-signal hover:underline"
        >
          <Icon icon={ArrowLeft01Icon} />
          Back to projects
        </Link>
      </div>
    );
  }

  return <TranscriptEditor projectId={projectId} />;
}

export default function TranscriptEditPage() {
  return (
    <Suspense fallback={<TranscriptEditorSkeleton />}>
      <TranscriptEditRoute />
    </Suspense>
  );
}

import { Loading03Icon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { Job, Project } from "@/lib/types";

export function ProcessingStatusCard({
  project,
  job,
}: {
  project: Project;
  job: Job | null;
}) {
  const failed = job?.status === "failed" || project.status === "failed";
  const percent = job?.progress.percent ?? project.progress?.percent ?? 0;
  const message =
    job?.progress.message ??
    project.progress?.message ??
    "Queued for transcription";

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          {!failed ? (
            <Icon icon={Loading03Icon} className="animate-spin text-signal" />
          ) : null}
          <CardTitle>
            {failed ? "Processing failed" : "Processing your video"}
          </CardTitle>
        </div>
        <CardDescription>
          {failed
            ? "Something went wrong while processing this video."
            : "We are transcribing your video, then the reviewers run over the transcript."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Progress value={percent} />
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">{message}</span>
          <span className="tabular text-muted-foreground">{percent}%</span>
        </div>
      </CardContent>
    </Card>
  );
}

import { formatDurationMs } from "@/lib/analysis";
import type { FindingLibraryLink } from "@/lib/types";

function passageUrl(link: FindingLibraryLink): string | null {
  if (!link.sourceUrl) return null;
  try {
    const url = new URL(link.sourceUrl);
    if (url.protocol !== "https:" && url.protocol !== "http:") return null;
    if (link.startMs != null) {
      const seconds = Math.floor(link.startMs / 1000);
      if (
        [
          "youtube.com",
          "www.youtube.com",
          "m.youtube.com",
          "youtu.be",
        ].includes(url.hostname)
      ) {
        url.searchParams.set("t", `${seconds}s`);
      } else {
        url.hash = `t=${seconds}`;
      }
    }
    return url.toString();
  } catch {
    return null;
  }
}

export function FindingLibraryLinks({
  links,
}: {
  links?: FindingLibraryLink[];
}) {
  if (!links?.length) return null;
  return (
    <div className="space-y-2 border-t border-border/60 px-3 py-2.5">
      <p className="text-xs font-medium text-muted-foreground">
        From your earlier work
      </p>
      {links.map((link) => {
        const url = passageUrl(link);
        const attribution = (
          <>
            {link.sourceTitle}
            {link.startMs != null && (
              <span className="ml-1.5 font-mono text-[11px] text-muted-foreground">
                at {formatDurationMs(link.startMs)}
              </span>
            )}
          </>
        );
        return (
          <div key={link.nodeId} className="space-y-1">
            {url ? (
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-medium underline underline-offset-2 hover:text-primary"
              >
                {attribution}
              </a>
            ) : (
              <p className="text-xs font-medium">{attribution}</p>
            )}
            <blockquote className="border-l-2 border-border pl-2 text-xs text-muted-foreground">
              {link.excerpt}
            </blockquote>
            <p className="text-xs text-foreground/80">{link.note}</p>
          </div>
        );
      })}
    </div>
  );
}

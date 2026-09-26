"use client";

import { useMemo, useState } from "react";
import { humation1 } from "@humation/assets-humation-1";
import { createPartPreview, getPartsForUiGroup } from "@humation/core";
import { DicesIcon } from "@hugeicons/core-free-icons";

import { Icon } from "@/components/common/icon";
import { UserAvatar } from "@/components/avatar/user-avatar";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { ApiError } from "@/lib/api-client";
import {
  normalizeAvatarState,
  randomAvatarState,
  updateAvatar,
  useUserAvatar,
} from "@/lib/avatar";
import { useAuth } from "@/components/auth/auth-provider";
import { cn } from "@/lib/utils";
import type { AvatarState } from "@/lib/types";

/* Curated swatches per color slot; background stays transparent. */
const COLOR_SWATCHES: Record<string, string[]> = {
  skin: ["#FFDFC4", "#F4C9A8", "#E8B088", "#C68642", "#8D5524", "#5C3A21"],
  hair: [
    "#1E1B18",
    "#4A3728",
    "#7A4A21",
    "#B5521F",
    "#D9D9D9",
    "#F2C94C",
    "#E85D75",
    "#3B82F6",
  ],
  clothes: [
    "#1E1B18",
    "#4A3728",
    "#2F6FED",
    "#0E9F6E",
    "#E85D75",
    "#7C3AED",
    "#F2C94C",
    "#D9D9D9",
  ],
};

function humanize(name: string): string {
  return name
    .split(/[-_]+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function partLabel(part: { name?: string; id: string }): string {
  return humanize(part.name ?? part.id);
}

function previewUrl(partId: string): string {
  const svg = String(createPartPreview(humation1, partId));
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

function describe(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Could not save your avatar. Try again.";
}

/*
 * Minimal avatar studio: live preview, one picker row per part group, three
 * color rows, randomize, save. Part and color state resolves through the
 * saved avatar (or a fresh random one until the first save).
 */
export function AvatarCustomizer() {
  const saved = useUserAvatar();
  const { refreshProfile } = useAuth();
  const [draft, setDraft] = useState<AvatarState | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const effective = draft ?? saved;

  const groups = useMemo(() => {
    const manifest = humation1 as unknown as {
      uiGroups?: { id: string; label?: string; order?: number }[];
    };
    const list = (manifest.uiGroups ?? []).toSorted(
      (a, b) => (a.order ?? 0) - (b.order ?? 0),
    );
    return list.map((group) => {
      const parts = getPartsForUiGroup(humation1, group.id) as {
        id: string;
        name?: string;
        selectionSlot?: string;
      }[];
      const slot = parts[0]?.selectionSlot ?? group.id;
      return {
        id: group.id,
        label: group.label ?? humanize(group.id),
        slot,
        parts,
      };
    });
  }, []);

  function pickPart(slot: string, partId: string) {
    setDraft((previous) => {
      const base = previous ?? effective;
      return {
        ...normalizeAvatarState(base),
        selections: { ...base.selections, [slot]: partId },
      };
    });
  }

  function pickColor(slot: string, color: string) {
    setDraft((previous) => {
      const base = previous ?? effective;
      return {
        ...normalizeAvatarState(base),
        colors: { ...base.colors, [slot]: color },
      };
    });
  }

  function randomize() {
    setDraft(randomAvatarState());
    setError(null);
  }

  async function save() {
    setPending(true);
    setError(null);
    try {
      await updateAvatar(normalizeAvatarState(effective));
      setDraft(null);
      await refreshProfile();
    } catch (caught) {
      setError(describe(caught));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <UserAvatar state={effective} size={96} title="Avatar preview" />
        <div className="space-y-2">
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={randomize}
              disabled={pending}
            >
              <Icon icon={DicesIcon} />
              Randomize
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={() => void save()}
              disabled={pending}
            >
              {pending ? "Saving…" : "Save avatar"}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Randomize for a new look, or mix parts and colors below.
          </p>
        </div>
      </div>

      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {groups.map((group) => (
        <div key={group.id} className="space-y-1">
          <p className="text-sm font-medium">{group.label}</p>
          {/* py-2 breathing room: the scroll container clips anything that
              reaches its edge, which used to slice the selected rings and the
              buttons' rounded corners top and bottom. */}
          <div className="flex gap-2 overflow-x-auto px-0.5 py-2">
            {group.parts.map((part) => {
              const selected = effective.selections[group.slot] === part.id;
              return (
                <button
                  key={part.id}
                  type="button"
                  title={partLabel(part)}
                  aria-label={`${group.label}: ${partLabel(part)}`}
                  aria-pressed={selected}
                  onClick={() => pickPart(group.slot, part.id)}
                  className={cn(
                    "size-14 shrink-0 rounded-xl bg-muted p-1 transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
                    selected
                      ? "shadow-sm ring-2 ring-signal"
                      : "border border-transparent shadow-none ring-1 ring-foreground/10 hover:ring-foreground/25",
                  )}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={previewUrl(part.id)}
                    alt=""
                    aria-hidden="true"
                    draggable={false}
                    className="size-full"
                  />
                </button>
              );
            })}
          </div>
        </div>
      ))}

      {Object.entries(COLOR_SWATCHES).map(([slot, swatches]) => (
        <div key={slot} className="space-y-2">
          <p className="text-sm font-medium">{humanize(slot)}</p>
          <div className="flex flex-wrap gap-2">
            {swatches.map((color) => {
              const selected = effective.colors[slot] === color;
              return (
                <button
                  key={color}
                  type="button"
                  title={color}
                  aria-label={`${humanize(slot)} color ${color}`}
                  aria-pressed={selected}
                  onClick={() => pickColor(slot, color)}
                  style={{ backgroundColor: color }}
                  className={cn(
                    "size-8 rounded-full transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                    selected
                      ? "shadow-sm ring-2 ring-signal ring-offset-2 ring-offset-background"
                      : "ring-1 ring-foreground/15 hover:ring-foreground/35",
                  )}
                />
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

/*
 * Collapsed entry point: a single button that opens the full customizer in a
 * modal, so the profile page stays compact. Shows the current avatar at a
 * correct fixed size next to the trigger.
 */
export function AvatarEditorDialog() {
  const saved = useUserAvatar();
  const [open, setOpen] = useState(false);

  return (
    <div className="flex items-center gap-4">
      <UserAvatar state={saved} size={64} title="Your avatar" />
      <div className="space-y-1.5">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger render={<Button variant="outline" />}>
            Customize avatar
          </DialogTrigger>
          <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-2xl">
            <DialogHeader>
              <DialogTitle>Avatar studio</DialogTitle>
              <DialogDescription>
                Randomize for a new look, or mix parts and colors. Save to apply
                it everywhere.
              </DialogDescription>
            </DialogHeader>
            <AvatarCustomizer />
          </DialogContent>
        </Dialog>
        <p className="text-xs text-muted-foreground">
          Hand-drawn Humation avatar — shown in the header.
        </p>
      </div>
    </div>
  );
}

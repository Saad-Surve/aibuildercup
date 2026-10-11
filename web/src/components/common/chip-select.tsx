"use client";

import Image from "next/image";

import { cn } from "@/lib/utils";

export interface ChipOption {
  value: string;
  label: string;
  /** Optional logo shown before the label (platform chips). */
  logoSrc?: string;
}

export function ChipSelect({
  options,
  value,
  onChange,
  multiple = true,
  className,
}: {
  options: ChipOption[];
  value: string[];
  onChange: (value: string[]) => void;
  multiple?: boolean;
  className?: string;
}) {
  function toggle(optionValue: string) {
    if (!multiple) {
      onChange([optionValue]);
      return;
    }
    onChange(
      value.includes(optionValue)
        ? value.filter((item) => item !== optionValue)
        : [...value, optionValue],
    );
  }

  return (
    <div role="group" className={cn("flex flex-wrap gap-2", className)}>
      {options.map((option) => {
        const selected = value.includes(option.value);
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={selected}
            onClick={() => toggle(option.value)}
            className={cn(
              "inline-flex h-8 items-center gap-1.5 rounded-lg border px-3 text-sm transition-colors focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
              selected
                ? "border-signal bg-signal text-signal-foreground"
                : "border-input bg-background text-foreground hover:bg-muted",
            )}
          >
            {option.logoSrc ? (
              <Image
                src={option.logoSrc}
                alt=""
                aria-hidden
                width={14}
                height={14}
                className="shrink-0 object-contain"
              />
            ) : null}
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

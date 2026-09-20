import { cn } from "@/lib/utils";

export function CenteredScreen({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex min-h-[100dvh] flex-1 items-center justify-center px-4 py-10",
        className,
      )}
    >
      {children}
    </div>
  );
}

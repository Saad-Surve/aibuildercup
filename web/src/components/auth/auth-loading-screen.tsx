export function AuthLoadingScreen({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center gap-4 text-zinc-500 dark:text-zinc-400">
      <span
        aria-hidden="true"
        className="h-8 w-8 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-900 dark:border-zinc-700 dark:border-t-white"
      />
      <p className="text-sm">{label}</p>
    </div>
  );
}

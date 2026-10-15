import Link from "next/link";
import type { ReactNode } from "react";

import { Logo } from "@/components/common/logo";
import { buttonVariants } from "@/components/ui/button";
import { LEGAL_LAST_UPDATED } from "@/lib/legal";

/*
 * Shared chrome for the public legal pages (privacy policy, terms of service).
 * Both routes are static, unauthenticated, and live outside the `(app)` group.
 * Each page supplies its own title/intro and a list of numbered sections; this
 * shell renders the branded header, on-page navigation, article body, and footer.
 */

export type LegalSectionLink = { id: string; label: string };

export function LegalSection({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-24">
      <h2 className="font-heading text-lg font-semibold tracking-tight text-foreground">
        {title}
      </h2>
      <div className="mt-3 space-y-3 text-sm leading-relaxed text-muted-foreground">
        {children}
      </div>
    </section>
  );
}

export function LegalPage({
  title,
  intro,
  sections,
  children,
}: {
  title: string;
  intro: ReactNode;
  sections: readonly LegalSectionLink[];
  children: ReactNode;
}) {
  return (
    <div className="relative flex min-h-full flex-1 flex-col">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[28rem] overflow-hidden"
      >
        <div className="absolute inset-0 bg-background" />
        <div className="absolute -left-40 -top-32 h-[32rem] w-[32rem] rounded-full bg-[radial-gradient(circle,rgba(217,119,6,0.10),transparent_66%)] blur-3xl" />
        <div className="absolute -right-40 -top-24 h-[34rem] w-[34rem] rounded-full bg-[radial-gradient(circle,rgba(124,58,237,0.09),transparent_66%)] blur-3xl" />
      </div>

      <header className="sticky top-0 z-20 border-b border-border/60 bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-6">
          <Logo href="/" showSubtitle={false} />
          <Link
            href="/"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Back to home
          </Link>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-12 sm:py-16">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Legal
          </p>
          <h1 className="mt-3 font-heading text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
            {title}
          </h1>
          <div className="mt-4 text-sm leading-relaxed text-muted-foreground">
            {intro}
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Last updated {LEGAL_LAST_UPDATED}
          </p>
        </div>

        <div className="mt-12 gap-12 lg:flex">
          <nav
            aria-label="On this page"
            className="hidden lg:block lg:w-56 lg:shrink-0"
          >
            <div className="sticky top-24">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                On this page
              </p>
              <ul className="mt-3 space-y-2 text-sm">
                {sections.map((section) => (
                  <li key={section.id}>
                    <a
                      href={`#${section.id}`}
                      className="text-muted-foreground transition-colors hover:text-foreground"
                    >
                      {section.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </nav>

          <article className="min-w-0 max-w-2xl flex-1 space-y-10">
            {children}
          </article>
        </div>
      </main>

      <footer className="border-t border-border/60">
        <div className="mx-auto flex max-w-5xl flex-col gap-3 px-6 py-8 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <p>Resonance &middot; AI review studio for creators</p>
          <div className="flex items-center gap-5">
            <Link
              href="/privacy"
              className="transition-colors hover:text-foreground"
            >
              Privacy Policy
            </Link>
            <Link
              href="/terms"
              className="transition-colors hover:text-foreground"
            >
              Terms of Service
            </Link>
            <Link
              href="/data-deletion"
              className="transition-colors hover:text-foreground"
            >
              Data Deletion
            </Link>
            <Link
              href="/"
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              Back to home
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

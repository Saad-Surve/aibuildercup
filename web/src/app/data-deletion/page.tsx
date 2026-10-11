import type { Metadata } from "next";

import { InlineArrow } from "@/components/common/inline-arrow";
import {
  LegalPage,
  LegalSection,
  type LegalSectionLink,
} from "@/components/legal/legal-page";
import { LEGAL_CONTACT_EMAIL } from "@/lib/legal";

export const metadata: Metadata = {
  title: "Data Deletion Instructions — Resonance",
  description:
    "How to delete your account, projects, and platform data from the Resonance Creator Helper Studio.",
};

const SECTIONS: readonly LegalSectionLink[] = [
  { id: "overview", label: "Overview" },
  { id: "what-we-store", label: "What we store" },
  { id: "delete-account", label: "Delete your account" },
  { id: "delete-project", label: "Delete a project or item" },
  { id: "disconnect", label: "Disconnect a platform" },
  { id: "by-email", label: "Request deletion by email" },
  { id: "timing", label: "What happens after deletion" },
  { id: "contact", label: "Contact us" },
];

export default function DataDeletionPage() {
  return (
    <LegalPage
      title="Data Deletion Instructions"
      intro={
        <p>
          If you signed in to Resonance or connected a platform account and want
          your data removed, you can delete it yourself from the studio or ask
          us to delete it for you. This page explains both options.
        </p>
      }
      sections={SECTIONS}
    >
      <LegalSection id="overview" title="Overview">
        <p>
          You are in control of your data. Deleting a project or your account in
          the studio is a real deletion: records and stored files are removed,
          not hidden.
        </p>
      </LegalSection>

      <LegalSection id="what-we-store" title="What we store">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Account information: your name, email address, and profile photo
            from Google sign-in.
          </li>
          <li>
            Your content: videos you upload and everything generated from them
            (transcripts, reviews, clips, thumbnails, drafts, captions, and
            localizations).
          </li>
          <li>
            Connected platform data: access tokens and, only with your
            authorization, the channel or account data the features you use
            require.
          </li>
          <li>
            Basic operational logs used to run and secure the service.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="delete-account" title="Delete your account">
        <p>
          This is the fastest way to remove everything associated with your
          account.
        </p>
        <ol className="list-decimal space-y-2 pl-5">
          <li>Sign in to the studio.</li>
          <li>
            Open your <span className="font-medium text-foreground">Profile</span>{" "}
            from the avatar menu.
          </li>
          <li>
            In the{" "}
            <span className="font-medium text-foreground">
              Delete account
            </span>{" "}
            card, choose <span className="font-medium text-foreground">Delete account</span> and
            confirm.
          </li>
        </ol>
        <p>
          We revoke access to every connected platform, delete your uploaded
          videos and generated files, and remove your account records from the
          database. You are signed out at the end. This action cannot be undone.
        </p>
      </LegalSection>

      <LegalSection id="delete-project" title="Delete a project or item">
        <p>
          To remove a single project without deleting your account:
        </p>
        <ol className="list-decimal space-y-2 pl-5">
          <li>Open the project from your dashboard.</li>
          <li>
            Use the{" "}
            <span className="font-medium text-foreground">Delete</span> action in
            the project workspace and confirm.
          </li>
        </ol>
        <p>
          You can also delete individual items &mdash; drafts, thumbnails, clips,
          caption renders, and localizations &mdash; from their panels inside a
          project. Deleting a project removes its stored files and records.
        </p>
      </LegalSection>

      <LegalSection id="disconnect" title="Disconnect a platform">
        <p>
          To revoke our access to a connected platform without deleting your
          account, go to{" "}
          <span className="font-medium text-foreground">Settings</span>{" "}
          <InlineArrow />{" "}
          <span className="font-medium text-foreground">Connections</span>, choose
          the connected channel or account, and disconnect it. This revokes our
          access and deletes the stored token. Content already generated from
          that connection stays in your projects until you delete it.
        </p>
        <p>
          You can also revoke access directly from the platform&rsquo;s own
          account settings.
        </p>
      </LegalSection>

      <LegalSection id="by-email" title="Request deletion by email">
        <p>
          If you cannot sign in, or you want help deleting specific data, email
          us and we will handle it for you.
        </p>
        <ol className="list-decimal space-y-2 pl-5">
          <li>
            Email{" "}
            <a
              href={`mailto:${LEGAL_CONTACT_EMAIL}?subject=Data%20deletion%20request`}
              className="font-medium text-foreground underline underline-offset-4"
            >
              {LEGAL_CONTACT_EMAIL}
            </a>{" "}
            with the subject &ldquo;Data deletion request&rdquo;.
          </li>
          <li>
            Tell us the email address or account identifier you used, and
            whether you want your whole account deleted or only specific data.
          </li>
          <li>
            We may ask you to verify that you own the account before we act.
          </li>
        </ol>
        <p>
          We will complete the deletion and confirm by reply, normally within 30
          days.
        </p>
      </LegalSection>

      <LegalSection id="timing" title="What happens after deletion">
        <ul className="list-disc space-y-2 pl-5">
          <li>
            Your records and stored files are removed, not flagged as hidden.
          </li>
          <li>
            Access to connected platforms is revoked first, so the deleted
            tokens cannot be reused.
          </li>
          <li>
            Residual copies may remain briefly in encrypted backups and are
            purged as those backups rotate.
          </li>
          <li>
            We may retain limited records where the law requires it, for example
            for accounting or fraud prevention.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="contact" title="Contact us">
        <p>
          For any data deletion request or question, email{" "}
          <a
            href={`mailto:${LEGAL_CONTACT_EMAIL}?subject=Data%20deletion%20request`}
            className="font-medium text-foreground underline underline-offset-4"
          >
            {LEGAL_CONTACT_EMAIL}
          </a>
          .
        </p>
      </LegalSection>
    </LegalPage>
  );
}

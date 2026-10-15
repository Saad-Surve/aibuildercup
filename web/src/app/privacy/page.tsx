import type { Metadata } from "next";
import Link from "next/link";

import {
  LegalPage,
  LegalSection,
  type LegalSectionLink,
} from "@/components/legal/legal-page";
import { LEGAL_CONTACT_EMAIL } from "@/lib/legal";

export const metadata: Metadata = {
  title: "Privacy Policy — Resonance",
  description:
    "How Resonance collects, uses, shares, and deletes information across Resonance.",
};

const SECTIONS: readonly LegalSectionLink[] = [
  { id: "overview", label: "Overview" },
  { id: "information-we-collect", label: "Information we collect" },
  { id: "how-we-use", label: "How we use information" },
  { id: "ai-processing", label: "AI processing" },
  { id: "sharing", label: "When we share information" },
  { id: "connections", label: "Connected platforms" },
  { id: "cookies", label: "Cookies and local storage" },
  { id: "retention", label: "Data retention" },
  { id: "your-choices", label: "Your choices and deletion" },
  { id: "security", label: "Security" },
  { id: "transfers", label: "International transfers" },
  { id: "children", label: "Children's privacy" },
  { id: "rights", label: "Your privacy rights" },
  { id: "changes", label: "Changes to this policy" },
  { id: "contact", label: "Contact us" },
];

export default function PrivacyPolicyPage() {
  return (
    <LegalPage
      title="Privacy Policy"
      intro={
        <p>
          Resonance is a creator studio that helps you review and repurpose your
          video content. This policy explains what we collect, why we collect
          it, who we share it with, and the control you have over it.
        </p>
      }
      sections={SECTIONS}
    >
      <LegalSection id="overview" title="Overview">
        <p>
          This policy applies to the Resonance and the web application at this
          domain (the &ldquo;Service&rdquo;). By using the Service you agree to
          the collection and use of information described here. If you do not
          agree, please do not use the Service.
        </p>
      </LegalSection>

      <LegalSection id="information-we-collect" title="Information we collect">
        <p>
          <span className="font-medium text-foreground">
            Account information.
          </span>{" "}
          When you sign in with Google, we receive your name, email address, and
          profile photo, and we use Firebase Authentication to manage your
          session.
        </p>
        <p>
          <span className="font-medium text-foreground">
            Content you provide.
          </span>{" "}
          Videos you upload, together with the transcripts, captions, reviews,
          clips, thumbnails, drafts, and localizations the studio generates from
          them.
        </p>
        <p>
          <span className="font-medium text-foreground">
            Connected platform data.
          </span>{" "}
          When you connect a third-party video or social platform through its
          official authorization flow, we store an access token and, only with
          the permissions you grant, the data the features you use require
          &mdash; for example your channel profile, your list of published
          videos, and aggregate performance analytics. We request only the
          scopes a feature needs.
        </p>
        <p>
          <span className="font-medium text-foreground">
            Usage and technical information.
          </span>{" "}
          Basic diagnostic data such as request timestamps, browser and device
          type, and IP address, used to operate, debug, and secure the Service.
        </p>
        <p>
          We do not collect payment card information, and we do not use
          advertising or cross-site tracking technologies.
        </p>
      </LegalSection>

      <LegalSection id="how-we-use" title="How we use information">
        <p>We use the information we collect to:</p>
        <ul className="list-disc space-y-2 pl-5">
          <li>provide, operate, and maintain the Service;</li>
          <li>
            generate transcripts, multi-reviewer critiques, and derivative
            content such as clips, thumbnails, and drafts;
          </li>
          <li>
            connect to platforms you authorize and, only on your instruction,
            read from or publish to them;
          </li>
          <li>
            personalize draft generation using your own previously published
            content;
          </li>
          <li>monitor, secure, and improve the Service and prevent abuse;</li>
          <li>
            communicate with you about the Service and respond to your requests;
            and
          </li>
          <li>comply with applicable legal obligations.</li>
        </ul>
      </LegalSection>

      <LegalSection id="ai-processing" title="AI processing">
        <p>
          To produce transcripts, reviews, translations, synthesized speech, and
          generated media, we send the relevant content to Google Cloud AI
          services, including Gemini (through Vertex AI), Speech-to-Text,
          Text-to-Speech, Translation, and image generation. These providers
          process your content on our behalf under Google Cloud&rsquo;s
          data-processing terms and only for the purpose of delivering the
          Service to you.
        </p>
      </LegalSection>

      <LegalSection id="sharing" title="When we share information">
        <p>
          We do not sell your personal information. We share it only as
          described below:
        </p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <span className="font-medium text-foreground">
              Service providers.
            </span>{" "}
            Google Cloud provides our hosting, object storage, database,
            authentication, and AI processing.
          </li>
          <li>
            <span className="font-medium text-foreground">
              Platforms you connect.
            </span>{" "}
            When you direct the studio to read from or publish to a connected
            platform, the relevant content is sent to that platform under your
            authorization.
          </li>
          <li>
            <span className="font-medium text-foreground">
              Legal and safety.
            </span>{" "}
            We may disclose information where required by law or to protect the
            rights, safety, and security of users and the Service.
          </li>
          <li>
            <span className="font-medium text-foreground">
              Business transfers.
            </span>{" "}
            If the Service is involved in a merger, acquisition, or sale of
            assets, information may be transferred as part of that transaction,
            subject to this policy.
          </li>
        </ul>
      </LegalSection>

      <LegalSection id="connections" title="Connected platforms">
        <p>
          When you connect a third-party platform, we act only on your
          instructions. We do not post, modify, or delete anything on a
          connected platform unless you take an action in the studio that does
          so. Access tokens are stored on our servers and are never exposed to
          your browser or to other users.
        </p>
        <p>
          You can disconnect a platform at any time from the studio, and you can
          also revoke the studio&rsquo;s access from the platform&rsquo;s own
          account settings. Disconnecting stops future access and removes the
          stored token.
        </p>
      </LegalSection>

      <LegalSection id="cookies" title="Cookies and local storage">
        <p>
          We use first-party browser storage for essential purposes only:
          keeping you signed in, remembering your light or dark theme
          preference, and storing feature-flag choices. We do not use
          third-party advertising cookies or cross-site tracking technologies.
        </p>
      </LegalSection>

      <LegalSection id="retention" title="Data retention">
        <p>
          We retain your content for as long as your account is active and as
          needed to provide the Service. Generated artifacts are kept so you can
          revisit them until you delete the project or your account. Operational
          logs are retained for a limited period for security and debugging, and
          some residual copies may remain in encrypted backups for a short time
          after deletion.
        </p>
      </LegalSection>

      <LegalSection id="your-choices" title="Your choices and deletion">
        <p>You are in control of your data:</p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            <span className="font-medium text-foreground">
              Delete a project.
            </span>{" "}
            Deleting a project removes its documents and every stored object
            under that project. This is a real deletion, not a hidden flag.
          </li>
          <li>
            <span className="font-medium text-foreground">
              Delete your account.
            </span>{" "}
            Deleting your account removes your entire data tree and all
            associated stored objects.
          </li>
          <li>
            <span className="font-medium text-foreground">
              Disconnect a platform.
            </span>{" "}
            Disconnect at any time, in the studio or from the platform&rsquo;s
            settings.
          </li>
          <li>
            <span className="font-medium text-foreground">Contact us.</span> You
            can ask us to access, correct, or delete your information by
            emailing{" "}
            <a
              href={`mailto:${LEGAL_CONTACT_EMAIL}`}
              className="font-medium text-foreground underline underline-offset-4"
            >
              {LEGAL_CONTACT_EMAIL}
            </a>
            .
          </li>
        </ul>
        <p>
          For step-by-step instructions covering your account, individual
          projects, and connected platform data, see our{" "}
          <Link
            href="/data-deletion"
            className="font-medium text-foreground underline underline-offset-4"
          >
            Data Deletion Instructions
          </Link>
          .
        </p>
      </LegalSection>

      <LegalSection id="security" title="Security">
        <p>
          We protect information with encryption in transit, access controls on
          our cloud resources, server-side storage of platform tokens, and
          per-user ownership checks on every read and write. No method of
          transmission or storage is completely secure, and we cannot guarantee
          absolute security.
        </p>
      </LegalSection>

      <LegalSection id="transfers" title="International transfers">
        <p>
          We process information using Google Cloud infrastructure, which may
          store and process data in regions outside your own. Where required, we
          rely on appropriate safeguards for these transfers.
        </p>
      </LegalSection>

      <LegalSection id="children" title="Children's privacy">
        <p>
          The Service is not directed to children under 13 (or the minimum age
          in your jurisdiction), and we do not knowingly collect their personal
          information. If you believe a child has provided us information,
          contact us and we will delete it.
        </p>
      </LegalSection>

      <LegalSection id="rights" title="Your privacy rights">
        <p>
          Depending on where you live, you may have the right to access,
          correct, delete, or receive a copy of your personal information, and
          to restrict or object to certain processing. You may also have the
          right not to be discriminated against for exercising these rights. We
          do not sell your personal information or share it for cross-context
          behavioral advertising.
        </p>
        <p>
          To exercise any of these rights, email{" "}
          <a
            href={`mailto:${LEGAL_CONTACT_EMAIL}`}
            className="font-medium text-foreground underline underline-offset-4"
          >
            {LEGAL_CONTACT_EMAIL}
          </a>
          . We will respond within the timeframe required by applicable law.
        </p>
      </LegalSection>

      <LegalSection id="changes" title="Changes to this policy">
        <p>
          We may update this policy from time to time. We will revise the
          &ldquo;last updated&rdquo; date above and, for material changes,
          provide a more prominent notice within the Service.
        </p>
      </LegalSection>

      <LegalSection id="contact" title="Contact us">
        <p>
          Questions about this policy or your information? Email{" "}
          <a
            href={`mailto:${LEGAL_CONTACT_EMAIL}`}
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

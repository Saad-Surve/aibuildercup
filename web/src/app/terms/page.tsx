import type { Metadata } from "next";

import {
  LegalPage,
  LegalSection,
  type LegalSectionLink,
} from "@/components/legal/legal-page";
import { LEGAL_CONTACT_EMAIL } from "@/lib/legal";

export const metadata: Metadata = {
  title: "Terms of Service — Resonance",
  description: "The terms that govern your use of the Resonance.",
};

const SECTIONS: readonly LegalSectionLink[] = [
  { id: "acceptance", label: "Acceptance of terms" },
  { id: "the-service", label: "The Service" },
  { id: "eligibility-accounts", label: "Eligibility and accounts" },
  { id: "your-content", label: "Your content" },
  { id: "acceptable-use", label: "Acceptable use" },
  { id: "connected-platforms", label: "Connected platforms" },
  { id: "ai-output", label: "AI-generated output" },
  { id: "intellectual-property", label: "Our intellectual property" },
  { id: "fees", label: "Fees" },
  { id: "disclaimers", label: "Disclaimers" },
  { id: "liability", label: "Limitation of liability" },
  { id: "indemnification", label: "Indemnification" },
  { id: "termination", label: "Suspension and termination" },
  { id: "governing-law", label: "Governing law" },
  { id: "changes", label: "Changes to these terms" },
  { id: "contact", label: "Contact us" },
];

export default function TermsOfServicePage() {
  return (
    <LegalPage
      title="Terms of Service"
      intro={
        <p>
          These terms govern your access to and use of the Resonance Creator
          Helper Studio (the &ldquo;Service&rdquo;). Please read them carefully.
        </p>
      }
      sections={SECTIONS}
    >
      <LegalSection id="acceptance" title="Acceptance of terms">
        <p>
          By creating an account or using the Service, you agree to be bound by
          these terms and by our Privacy Policy. If you do not agree, do not use
          the Service. If you use the Service on behalf of an organization, you
          represent that you have authority to bind that organization to these
          terms.
        </p>
      </LegalSection>

      <LegalSection id="the-service" title="The Service">
        <p>
          The Service is a creator studio that transcribes your videos, runs
          multi-reviewer critiques, and generates derivative content such as
          clips, thumbnails, drafts, captions, and localizations. Some features
          rely on third-party platforms and on AI models and may change,
          improve, or be discontinued over time. We may set limits on features
          or usage to protect the Service and control cost.
        </p>
      </LegalSection>

      <LegalSection id="eligibility-accounts" title="Eligibility and accounts">
        <p>
          You must be old enough to form a binding contract in your jurisdiction
          and at least the minimum age required by any platform you connect. You
          sign in through Google, and you are responsible for maintaining the
          security of your account and for all activity that occurs under it.
          Notify us promptly if you suspect unauthorized use.
        </p>
      </LegalSection>

      <LegalSection id="your-content" title="Your content">
        <p>
          You retain all rights to the videos, text, and other material you
          upload or connect to the Service (&ldquo;Your Content&rdquo;). You are
          responsible for making sure you have the rights necessary to upload
          and process Your Content.
        </p>
        <p>
          You grant us a limited, non-exclusive, worldwide license to host,
          store, reproduce, transmit, and process Your Content &mdash; including
          sending it to the service providers and AI services described in our
          Privacy Policy &mdash; solely to operate, provide, and improve the
          features you use. This license ends when you delete Your Content,
          except for residual copies in backups or where retention is required
          by law.
        </p>
      </LegalSection>

      <LegalSection id="acceptable-use" title="Acceptable use">
        <p>You agree not to:</p>
        <ul className="list-disc space-y-2 pl-5">
          <li>
            upload or process content that is unlawful, infringing, or that you
            do not have the right to use;
          </li>
          <li>
            use the Service to harass, deceive, defame, or harm others, or to
            create misleading or deceptive media;
          </li>
          <li>
            attempt to reverse engineer, disrupt, overload, or gain unauthorized
            access to the Service or its infrastructure;
          </li>
          <li>
            bypass usage limits, cost controls, or access restrictions, or
            resell the Service without our permission; or
          </li>
          <li>
            use the Service or its output to develop or train a competing
            product or model.
          </li>
        </ul>
        <p>
          We may remove content or suspend access that violates these terms.
        </p>
      </LegalSection>

      <LegalSection id="connected-platforms" title="Connected platforms">
        <p>
          When you connect a third-party platform, you authorize us to access
          and act on that platform only as needed for the features you use, and
          you agree to comply with that platform&rsquo;s own terms. You are
          responsible for the content you publish through the Service and for
          the permissions you grant. You can disconnect a platform at any time.
        </p>
      </LegalSection>

      <LegalSection id="ai-output" title="AI-generated output">
        <p>
          The Service uses AI to generate transcripts, critiques, suggestions,
          and media. AI output can be inaccurate, incomplete, or offensive, and
          may resemble output generated for others. To the extent permitted by
          law, and subject to the terms of the underlying providers, you own the
          output generated for your account; we do not warrant that it is unique
          or free of third-party rights.
        </p>
        <p>
          The Service, including its review and &ldquo;legal&rdquo; reviewers,
          is not a substitute for professional advice. It does not provide
          legal, medical, financial, or other professional advice. You are
          responsible for reviewing and verifying all output before relying on
          or publishing it.
        </p>
      </LegalSection>

      <LegalSection
        id="intellectual-property"
        title="Our intellectual property"
      >
        <p>
          The Service, including its software, design, and branding, is owned by
          us or our licensors and is protected by intellectual-property laws.
          These terms do not grant you any right to our trademarks, logos, or
          other brand features, and you may not use them without our prior
          written permission.
        </p>
      </LegalSection>

      <LegalSection id="fees" title="Fees">
        <p>
          The Service is currently offered free of charge while in development.
          We do not collect payment information. If we introduce paid features,
          we will present the applicable fees and terms before you are charged.
        </p>
      </LegalSection>

      <LegalSection id="disclaimers" title="Disclaimers">
        <p>
          The Service is provided &ldquo;as is&rdquo; and &ldquo;as
          available,&rdquo; without warranties of any kind, whether express or
          implied, including fitness for a particular purpose, accuracy, and
          non-infringement. We do not warrant that the Service will be
          uninterrupted, error-free, or secure, or that it will meet your
          requirements.
        </p>
      </LegalSection>

      <LegalSection id="liability" title="Limitation of liability">
        <p>
          To the maximum extent permitted by law, we will not be liable for any
          indirect, incidental, special, consequential, or punitive damages, or
          for any loss of data, content, revenue, or profits, arising out of or
          related to your use of the Service. Our total aggregate liability for
          any claim relating to the Service will not exceed the greater of the
          amount you paid us in the twelve months before the claim or one
          hundred US dollars (US$100).
        </p>
        <p>
          Some jurisdictions do not allow certain limitations, so some of the
          above may not apply to you.
        </p>
      </LegalSection>

      <LegalSection id="indemnification" title="Indemnification">
        <p>
          You agree to indemnify and hold us harmless from any claims, damages,
          liabilities, and expenses arising from Your Content, from your use of
          the Service, or from your violation of these terms or of any
          third-party rights.
        </p>
      </LegalSection>

      <LegalSection id="termination" title="Suspension and termination">
        <p>
          You may stop using the Service and delete your account at any time;
          deleting your account removes your data as described in our Privacy
          Policy. We may suspend or terminate your access if you violate these
          terms or if we are required to by law. Sections that by their nature
          should survive termination &mdash; such as content licenses for
          retained copies, disclaimers, liability limits, and indemnification
          &mdash; will continue to apply.
        </p>
      </LegalSection>

      <LegalSection id="governing-law" title="Governing law">
        <p>
          These terms are governed by the laws of the jurisdiction in which the
          operator of the Service is established, without regard to its
          conflict-of-law rules, and the courts of that jurisdiction will have
          exclusive jurisdiction over any dispute, unless mandatory local law
          provides otherwise.
        </p>
      </LegalSection>

      <LegalSection id="changes" title="Changes to these terms">
        <p>
          We may update these terms from time to time. We will revise the
          &ldquo;last updated&rdquo; date above and, for material changes,
          provide a more prominent notice within the Service. Your continued use
          of the Service after changes take effect means you accept the updated
          terms.
        </p>
      </LegalSection>

      <LegalSection id="contact" title="Contact us">
        <p>
          Questions about these terms? Email{" "}
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

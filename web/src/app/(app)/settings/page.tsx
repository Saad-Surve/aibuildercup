"use client";

import { PageHeader } from "@/components/common/page-header";
import { AccountConnections } from "@/components/accounts/account-connections";
import { Card, CardContent } from "@/components/ui/card";

/**
 * Connectors: every external account (YouTube channels, writing platforms)
 * lives here. Publishing and experiments moved out — header tabs are always
 * on, and the library has its own sidebar entry.
 */
export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="Connectors"
        description="Connected accounts and where your work goes."
      />

      <Card>
        <CardContent>
          <AccountConnections redirectPath="/settings" />
        </CardContent>
      </Card>
    </div>
  );
}

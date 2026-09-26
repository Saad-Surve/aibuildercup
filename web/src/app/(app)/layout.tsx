import { AvatarBootstrap } from "@/components/avatar/avatar-bootstrap";
import { RequireAuth, RequireOnboarded } from "@/components/auth/guards";
import { AppShell } from "@/components/layout/app-shell";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <RequireOnboarded>
        <AppShell>{children}</AppShell>
        <AvatarBootstrap />
      </RequireOnboarded>
    </RequireAuth>
  );
}

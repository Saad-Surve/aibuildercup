import { AvatarBootstrap } from "@/components/avatar/avatar-bootstrap";
import { RequireAuth, RequireOnboarded } from "@/components/auth/guards";
import { AppShell } from "@/components/layout/app-shell";
import { ImagePrefetcher } from "@/components/layout/image-prefetcher";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <RequireOnboarded>
        <AppShell>{children}</AppShell>
        <AvatarBootstrap />
        <ImagePrefetcher />
      </RequireOnboarded>
    </RequireAuth>
  );
}

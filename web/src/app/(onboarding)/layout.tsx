import { RequireAuth } from "@/components/auth/guards";

export default function OnboardingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <RequireAuth>{children}</RequireAuth>;
}

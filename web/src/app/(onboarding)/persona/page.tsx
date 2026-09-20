import { RequireOnboarded } from "@/components/auth/guards";
import { OnboardingFlow } from "@/components/onboarding/onboarding-flow";

export default function Page() {
  return (
    <RequireOnboarded>
      <OnboardingFlow mode="edit" />
    </RequireOnboarded>
  );
}

import { AuthGate } from "@/components/AuthGate";
import { TriageApp } from "@/components/TriageApp";

export default function Home() {
  return (
    <AuthGate>
      <TriageApp />
    </AuthGate>
  );
}

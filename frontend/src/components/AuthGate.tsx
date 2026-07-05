"use client";

import { SignIn } from "@clerk/nextjs";
import { LoadingShell } from "./ConnectionBanner";
import { useAppAuth } from "./Providers";

export function AuthGate({ children }: { children: React.ReactNode }) {
  const { isLoaded, isSignedIn, clerkEnabled } = useAppAuth();

  if (!clerkEnabled) {
    return (
      <div className="grid min-h-[100dvh] place-items-center bg-[#06080f] px-6 text-center">
        <div className="max-w-md rounded-2xl border border-amber-500/30 bg-amber-500/10 p-8">
          <h1 className="text-lg font-semibold text-amber-100">Authentication required</h1>
          <p className="mt-3 text-sm leading-relaxed text-amber-200/80">
            Set <code className="text-cyan-300">NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY</code> and{" "}
            <code className="text-cyan-300">CLERK_SECRET_KEY</code> in Vercel environment variables, then
            redeploy.
          </p>
        </div>
      </div>
    );
  }

  if (!isLoaded) {
    return <LoadingShell />;
  }

  if (!isSignedIn) {
    return (
      <div className="grid min-h-[100dvh] place-items-center bg-[#06080f] px-4">
        <SignIn
          routing="path"
          path="/sign-in"
          signUpUrl="/sign-up"
          appearance={{
            variables: {
              colorPrimary: "#6366f1",
              colorBackground: "#0c1220",
            },
          }}
        />
      </div>
    );
  }

  return children;
}

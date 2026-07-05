"use client";

import { ClerkProvider, useAuth } from "@clerk/nextjs";
import { createContext, useContext, type ReactNode } from "react";

export interface AppAuth {
  getToken: () => Promise<string | null>;
  isSignedIn: boolean;
  isLoaded: boolean;
  clerkEnabled: boolean;
}

const disabledAuth: AppAuth = {
  getToken: async () => null,
  isSignedIn: false,
  isLoaded: true,
  clerkEnabled: false,
};

const AuthContext = createContext<AppAuth>(disabledAuth);

function ClerkBridge({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const value: AppAuth = {
    getToken: () => auth.getToken(),
    isSignedIn: auth.isSignedIn ?? false,
    isLoaded: auth.isLoaded,
    clerkEnabled: true,
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function Providers({ children }: { children: ReactNode }) {
  const key = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  if (!key) {
    return <AuthContext.Provider value={disabledAuth}>{children}</AuthContext.Provider>;
  }
  return (
    <ClerkProvider publishableKey={key} signInUrl="/sign-in" signUpUrl="/sign-up">
      <ClerkBridge>{children}</ClerkBridge>
    </ClerkProvider>
  );
}

export function useAppAuth() {
  return useContext(AuthContext);
}

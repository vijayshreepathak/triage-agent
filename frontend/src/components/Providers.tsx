"use client";

import { ClerkProvider, useAuth } from "@clerk/nextjs";
import { createContext, useContext, type ReactNode } from "react";

export interface AppAuth {
  getToken: () => Promise<string | null>;
  isSignedIn: boolean;
  isLoaded: boolean;
}

const noopAuth: AppAuth = {
  getToken: async () => null,
  isSignedIn: true,
  isLoaded: true,
};

const AuthContext = createContext<AppAuth>(noopAuth);

function ClerkBridge({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const value: AppAuth = {
    getToken: () => auth.getToken(),
    isSignedIn: auth.isSignedIn ?? false,
    isLoaded: auth.isLoaded,
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function Providers({ children }: { children: ReactNode }) {
  const key = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  if (!key) {
    return <AuthContext.Provider value={noopAuth}>{children}</AuthContext.Provider>;
  }
  return (
    <ClerkProvider publishableKey={key}>
      <ClerkBridge>{children}</ClerkBridge>
    </ClerkProvider>
  );
}

export function useAppAuth() {
  return useContext(AuthContext);
}

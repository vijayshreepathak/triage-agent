import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <div className="grid min-h-[100dvh] place-items-center bg-[#06080f] px-4">
      <SignIn
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

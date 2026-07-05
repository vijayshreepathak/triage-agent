import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <div className="grid min-h-[100dvh] place-items-center bg-[#06080f] px-4">
      <SignUp
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

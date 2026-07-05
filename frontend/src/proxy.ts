import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

/** Backend proxy + Clerk auth pages — no login required for these paths only. */
const isPublicRoute = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)", "/engine(.*)"]);

export default clerkMiddleware(async (auth, req) => {
  if (!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) {
    return;
  }
  if (!isPublicRoute(req)) {
    await auth.protect();
  }
});

export const config = {
  matcher: [
    "/((?!_next|engine|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/__clerk/:path*",
  ],
};

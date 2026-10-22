import { ClerkProvider } from "@clerk/react"
import { shadcn } from "@clerk/themes"
import { useNavigate } from "react-router"
import { ErrorBoundary } from "@/components/layout/ErrorBoundary"
import { AppRoutes } from "@/app/routes"

const publishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY

// ClerkProvider sits inside the router so Clerk components navigate with
// React Router instead of reloading the page.
export function RootLayout() {
  const navigate = useNavigate()

  if (!publishableKey) {
    return (
      <div className="mx-auto max-w-md p-8 text-sm">
        <h1 className="mb-2 text-lg font-semibold">Clerk key missing</h1>
        <p className="text-muted-foreground">
          Set CLERK_PUBLISHABLE_KEY in the repo-root .env and restart the dev
          server.
        </p>
      </div>
    )
  }

  return (
    <ClerkProvider
      publishableKey={publishableKey}
      routerPush={(to) => navigate(to)}
      routerReplace={(to) => navigate(to, { replace: true })}
      afterSignOutUrl="/"
      taskUrls={{ "choose-organization": "/session-tasks/choose-organization" }}
      appearance={{ theme: shadcn }}
    >
      <ErrorBoundary>
        <AppRoutes />
      </ErrorBoundary>
    </ClerkProvider>
  )
}

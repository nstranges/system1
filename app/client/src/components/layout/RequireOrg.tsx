import {
  CreateOrganization,
  RedirectToTasks,
  Show,
  useAuth,
  useSession,
} from "@clerk/react"
import { Fragment, type ReactNode } from "react"
import { Navigate } from "react-router"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"

function OrgGate({ children }: { children: ReactNode }) {
  const { isLoaded, orgId } = useAuth()
  if (!isLoaded) return null
  if (!orgId) {
    return (
      <div className="flex min-h-svh items-center justify-center bg-muted/40 p-6">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Create your team</CardTitle>
            <CardDescription>
              system1 works per team. Create one to get started, or ask a
              teammate to invite you.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex justify-center">
            <CreateOrganization afterCreateOrganizationUrl="/app" />
          </CardContent>
        </Card>
      </div>
    )
  }
  // Keyed on the organization so switching teams remounts the pages and drops
  // anything cached for the previous one.
  return <Fragment key={orgId}>{children}</Fragment>
}

// A pending session is signed in but has an unfinished task (choosing an
// organization). Clerk's `Show` counts it as signed out, so send it to the task.
function SignedOutFallback() {
  const { isLoaded, session } = useSession()
  if (!isLoaded) return null
  if (session?.status === "pending") return <RedirectToTasks />
  return <Navigate to="/sign-in" replace />
}

export function RequireOrg({ children }: { children: ReactNode }) {
  return (
    <Show when="signed-in" fallback={<SignedOutFallback />}>
      <OrgGate>{children}</OrgGate>
    </Show>
  )
}

import { TaskChooseOrganization } from "@clerk/react"
import { AuthLayout } from "./AuthLayout"

// Sign-in leaves the session pending until the user picks or creates an
// organization, because personal accounts are turned off.
export function ChooseOrganizationPage() {
  return (
    <AuthLayout>
      <TaskChooseOrganization redirectUrlComplete="/app" />
    </AuthLayout>
  )
}

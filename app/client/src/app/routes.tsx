import { Route, Routes } from "react-router"
import { ErrorBoundary } from "@/components/layout/ErrorBoundary"
import { AppShell } from "@/components/layout/AppShell"
import { RequireOrg } from "@/components/layout/RequireOrg"
import { ChooseOrganizationPage } from "@/features/auth/ChooseOrganizationPage"
import { SignInPage } from "@/features/auth/SignInPage"
import { SignUpPage } from "@/features/auth/SignUpPage"
import { LandingPage } from "@/features/landing/LandingPage"
import { DashboardPage } from "@/features/dashboard/DashboardPage"
import { WorkspacePage } from "@/features/workspace/WorkspacePage"
import { TeamPage } from "@/features/team/TeamPage"

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/sign-in/*" element={<SignInPage />} />
      <Route path="/sign-up/*" element={<SignUpPage />} />
      <Route
        path="/session-tasks/choose-organization"
        element={<ChooseOrganizationPage />}
      />
      <Route
        path="/app"
        element={
          <RequireOrg>
            <AppShell />
          </RequireOrg>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route
          path="p/:projectId/:stage"
          element={
            <ErrorBoundary>
              <WorkspacePage />
            </ErrorBoundary>
          }
        />
        <Route path="team/*" element={<TeamPage />} />
      </Route>
    </Routes>
  )
}

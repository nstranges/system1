import { OrganizationSwitcher, UserButton } from "@clerk/react"
import { Link, Outlet } from "react-router"

export function AppShell() {
  return (
    <div className="min-h-svh bg-background">
      <header className="border-b">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
          <Link to="/app" className="text-lg font-semibold tracking-tight">
            system<span className="text-primary">1</span>
          </Link>
          <OrganizationSwitcher
            hidePersonal
            afterSelectOrganizationUrl="/app"
            afterCreateOrganizationUrl="/app"
          />
          <nav className="ml-auto flex items-center gap-4 text-sm">
            <Link
              to="/app/team"
              className="text-muted-foreground hover:text-foreground"
            >
              Team
            </Link>
            <UserButton />
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}

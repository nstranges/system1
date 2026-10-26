import { OrganizationSwitcher, UserButton } from "@clerk/react"
import { Link, Outlet, useMatch } from "react-router"
import { cn } from "@/lib/utils"

export function AppShell() {
  // A project's workspace has a rail, a canvas and the assistant side by side.
  const wide = useMatch("/app/p/*") !== null
  const width = wide ? "max-w-[1600px]" : "max-w-6xl"
  return (
    <div className="min-h-svh bg-background">
      <header className="sticky top-0 z-30 border-b bg-background/95 backdrop-blur">
        <div className={cn("mx-auto flex h-14 items-center gap-4 px-4", width)}>
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
      <main className={cn("mx-auto px-4 py-8", width)}>
        <Outlet />
      </main>
    </div>
  )
}

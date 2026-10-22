import type { ReactNode } from "react"
import { Link } from "react-router"

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted/40 p-6">
      <Link to="/" className="text-lg font-semibold tracking-tight">
        system<span className="text-primary">1</span>
      </Link>
      {children}
    </div>
  )
}

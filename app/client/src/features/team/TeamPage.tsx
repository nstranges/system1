import { OrganizationProfile } from "@clerk/react"
import { ArrowLeft, X } from "lucide-react"
import { useEffect } from "react"
import { Link, useNavigate } from "react-router"
import { Button } from "@/components/ui/button"

export function TeamPage() {
  const navigate = useNavigate()

  // Listens on the window because focus is usually inside Clerk's own markup.
  // Clerk's inner modals and open dialogs handle Escape themselves.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented) return
      if (document.querySelector('[role="dialog"], .cl-modalBackdrop')) return
      navigate("/app")
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [navigate])
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Link
          to="/app"
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" /> Back to projects
        </Link>
        <Button
          variant="ghost"
          size="icon"
          aria-label="Close"
          nativeButton={false}
          render={<Link to="/app" />}
        >
          <X />
        </Button>
      </div>
      <div className="flex justify-center">
        <OrganizationProfile routing="path" path="/app/team" />
      </div>
    </div>
  )
}

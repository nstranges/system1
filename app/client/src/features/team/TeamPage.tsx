import { OrganizationProfile } from "@clerk/react"

export function TeamPage() {
  return (
    <div className="flex justify-center">
      <OrganizationProfile routing="path" path="/app/team" />
    </div>
  )
}

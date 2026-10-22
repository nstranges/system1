import { Badge } from "@/components/ui/badge"
import type { components } from "@/lib/api/schema"

const RATING = {
  good: { label: "Good fit", variant: "default" },
  workable: { label: "Workable", variant: "secondary" },
  poor: { label: "Poor fit", variant: "destructive" },
} as const

export function FitCard({
  event,
}: {
  event: components["schemas"]["FitEvent"]
}) {
  const r = RATING[event.rating]
  return (
    <div className="space-y-2 rounded-lg border bg-card p-3">
      <Badge variant={r.variant}>{r.label}</Badge>
      <ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground">
        {event.reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
    </div>
  )
}

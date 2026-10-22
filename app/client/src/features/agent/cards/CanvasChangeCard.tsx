import { Link } from "react-router"
import type { CanvasEvent } from "../useAgent"

export function CanvasChangeCard({
  event,
  projectId,
}: {
  event: CanvasEvent
  projectId: string
}) {
  return (
    <div className="space-y-1.5 rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm">
      <p className="font-medium">Rules updated</p>
      {event.changed.length > 0 && (
        <ul className="list-disc space-y-0.5 pl-4 text-muted-foreground">
          {event.changed.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      )}
      <Link
        to={`/app/p/${projectId}/rules`}
        className="inline-block text-primary underline-offset-4 hover:underline"
      >
        Open the rules
      </Link>
    </div>
  )
}

import { ResultRow } from "@/features/playground/ResultRow"
import type { components } from "@/lib/api/schema"

export function TryResultCard({
  event,
}: {
  event: components["schemas"]["TryResultEvent"]
}) {
  const { result } = event
  return (
    <div className="space-y-2">
      <p className="rounded-lg bg-muted p-2 text-sm whitespace-pre-wrap">
        {event.input}
      </p>
      {result.results.map((r) => (
        <ResultRow
          key={r.lane}
          result={r}
          recordedAnswer={result.recorded?.[r.lane]}
          gold={result.gold ?? null}
        />
      ))}
    </div>
  )
}

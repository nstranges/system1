import { Check } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { FeedbackControls } from "@/features/improve/FeedbackControls"
import type { LaneResult, PolicyOption } from "@/lib/api/types"

export const LANE_NAMES: Record<string, string> = {
  jev_labels: "Jev, options only",
  jev: "Jev + your rules",
  sys1: "Your model",
}

function topProbability(
  r: LaneResult,
  label: string | null | undefined,
): number | null {
  const values = Object.values(r.probabilities ?? {})
  if (values.length === 0 || label == null) return null
  return Math.max(...values)
}

export function ResultRow({
  result,
  recordedAnswer,
  gold,
  options,
}: {
  result: LaneResult
  // Offline prediction for this sample; shown in place of a live answer.
  recordedAnswer?: string
  gold: string | null
  // Without options (e.g. in the assistant's chat card) no feedback buttons show.
  options?: PolicyOption[]
}) {
  const isModel = result.lane === "sys1"
  const answer = recordedAnswer ?? result.label
  const p = recordedAnswer ? null : topProbability(result, answer)
  const right = gold !== null && answer !== null && answer === gold

  return (
    <div
      className={cn(
        "grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 rounded-lg border p-3 sm:grid-cols-[12rem_1fr_9rem_5rem]",
        isModel ? "border-primary/40 bg-primary/5" : "bg-card",
      )}
    >
      <div className="flex items-center gap-2 text-sm font-medium">
        <span
          className={cn(
            "size-2 rounded-full",
            isModel ? "bg-primary" : "bg-jev",
          )}
        />
        {LANE_NAMES[result.lane] ?? result.lane}
        {recordedAnswer && <Badge variant="outline">recorded</Badge>}
      </div>
      {result.error && !recordedAnswer ? (
        <p className="col-span-2 text-sm text-destructive sm:col-span-3">
          {result.error}
        </p>
      ) : (
        <>
          <div className="flex items-center gap-1.5 font-mono text-sm sm:order-none">
            {answer ?? "No answer"}
            {gold !== null && answer !== null && (
              <span
                className={right ? "text-primary" : "text-destructive"}
                aria-label={right ? "Right" : "Wrong"}
              >
                {right ? <Check className="size-4" /> : "✗"}
              </span>
            )}
          </div>
          <div className="col-span-2 flex items-center gap-2 sm:col-span-1">
            {p !== null ? (
              <>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn("h-full", isModel ? "bg-primary" : "bg-jev")}
                    style={{ width: `${Math.round(p * 100)}%` }}
                  />
                </div>
                <span className="w-10 text-right text-xs text-muted-foreground">
                  {Math.round(p * 100)}%
                </span>
              </>
            ) : (
              <span className="text-xs text-muted-foreground">
                {recordedAnswer ? "Not recorded" : ""}
              </span>
            )}
          </div>
          <div className="text-right text-xs text-muted-foreground">
            {result.latency_ms != null && !recordedAnswer
              ? `${Math.round(result.latency_ms)} ms`
              : ""}
          </div>
          {result.decision_id && options && !recordedAnswer && (
            <div className="col-span-2 sm:col-span-4">
              <FeedbackControls
                decisionId={result.decision_id}
                options={options}
              />
            </div>
          )}
        </>
      )}
    </div>
  )
}

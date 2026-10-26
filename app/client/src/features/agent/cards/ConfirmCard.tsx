import { useState } from "react"
import { Button } from "@/components/ui/button"
import { useApi } from "@/lib/api/client"
import { readProblem } from "@/lib/api/types"
import type { components } from "@/lib/api/schema"

type Outcome = { kind: "confirmed" | "cancelled" | "notice"; text: string }

function minutes(m: number) {
  return m < 1 ? "under a minute" : `about ${Math.round(m)} min`
}

export function ConfirmCard({
  event,
  projectId,
}: {
  event: components["schemas"]["ConfirmEvent"]
  projectId: string
}) {
  const api = useApi()
  const [pending, setPending] = useState(false)
  const [outcome, setOutcome] = useState<Outcome | null>(null)
  // A failed confirm leaves the action pending on the server, so it can retry.
  const [problem, setProblem] = useState<string | null>(null)

  async function decide(kind: "confirm" | "cancel") {
    setPending(true)
    setProblem(null)
    const params = {
      params: {
        path: { project_id: projectId, action_id: event.action_id },
      },
    }
    try {
      const res =
        kind === "confirm"
          ? await api.POST(
              "/api/projects/{project_id}/actions/{action_id}/confirm",
              params,
            )
          : await api.POST(
              "/api/projects/{project_id}/actions/{action_id}/cancel",
              params,
            )
      if (res.data) {
        setOutcome(
          kind === "confirm"
            ? { kind: "confirmed", text: "Confirmed. This is underway." }
            : { kind: "cancelled", text: "Cancelled. Nothing was started." },
        )
      } else {
        const p = readProblem(res.error)
        if (p.code === "already_resolved") {
          setOutcome({ kind: "notice", text: p.message })
        } else {
          setProblem(p.message)
        }
      }
    } catch {
      setProblem("We couldn't reach the server. Try again.")
    }
    setPending(false)
  }

  return (
    <div className="space-y-2 rounded-lg border bg-card p-3">
      <p className="text-sm font-medium">{event.title}</p>
      <p className="text-sm text-muted-foreground">{event.detail}</p>
      {event.examples != null && (
        <p className="text-xs text-muted-foreground">
          {event.examples} examples
        </p>
      )}
      <p className="text-xs text-muted-foreground">
        Takes {minutes(event.est_minutes)}.
      </p>
      {outcome ? (
        <p className="text-sm font-medium">{outcome.text}</p>
      ) : (
        <>
          {problem && <p className="text-sm text-destructive">{problem}</p>}
          <div className="flex gap-2">
            <Button
              size="sm"
              disabled={pending}
              onClick={() => void decide("confirm")}
            >
              Confirm
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={pending}
              onClick={() => void decide("cancel")}
            >
              Cancel
            </Button>
          </div>
        </>
      )}
    </div>
  )
}

import { useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { NativeSelect } from "@/features/rules/fields"
import { useApi } from "@/lib/api/client"
import { readProblem, type PolicyOption } from "@/lib/api/types"

// "Looks right" confirms the shown answer; "Wrong" asks for the right option.
export function FeedbackControls({
  decisionId,
  options,
  onSent,
}: {
  decisionId: string
  options: PolicyOption[]
  onSent?: () => void
}) {
  const api = useApi()
  const [picking, setPicking] = useState(false)
  const [choice, setChoice] = useState("")
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)

  async function send(kind: "confirm" | "correction", label?: string) {
    setBusy(true)
    const { response, error } = await api.POST(
      "/api/decisions/{decision_id}/feedback",
      {
        params: { path: { decision_id: decisionId } },
        body: { kind, correct_label: label ?? null },
      },
    )
    setBusy(false)
    if (!response.ok) return void toast.error(readProblem(error).message)
    setSent(true)
    setPicking(false)
    onSent?.()
  }

  if (sent) {
    return <span className="text-xs text-muted-foreground">Thanks, noted.</span>
  }
  if (picking) {
    return (
      <div className="flex items-center gap-2">
        <div className="w-56">
          <NativeSelect
            aria-label="The right answer"
            value={choice}
            onChange={(e) => setChoice(e.target.value)}
          >
            <option value="">What should it be?</option>
            {options.map((o) => (
              <option key={o.key} value={o.key}>
                {o.name}
              </option>
            ))}
          </NativeSelect>
        </div>
        <Button
          size="sm"
          disabled={!choice || busy}
          onClick={() => void send("correction", choice)}
        >
          Save
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setPicking(false)}>
          Cancel
        </Button>
      </div>
    )
  }
  return (
    <div className="flex items-center gap-1">
      <Button
        size="sm"
        variant="outline"
        disabled={busy}
        aria-label="This answer is right"
        onClick={() => void send("confirm")}
      >
        ✓ Right
      </Button>
      <Button
        size="sm"
        variant="outline"
        aria-label="This answer is wrong"
        onClick={() => setPicking(true)}
      >
        ✗ Wrong
      </Button>
    </div>
  )
}

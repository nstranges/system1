import { useState } from "react"
import { toast } from "sonner"
import { BucketSwatch } from "@/components/BucketChip"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { useApi } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"
import { readProblem, type PolicyOption } from "@/lib/api/types"
import { bucketIndex } from "@/lib/buckets"

export type InboxItem = components["schemas"]["InboxItem"]

const pct = (v: number) => `${Math.round(v * 100)}%`

function stateText(state: unknown): string {
  if (state && typeof state === "object" && !Array.isArray(state)) {
    const ticket = (state as Record<string, unknown>).ticket as
      { subject?: string; body?: string } | undefined
    if (ticket && (ticket.subject || ticket.body)) {
      return [ticket.subject, ticket.body].filter(Boolean).join("\n\n")
    }
  }
  return typeof state === "string" ? state : JSON.stringify(state, null, 2)
}

// "How sure" from the gap between the top two answers; flagged items have none.
function howSure(margin: number | null | undefined): string {
  if (margin == null) return "Flagged for review"
  if (margin < 0.2) return "Not sure"
  if (margin < 0.5) return "Fairly sure"
  return "Sure"
}

// One answer to check. The model's top guesses are one click away; anything else is a search away. Picking the
// answer it gave confirms it; picking another bucket corrects it.
export function InboxCard({
  item,
  options,
  onSorted,
}: {
  item: InboxItem
  options: PolicyOption[]
  onSorted: (decisionId: string) => void
}) {
  const api = useApi()
  const [searching, setSearching] = useState(false)
  const [query, setQuery] = useState("")
  const [busy, setBusy] = useState(false)
  const names = new Map(options.map((o) => [o.key, o.name]))
  const name = (k: string) => names.get(k) ?? k
  const guesses = (item.guesses ?? []).filter((g) => names.has(g.key))
  const matches = options
    .filter((o) =>
      `${o.name} ${o.key}`.toLowerCase().includes(query.trim().toLowerCase()),
    )
    .slice(0, 30)

  async function sort(key: string) {
    setBusy(true)
    const confirm = key === item.answer
    try {
      const { response, error } = await api.POST(
        "/api/decisions/{decision_id}/feedback",
        {
          params: { path: { decision_id: item.decision_id } },
          body: {
            kind: confirm ? "confirm" : "correction",
            correct_label: confirm ? null : key,
          },
        },
      )
      if (!response.ok) return void toast.error(readProblem(error).message)
      onSorted(item.decision_id)
    } catch {
      toast.error("We couldn't reach the server.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card>
      <CardContent className="space-y-3">
        <p className="font-voice line-clamp-6 whitespace-pre-wrap">
          {stateText(item.state)}
        </p>
        <p className="text-xs text-muted-foreground">
          It said{" "}
          <span className="font-medium text-foreground">
            {item.answer ? name(item.answer) : "nothing"}
          </span>
          . {howSure(item.how_sure)}
        </p>
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Which bucket is right?
          </p>
          <div className="flex flex-wrap gap-2">
            {guesses.map((g) => (
              <Button
                key={g.key}
                size="sm"
                variant={g.key === item.answer ? "default" : "outline"}
                disabled={busy}
                onClick={() => void sort(g.key)}
              >
                <BucketSwatch index={bucketIndex(options, g.key)} />
                {name(g.key)}
                <span className="tabular-nums opacity-70">{pct(g.p)}</span>
              </Button>
            ))}
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              onClick={() => setSearching((s) => !s)}
            >
              {searching ? "Close" : "Something else…"}
            </Button>
          </div>
          {searching && (
            <div className="space-y-2 rounded-lg border p-2">
              <Input
                autoFocus
                aria-label="Find a bucket"
                placeholder="Find a bucket"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              <div className="flex max-h-48 flex-wrap gap-1 overflow-y-auto">
                {matches.map((o) => (
                  <Button
                    key={o.key}
                    size="sm"
                    variant="ghost"
                    disabled={busy}
                    onClick={() => void sort(o.key)}
                  >
                    <BucketSwatch index={bucketIndex(options, o.key)} />
                    {o.name}
                  </Button>
                ))}
                {matches.length === 0 && (
                  <p className="p-1 text-sm text-muted-foreground">
                    No bucket matches that.
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

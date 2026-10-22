import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { useApi } from "@/lib/api/client"
import { readProblem, type PolicyOut, type Project } from "@/lib/api/types"
import { FeedbackControls } from "./FeedbackControls"

type InboxItem = {
  decision_id: string
  state: unknown
  answer: string | null
  lane: string
}

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

export function ImproveCanvas({
  project,
  policy,
}: {
  project: Project
  policy: PolicyOut
}) {
  const api = useApi()
  const [items, setItems] = useState<InboxItem[] | null>(null)
  const [count, setCount] = useState(0)
  const [failed, setFailed] = useState(false)

  const load = useCallback(async () => {
    const path = { params: { path: { project_id: project.id } } }
    try {
      const [inbox, pool] = await Promise.all([
        api.GET("/api/projects/{project_id}/inbox", path),
        api.GET("/api/projects/{project_id}/training-pool", path),
      ])
      if (inbox.data) {
        setItems(inbox.data.items)
        setFailed(false)
      } else {
        setFailed(true)
        toast.error(readProblem(inbox.error).message)
      }
      if (pool.data) setCount(pool.data.count)
    } catch (e) {
      setFailed(true)
      toast.error(readProblem(e).message)
    }
  }, [api, project.id])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold tracking-tight">Improve</h2>
        <p className="text-sm text-muted-foreground">
          Answers your model wasn't sure about. Tell it the right one and it
          learns from it.
        </p>
      </div>
      <p className="rounded-lg bg-muted px-3 py-2 text-sm">
        <span className="font-medium">{count}</span> new{" "}
        {count === 1 ? "answer" : "answers"} since your last training
      </p>
      {failed && (
        <p className="flex items-center gap-3 text-sm text-destructive">
          We couldn't load this list.
          <Button size="sm" variant="outline" onClick={() => void load()}>
            Try again
          </Button>
        </p>
      )}
      {items === null ? null : items.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nothing to look at right now. Anything your model isn't sure about
          will show up here.
        </p>
      ) : (
        <ul className="space-y-3">
          {items.map((it) => (
            <li key={it.decision_id}>
              <Card>
                <CardContent className="space-y-3">
                  <p className="line-clamp-6 whitespace-pre-wrap text-sm">
                    {stateText(it.state)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    It said:{" "}
                    <span className="font-mono">
                      {it.answer ?? "no answer"}
                    </span>
                  </p>
                  <FeedbackControls
                    decisionId={it.decision_id}
                    options={policy.policy.options}
                    canConfirm={policy.policy.options.some(
                      (o) => o.key === it.answer,
                    )}
                    onSent={() => void load()}
                  />
                </CardContent>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

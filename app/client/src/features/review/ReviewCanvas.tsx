import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { FLAGSHIP_TEMPLATE } from "@/features/data/DataCanvas"
import {
  HealthPanel,
  exampleTotal,
  useHealth,
} from "@/features/data/HealthPanel"
import { useApi } from "@/lib/api/client"
import { readProblem, type PolicyOut, type Project } from "@/lib/api/types"
import { SortCard, type ReviewExample } from "./SortCard"

export function ReviewCanvas({
  project,
  policy,
}: {
  project: Project
  policy: PolicyOut
}) {
  const flagship = project.template_id === FLAGSHIP_TEMPLATE
  if (flagship) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Built with exact rules</CardTitle>
          <CardDescription>
            Nothing to sort here — these examples were labelled by exact rules.
          </CardDescription>
        </CardHeader>
      </Card>
    )
  }
  return <Queue project={project} policy={policy} />
}

function Queue({ project, policy }: { project: Project; policy: PolicyOut }) {
  const api = useApi()
  const { health, failed, reload } = useHealth(project.id)
  const [cards, setCards] = useState<ReviewExample[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const { data, error: err } = await api.GET(
        "/api/projects/{project_id}/review",
        { params: { path: { project_id: project.id } } },
      )
      if (data) setCards(data)
      else setError(readProblem(err).message)
    } catch {
      setError("We couldn't reach the server.")
    }
  }, [api, project.id])

  useEffect(() => {
    void load()
  }, [load])

  async function act(ex: ReviewExample, action: "agree" | "move", to?: string) {
    if (busyId) return
    setBusyId(ex.id)
    try {
      const { error: err, response } = await api.POST(
        "/api/examples/{example_id}/review",
        {
          params: { path: { example_id: ex.id } },
          body: { action, to },
        },
      )
      if (response.ok) {
        // The queue is capped, so an emptied list may hide more behind it.
        const left = (cards ?? []).filter((c) => c.id !== ex.id)
        setCards(left)
        if (left.length === 0) void load()
        void reload()
        const name = policy.policy.options.find((o) => o.key === to)?.name
        toast.success(
          action === "agree" ? "Marked as right" : `Moved to ${name ?? to}`,
        )
      } else {
        toast.error(readProblem(err).message)
      }
    } catch {
      toast.error("We couldn't reach the server.")
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="space-y-6">
      {exampleTotal(health) > 0 && (
        <HealthPanel policy={policy.policy} health={health} failed={failed} />
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      {!cards && !error && <Skeleton className="h-32 w-full" />}
      {cards && cards.length === 0 && (
        <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
          Nothing to review. Generated examples you should check will show up
          here.
        </p>
      )}
      {cards && cards.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {cards.length} {cards.length === 1 ? "card" : "cards"}
          </p>
          {cards.map((c) => (
            <SortCard
              key={c.id}
              example={c}
              buckets={policy.policy.options}
              busy={busyId !== null}
              onAgree={() => void act(c, "agree")}
              onMove={(to) => void act(c, "move", to)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

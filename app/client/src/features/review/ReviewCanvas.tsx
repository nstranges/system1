import { useCallback, useEffect, useRef, useState } from "react"
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
import { isTypingTarget, reviewKey } from "./keys"
import { SortCard, type ReviewExample } from "./SortCard"
import { useProgressReload } from "@/features/workspace/useProgress"

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
  const reloadProgress = useProgressReload()
  const [cards, setCards] = useState<ReviewExample[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  // Which card the keys act on. It keeps its position when a card is sorted, so it lands on the next one.
  const [active, setActive] = useState(0)
  const options = policy.policy.options
  const activeIndex = Math.min(active, Math.max((cards?.length ?? 0) - 1, 0))

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

  // The queue is capped, so after an action empties it more may be waiting.
  const acted = useRef(false)
  const emptied = cards !== null && cards.length === 0
  useEffect(() => {
    if (emptied && acted.current) {
      acted.current = false
      void load()
    }
  }, [emptied, load])

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
        setCards((cs) => cs?.filter((c) => c.id !== ex.id) ?? cs)
        acted.current = true
        void reload()
        reloadProgress()
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

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (!cards || cards.length === 0 || busyId) return
      if (e.metaKey || e.ctrlKey || e.altKey || e.repeat) return
      if (isTypingTarget(e.target as HTMLElement | null)) return
      // Enter on a focused button or link already activates it.
      const tag = (e.target as HTMLElement | null)?.tagName
      if (e.key === "Enter" && (tag === "BUTTON" || tag === "A")) return
      const action = reviewKey(e.key, options.length)
      if (!action) return
      e.preventDefault()
      const card = cards[activeIndex]
      if (action.kind === "next")
        setActive(Math.min(activeIndex + 1, cards.length - 1))
      else if (action.kind === "prev") setActive(Math.max(activeIndex - 1, 0))
      else if (action.kind === "agree") void act(card, "agree")
      else if (options[action.index].key === card.label) void act(card, "agree")
      else void act(card, "move", options[action.index].key)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  })

  const scrolled = useRef(false)
  useEffect(() => {
    // Skip the first run so opening the step doesn't jump the page.
    if (!scrolled.current) {
      scrolled.current = true
      return
    }
    document
      .getElementById(`review-card-${activeIndex}`)
      ?.scrollIntoView({ block: "nearest" })
  }, [activeIndex])

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
            {cards.length} {cards.length === 1 ? "card" : "cards"}. Keys: 1–9
            sorts into a bucket, Enter keeps it, J and K move between cards.
          </p>
          {cards.map((c, i) => (
            <SortCard
              key={c.id}
              example={c}
              buckets={options}
              busy={busyId !== null}
              active={i === activeIndex}
              index={i}
              onAgree={() => void act(c, "agree")}
              onMove={(to) => void act(c, "move", to)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

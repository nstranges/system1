import { useAuth } from "@clerk/react"
import { Loader2 } from "lucide-react"
import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useApi } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"
import {
  readProblem,
  type PolicyOut,
  type Project,
  type TrainedModel,
} from "@/lib/api/types"
import { recalledJob, rememberJob } from "@/features/data/JobProgress"
import { TrainProgress } from "@/features/train/TrainProgress"
import { InboxCard, type InboxItem } from "./InboxCard"
import { ModelHistory } from "./ModelHistory"

type Summary = components["schemas"]["ImproveSummary"]
type Comparison = components["schemas"]["Comparison"]

const pct = (v: number) => `${Math.round(v * 100)}%`

// The loop after launch: check what the live model wasn't sure about, teach it again from those answers, and
// make the new version live only when it does better on the same test examples.
export function ImproveCanvas({
  project,
  policy,
}: {
  project: Project
  policy: PolicyOut
}) {
  const api = useApi()
  const [items, setItems] = useState<InboxItem[] | null>(null)
  const [summary, setSummary] = useState<Summary | null>(null)
  const [models, setModels] = useState<TrainedModel[]>([])
  const [comparison, setComparison] = useState<Comparison | null>(null)
  const [failed, setFailed] = useState(false)
  const [jobId, setJobId] = useState<string | null>(() =>
    recalledJob(project.id),
  )
  const options = policy.policy.options
  const names = new Map(options.map((o) => [o.key, o.name]))

  const load = useCallback(async () => {
    const path = { params: { path: { project_id: project.id } } }
    try {
      const [inbox, sum, list] = await Promise.all([
        api.GET("/api/projects/{project_id}/inbox", path),
        api.GET("/api/projects/{project_id}/improve", path),
        api.GET("/api/models", {
          params: { query: { project_id: project.id } },
        }),
      ])
      setFailed(!inbox.data)
      if (inbox.data) setItems(inbox.data.items)
      else toast.error(readProblem(inbox.error).message)
      if (sum.data) setSummary(sum.data)
      const all = list.data ?? []
      setModels(all)
      // The newest version is worth a comparison only while it isn't the live one.
      const newest = all[0]
      if (newest && !newest.live) {
        const { data } = await api.GET("/api/models/{model_id}/compare", {
          params: { path: { model_id: newest.id } },
        })
        setComparison(data ?? null)
      } else {
        setComparison(null)
      }
    } catch {
      setFailed(true)
      toast.error("We couldn't reach the server.")
    }
  }, [api, project.id])

  useEffect(() => {
    void load()
  }, [load])

  function sorted(decisionId: string) {
    setItems((all) => (all ?? []).filter((i) => i.decision_id !== decisionId))
    void api
      .GET("/api/projects/{project_id}/improve", {
        params: { path: { project_id: project.id } },
      })
      .then(({ data }) => data && setSummary(data))
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold tracking-tight">Improve</h2>
        <p className="text-sm text-muted-foreground">
          Check the answers your model wasn't sure about, then teach it again
          from them.
        </p>
      </div>

      {summary && <Stats summary={summary} />}

      <TeachAgain
        project={project}
        ready={summary?.ready ?? 0}
        hasModel={models.length > 0}
        jobId={jobId}
        onStarted={(id) => {
          rememberJob(project.id, id)
          setJobId(id)
        }}
        onDone={() => {
          rememberJob(project.id, null)
          setJobId(null)
          void load()
        }}
      />

      {comparison && (
        <CompareCard
          comparison={comparison}
          names={names}
          onLive={() => void load()}
        />
      )}

      {models.length >= 2 && (
        <Card>
          <CardHeader>
            <CardTitle>Your model over time</CardTitle>
            <CardDescription>
              Each version's score on the same test examples it never learned
              from.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ModelHistory models={models} />
          </CardContent>
        </Card>
      )}

      <section className="space-y-3">
        <h3 className="font-medium">To check</h3>
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
            Nothing to check right now. Answers your model gives in Try or
            through your endpoint show up here, least sure first.
          </p>
        ) : (
          <ul className="space-y-3">
            {items.map((it) => (
              <li key={it.decision_id}>
                <InboxCard item={it} options={options} onSorted={sorted} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

function Stats({ summary }: { summary: Summary }) {
  const tiles = [
    {
      label: "Waiting for a look",
      value: summary.waiting.toLocaleString(),
      note: "Least sure first",
    },
    {
      label: "Ready to learn from",
      value: summary.ready.toLocaleString(),
      note: "Checked answers since the last training",
    },
    {
      label: "Live model, as checked",
      value:
        summary.live_checked > 0
          ? pct(summary.live_right / summary.live_checked)
          : "–",
      note:
        summary.live_checked > 0
          ? `Right on ${summary.live_right} of ${summary.live_checked} your team checked`
          : "Check some answers to see this",
    },
  ]
  return (
    <dl className="grid gap-3 sm:grid-cols-3">
      {tiles.map((t) => (
        <div key={t.label} className="rounded-lg border p-3">
          <dt className="text-xs text-muted-foreground">{t.label}</dt>
          <dd className="text-lg font-semibold tabular-nums">{t.value}</dd>
          <dd className="text-xs text-muted-foreground">{t.note}</dd>
        </div>
      ))}
    </dl>
  )
}

function TeachAgain({
  project,
  ready,
  hasModel,
  jobId,
  onStarted,
  onDone,
}: {
  project: Project
  ready: number
  hasModel: boolean
  jobId: string | null
  onStarted: (jobId: string) => void
  onDone: () => void
}) {
  const api = useApi()
  const [starting, setStarting] = useState(false)

  async function start() {
    setStarting(true)
    try {
      const { data, error } = await api.POST(
        "/api/projects/{project_id}/training",
        { params: { path: { project_id: project.id } } },
      )
      if (data) onStarted(data.job_id)
      else toast.error(readProblem(error).message)
    } catch {
      toast.error("We couldn't reach the server.")
    } finally {
      setStarting(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Teach it again</CardTitle>
        <CardDescription>
          {ready > 0
            ? `Train a new version that also learns from the ${ready} ${ready === 1 ? "answer" : "answers"} your team checked. The live model keeps answering until you choose to switch.`
            : hasModel
              ? "Check some answers below first, so the new version has something new to learn from."
              : "Train your first model in the Train step."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {jobId ? (
          <TrainProgress jobId={jobId} onDone={onDone} />
        ) : (
          <Button
            disabled={ready === 0 || !hasModel || starting}
            onClick={() => void start()}
          >
            {starting && <Loader2 className="animate-spin" />}
            {starting ? "Starting…" : "Teach it again"}
          </Button>
        )}
      </CardContent>
    </Card>
  )
}

function CompareCard({
  comparison,
  names,
  onLive,
}: {
  comparison: Comparison
  names: Map<string, string>
  onLive: () => void
}) {
  const api = useApi()
  const { orgRole } = useAuth()
  const isAdmin = orgRole === "org:admin"
  const [busy, setBusy] = useState(false)
  const { candidate, live } = comparison
  const name = (k: string) => names.get(k) ?? k

  async function makeLive() {
    setBusy(true)
    try {
      const { data, error } = await api.POST("/api/models/{model_id}/live", {
        params: { path: { model_id: candidate.id } },
      })
      if (data) {
        toast("The new version now answers your endpoint")
        onLive()
      } else {
        toast.error(readProblem(error).message)
      }
    } catch {
      toast.error("We couldn't reach the server.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className={comparison.recommend ? "border-primary/50" : undefined}>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          New version vs the live one
          {comparison.recommend && <Badge>Recommended</Badge>}
        </CardTitle>
        <CardDescription>{comparison.sentence}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="grid grid-cols-2 gap-3">
          <Score label="Live model" model={live} />
          <Score label="New version" model={candidate} />
        </dl>
        {(comparison.improved.length > 0 || comparison.worsened.length > 0) && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Changes
              title="Got better"
              items={comparison.improved}
              name={name}
            />
            <Changes
              title="Got worse"
              items={comparison.worsened}
              name={name}
            />
          </div>
        )}
        {candidate.corrections_used ? (
          <p className="text-xs text-muted-foreground">
            It learned from {candidate.corrections_used} answers your team
            checked.
          </p>
        ) : null}
        <div className="flex flex-wrap items-center gap-3">
          <Button
            variant={comparison.recommend ? "default" : "outline"}
            disabled={!isAdmin || busy}
            onClick={() => void makeLive()}
          >
            {comparison.recommend ? "Make live" : "Make live anyway"}
          </Button>
          {!isAdmin && (
            <p className="text-xs text-muted-foreground">
              Only an admin of your team can change the live model.
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function Score({
  label,
  model,
}: {
  label: string
  model: TrainedModel | null | undefined
}) {
  return (
    <div className="rounded-lg border p-3">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">
        {model?.accuracy != null ? pct(model.accuracy) : "–"}
      </dd>
      <dd className="text-xs text-muted-foreground">
        {model
          ? `Trained ${new Date(model.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}`
          : "None yet"}
      </dd>
    </div>
  )
}

function Changes({
  title,
  items,
  name,
}: {
  title: string
  items: Comparison["improved"]
  name: (k: string) => string
}) {
  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium">{title}</h4>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">Nothing notable.</p>
      ) : (
        <ul className="divide-y rounded-lg border text-sm">
          {items.map((c) => (
            <li
              key={c.key}
              className="flex items-center justify-between gap-3 p-2"
            >
              <span className="min-w-0 truncate">{name(c.key)}</span>
              <span className="shrink-0 tabular-nums text-muted-foreground">
                {pct(c.before)} → {pct(c.after)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

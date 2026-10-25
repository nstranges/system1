import { Check, Loader2 } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useApi } from "@/lib/api/client"
import { LossDetails, readDetail } from "./LossDetails"
import type { components } from "@/lib/api/schema"

type Job = components["schemas"]["JobOut"]

const ACTIVE = ["queued", "running"]
const POLL_MS = 2000

// The server reports these four stages, in this order.
const STEPS = [
  {
    id: "preparing",
    label: "Preparing",
    text: "Loading the base model and your examples",
  },
  {
    id: "learning",
    label: "Learning",
    text: "Teaching the model from your training examples",
  },
  {
    id: "checking",
    label: "Checking",
    text: "Tuning how sure the model is of its answers",
  },
  {
    id: "testing",
    label: "Testing",
    text: "Scoring your model, the base model and Jev on the test examples",
  },
] as const

// SQLite hands timestamps back without a zone; they are UTC.
function parseTime(iso: string): number {
  return Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`)
}

function clock(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`
}

// Polls one training job, showing where it is and how long it has run. `onDone` fires once when it ends.
export function TrainProgress({
  jobId,
  examples,
  onDone,
}: {
  jobId: string
  examples?: { train: number; test: number }
  onDone: () => void
}) {
  const api = useApi()
  const [job, setJob] = useState<Job | null>(null)
  const [now, setNow] = useState(() => Date.now())
  const [trouble, setTrouble] = useState(false)
  const done = useRef(onDone)
  useEffect(() => {
    done.current = onDone
  })

  useEffect(() => {
    let live = true
    let timer: ReturnType<typeof setTimeout> | undefined
    async function tick() {
      try {
        const { data, response } = await api.GET("/api/jobs/{job_id}", {
          params: { path: { job_id: jobId } },
        })
        if (!live) return
        if (response.status === 404) {
          done.current()
          return
        }
        if (data) {
          setTrouble(false)
          setJob(data)
          if (!ACTIVE.includes(data.status)) {
            done.current()
            return
          }
        }
      } catch {
        if (!live) return
        setTrouble(true)
      }
      timer = setTimeout(() => void tick(), POLL_MS)
    }
    void tick()
    return () => {
      live = false
      clearTimeout(timer)
    }
  }, [api, jobId])

  const active = job === null || ACTIVE.includes(job.status)
  useEffect(() => {
    if (!active) return
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [active])

  if (!job) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        {trouble ? "We couldn't reach the server. Trying again…" : "Starting…"}
      </p>
    )
  }

  if (!active) {
    const ok = job.status === "succeeded"
    return (
      <p
        role={ok ? "status" : "alert"}
        className={ok ? "text-sm" : "text-sm text-destructive"}
      >
        {job.message ??
          (ok ? "Training finished." : "Training didn't finish. Try again.")}
      </p>
    )
  }

  const pct = Math.round(Math.min(1, Math.max(0, job.progress)) * 100)
  const current = Math.max(
    0,
    STEPS.findIndex((s) => s.id === job.stage),
  )
  const elapsed = now - parseTime(job.created_at)
  const detail =
    current === 1 && examples
      ? `Learning from ${examples.train.toLocaleString()} examples`
      : current === 3 && examples
        ? `Testing on ${examples.test.toLocaleString()} examples it never saw`
        : STEPS[current].text

  return (
    <div className="space-y-3" aria-live="polite">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="font-medium">
          {job.status === "queued" ? "Waiting for a GPU" : STEPS[current].label}
          … {pct}%
        </span>
        <span className="tabular-nums text-muted-foreground">
          {clock(elapsed)} elapsed
        </span>
      </div>
      <div
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        className="h-2 w-full overflow-hidden rounded-full bg-muted"
      >
        <div
          className="h-full bg-primary transition-all"
          style={{ width: `${Math.max(pct, 3)}%` }}
        />
      </div>
      <ol className="grid gap-1 text-sm sm:grid-cols-4">
        {STEPS.map((step, i) => (
          <li
            key={step.id}
            className={
              i === current
                ? "flex items-center gap-1.5 font-medium"
                : i < current
                  ? "flex items-center gap-1.5 text-muted-foreground"
                  : "flex items-center gap-1.5 text-muted-foreground/60"
            }
          >
            {i < current ? (
              <Check className="size-4" />
            ) : i === current ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <span className="size-4 text-center">·</span>
            )}
            {step.label}
          </li>
        ))}
      </ol>
      <p className="text-xs text-muted-foreground">
        {job.status === "queued" ? "Queued. A GPU is being set up." : detail}{" "}
        Training can take several minutes; you can leave this page.
      </p>
      <LossDetails detail={readDetail(job.result)} />
      {trouble && (
        <p className="text-xs text-muted-foreground">
          We couldn't reach the server. Trying again…
        </p>
      )}
    </div>
  )
}

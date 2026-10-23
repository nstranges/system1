import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { useApi } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

type Job = components["schemas"]["JobOut"]

const POLL_MS = 1500
const MAX_MS = 10_000
const MAX_FAILURES = 20
const STAGES: Record<string, string> = { writing: "Writing examples" }

function stageName(stage: string): string {
  return STAGES[stage] ?? stage.charAt(0).toUpperCase() + stage.slice(1)
}
const ACTIVE = ["queued", "running"]

const jobKey = (projectId: string) => `system1:job:${projectId}`
export function rememberJob(projectId: string, jobId: string | null) {
  try {
    if (jobId) sessionStorage.setItem(jobKey(projectId), jobId)
    else sessionStorage.removeItem(jobKey(projectId))
  } catch {
    // Storage can be blocked; resuming a job is a convenience only.
  }
}
export function recalledJob(projectId: string): string | null {
  try {
    return sessionStorage.getItem(jobKey(projectId))
  } catch {
    return null
  }
}

// Polls one job until it ends. `onDone` fires once when it does, whatever the
// outcome, so the caller can refresh its counts.
export function JobProgress({
  jobId,
  onDone,
  onRetry,
  onGone,
  resumed = false,
}: {
  jobId: string
  onDone: () => void
  onRetry?: () => void
  // The remembered job turned out to be finished or unknown.
  onGone?: () => void
  resumed?: boolean
}) {
  const api = useApi()
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lost, setLost] = useState(false)
  const done = useRef(onDone)
  const gone = useRef(onGone)
  useEffect(() => {
    done.current = onDone
    gone.current = onGone
  })

  useEffect(() => {
    let live = true
    let timer: ReturnType<typeof setTimeout> | undefined
    let first = resumed
    let failures = 0
    async function tick() {
      let ok = false
      try {
        const { data, response } = await api.GET("/api/jobs/{job_id}", {
          params: { path: { job_id: jobId } },
        })
        if (!live) return
        // An unknown job will never appear; retrying would only spin.
        if (response.status === 404) {
          gone.current?.()
          return
        }
        if (data) {
          ok = true
          failures = 0
          setError(null)
          setJob(data)
          if (!ACTIVE.includes(data.status)) {
            if (first) gone.current?.()
            else done.current()
            return
          }
        }
      } catch {
        if (!live) return
      }
      if (!ok) {
        failures += 1
        if (failures >= MAX_FAILURES) {
          setError("We lost track of this job. Refresh to check.")
          setLost(true)
          // Release the buttons and the stored id; the message stays up.
          done.current()
          return
        }
        setError("We couldn't reach the server. Trying again…")
      }
      first = false
      const wait = Math.min(MAX_MS, POLL_MS * 1.5 ** failures)
      timer = setTimeout(() => void tick(), wait)
    }
    void tick()
    return () => {
      live = false
      clearTimeout(timer)
    }
  }, [api, jobId, resumed])

  if (lost) {
    return (
      <p role="alert" className="text-sm text-destructive">
        {error}
      </p>
    )
  }
  if (!job) {
    return (
      <p className="text-sm text-muted-foreground">{error ?? "Starting…"}</p>
    )
  }
  const active = ACTIVE.includes(job.status)
  const pct = Math.round(Math.min(1, Math.max(0, job.progress)) * 100)
  return (
    <div className="space-y-2" aria-live="polite">
      {active ? (
        <>
          <p className="text-sm">
            {(job.stage ? stageName(job.stage) : null) ??
              (job.status === "queued" ? "Waiting to start" : "Working")}
            … {pct}%
          </p>
          <div
            role="progressbar"
            aria-valuenow={pct}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-2 w-full overflow-hidden rounded-full bg-muted"
          >
            <div
              className="h-full bg-primary transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
          {error && <p className="text-xs text-muted-foreground">{error}</p>}
        </>
      ) : (
        <>
          <p
            role={job.status === "succeeded" ? "status" : "alert"}
            className={
              job.status === "succeeded"
                ? "text-sm"
                : "text-sm text-destructive"
            }
          >
            {job.message ??
              (job.status === "succeeded"
                ? "Done."
                : job.status === "unavailable"
                  ? "Generating isn't available right now."
                  : "Something went wrong.")}
          </p>
          {job.status !== "succeeded" && onRetry && (
            <Button size="sm" variant="outline" onClick={onRetry}>
              Try again
            </Button>
          )}
        </>
      )}
    </div>
  )
}

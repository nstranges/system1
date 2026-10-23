import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { useApi } from "@/lib/api/client"
import type { components } from "@/lib/api/schema"

type Job = components["schemas"]["JobOut"]

const POLL_MS = 1500
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
    async function tick() {
      try {
        const { data } = await api.GET("/api/jobs/{job_id}", {
          params: { path: { job_id: jobId } },
        })
        if (!live) return
        if (!data) {
          setError("We couldn't check on the job.")
          if (first) gone.current?.()
          return
        }
        setError(null)
        setJob(data)
        if (!ACTIVE.includes(data.status)) {
          if (first) gone.current?.()
          else done.current()
          return
        }
      } catch {
        if (!live) return
        setError("We couldn't reach the server. Trying again…")
      }
      first = false
      timer = setTimeout(() => void tick(), POLL_MS)
    }
    void tick()
    return () => {
      live = false
      clearTimeout(timer)
    }
  }, [api, jobId, resumed])

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
            {job.stage ??
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

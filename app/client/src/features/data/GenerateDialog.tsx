import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { useApi } from "@/lib/api/client"
import { readProblem, type Policy } from "@/lib/api/types"
import type { components } from "@/lib/api/schema"
import { MIN_PER_BUCKET, totalOf, type Health } from "./HealthPanel"

type Estimate = components["schemas"]["Estimate"]
export const GENERATE_CAP = 300

export function GenerateDialog({
  open,
  projectId,
  policy,
  health,
  onClose,
  onStarted,
}: {
  open: boolean
  projectId: string
  policy: Policy
  health: Health | null
  onClose: () => void
  onStarted: (jobId: string) => void
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        {open && (
          <Body
            projectId={projectId}
            policy={policy}
            health={health}
            onClose={onClose}
            onStarted={onStarted}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function Body({
  projectId,
  policy,
  health,
  onClose,
  onStarted,
}: {
  projectId: string
  policy: Policy
  health: Health | null
  onClose: () => void
  onStarted: (jobId: string) => void
}) {
  const api = useApi()
  const [targets, setTargets] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      policy.options.map((o) => [
        o.key,
        String(Math.max(0, MIN_PER_BUCKET - totalOf(health, o.key))),
      ]),
    ),
  )
  const [estimate, setEstimate] = useState<Estimate | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const numbers = Object.fromEntries(
    Object.entries(targets).map(([k, v]) => [
      k,
      Math.max(0, Math.floor(Number(v) || 0)),
    ]),
  )
  const total = Object.values(numbers).reduce((a, b) => a + b, 0)
  const body = {
    targets: Object.fromEntries(
      Object.entries(numbers).filter(([, n]) => n > 0),
    ),
  }

  async function review() {
    setBusy(true)
    setError(null)
    try {
      const { data, error: err } = await api.POST(
        "/api/projects/{project_id}/generate/estimate",
        { params: { path: { project_id: projectId } }, body },
      )
      if (data) setEstimate(data)
      else setError(readProblem(err).message)
    } catch {
      setError("We couldn't reach the server.")
    } finally {
      setBusy(false)
    }
  }

  async function confirm() {
    setBusy(true)
    setError(null)
    try {
      const {
        data,
        error: err,
        response,
      } = await api.POST("/api/projects/{project_id}/generate", {
        params: { path: { project_id: projectId } },
        body,
      })
      if (data) {
        onStarted(data.job_id)
        return
      }
      const problem = readProblem(err)
      setError(
        response.status === 409 || problem.code === "generation_running"
          ? "A generation is already running. Wait for it to finish."
          : problem.message,
      )
    } catch {
      setError("We couldn't reach the server.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Generate practice examples</DialogTitle>
        <DialogDescription>
          The assistant writes made-up examples for each bucket. Choose how
          many.
        </DialogDescription>
      </DialogHeader>
      {estimate ? (
        <p className="text-sm">
          Generate {estimate.examples} practice examples (about{" "}
          {Math.max(1, Math.round(estimate.est_minutes))} minutes)? This uses
          the assistant.
        </p>
      ) : (
        <div className="space-y-2">
          {policy.options.map((o) => (
            <label key={o.key} className="flex items-center gap-3 text-sm">
              <span className="min-w-0 flex-1 truncate">
                {o.name}
                <span className="ml-2 text-xs text-muted-foreground">
                  {totalOf(health, o.key)} now
                </span>
              </span>
              <Input
                type="number"
                min={0}
                className="w-24"
                value={targets[o.key] ?? "0"}
                onChange={(e) =>
                  setTargets((t) => ({ ...t, [o.key]: e.target.value }))
                }
              />
            </label>
          ))}
          <p className="text-sm text-muted-foreground">
            {total} in total.
            {total > GENERATE_CAP &&
              ` That's over the limit of ${GENERATE_CAP} at a time. Lower some numbers.`}
          </p>
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <DialogFooter>
        {estimate ? (
          <>
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => {
                setEstimate(null)
                setError(null)
              }}
            >
              Back
            </Button>
            <Button disabled={busy} onClick={() => void confirm()}>
              {busy ? "Starting…" : "Confirm"}
            </Button>
          </>
        ) : (
          <>
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button
              disabled={busy || total === 0 || total > GENERATE_CAP}
              onClick={() => void review()}
            >
              {busy ? "Checking…" : "Review cost"}
            </Button>
          </>
        )}
      </DialogFooter>
    </>
  )
}

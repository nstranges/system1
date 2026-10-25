import { Loader2 } from "lucide-react"
import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useApi } from "@/lib/api/client"
import { readProblem, type PolicyOut, type Project } from "@/lib/api/types"
import type { components } from "@/lib/api/schema"
import { useHealth } from "@/features/data/HealthPanel"
import { recalledJob, rememberJob } from "@/features/data/JobProgress"
import { TrainProgress } from "./TrainProgress"
import { ReportCard } from "./ReportCard"

type Report = components["schemas"]["Report"]

export function TrainCanvas({
  project,
  policy,
}: {
  project: Project
  policy: PolicyOut
}) {
  const api = useApi()
  const { health, reload: reloadHealth } = useHealth(project.id)
  const [report, setReport] = useState<Report | null>(null)
  const [jobId, setJobId] = useState<string | null>(() =>
    recalledJob(project.id),
  )
  // True while a job is still going; a finished one stays on screen as its message.
  const [running, setRunning] = useState(jobId !== null)
  const [confirming, setConfirming] = useState(false)
  const [starting, setStarting] = useState(false)

  const loadReport = useCallback(async () => {
    try {
      const { data } = await api.GET("/api/projects/{project_id}/report", {
        params: { path: { project_id: project.id } },
      })
      if (data) setReport(data)
    } catch {
      toast.error("We couldn't load the report. Reload to try again.")
    }
  }, [api, project.id])

  useEffect(() => {
    void loadReport()
  }, [loadReport])

  const names = new Map(policy.policy.options.map((o) => [o.key, o.name]))
  const examples = health
    ? {
        train: Object.values(health.per_bucket).reduce(
          (n, c) => n + c.train + c.cal,
          0,
        ),
        test: Object.values(health.per_bucket).reduce((n, c) => n + c.test, 0),
      }
    : undefined
  const short = (health?.below_minimum ?? []).map((k) => names.get(k) ?? k)
  const blocked =
    short.length > 0
      ? `Add at least 30 examples to: ${short.join(", ")}.`
      : null

  async function start() {
    setStarting(true)
    try {
      const { data, error } = await api.POST(
        "/api/projects/{project_id}/training",
        { params: { path: { project_id: project.id } } },
      )
      if (data) {
        rememberJob(project.id, data.job_id)
        setRunning(true)
        setJobId(data.job_id)
        setConfirming(false)
      } else {
        toast.error(readProblem(error).message)
      }
    } catch {
      toast.error("We couldn't reach the server.")
    } finally {
      setStarting(false)
    }
  }

  function finished() {
    rememberJob(project.id, null)
    setRunning(false)
    void loadReport()
    void reloadHealth()
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Train my model</CardTitle>
          <CardDescription>
            We teach a small model from your examples, then check it on test
            examples it never saw, next to Jev.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {jobId && (
            <TrainProgress
              jobId={jobId}
              examples={examples}
              onDone={finished}
            />
          )}
          {running ? null : confirming ? (
            <div className="space-y-3 rounded-lg border p-3">
              <p className="text-sm">
                This starts a training run. It can take several minutes, and
                your test examples are set aside for good the first time.
              </p>
              <div className="flex gap-2">
                <Button disabled={starting} onClick={() => void start()}>
                  {starting && <Loader2 className="animate-spin" />}
                  {starting ? "Starting…" : "Start training"}
                </Button>
                <Button
                  variant="outline"
                  disabled={starting}
                  onClick={() => setConfirming(false)}
                >
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <>
              <Button
                disabled={blocked !== null}
                onClick={() => setConfirming(true)}
              >
                {report?.available ? "Train again" : "Train my model"}
              </Button>
              {blocked && (
                <p className="text-sm text-muted-foreground">{blocked}</p>
              )}
            </>
          )}
        </CardContent>
      </Card>
      {report?.available && (
        <div className={running ? "opacity-60" : ""}>
          {running && (
            <p className="mb-2 text-sm text-muted-foreground">
              This is your last report. It updates when the run finishes.
            </p>
          )}
          <ReportCard report={report} />
        </div>
      )}
    </div>
  )
}

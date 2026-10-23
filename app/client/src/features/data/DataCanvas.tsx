import { Layers, Sparkles, Upload } from "lucide-react"
import { useEffect, useState } from "react"
import { useLocation, useNavigate } from "react-router"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useApi } from "@/lib/api/client"
import type { PolicyOut, Project } from "@/lib/api/types"
import { GenerateDialog } from "./GenerateDialog"
import { HealthPanel, useHealth, type Health } from "./HealthPanel"
import { JobProgress, recalledJob, rememberJob } from "./JobProgress"
import { UploadWizard, describeImport } from "./UploadWizard"

export const FLAGSHIP_TEMPLATE = "tallyfern-triage"

export function DataCanvas({
  project,
  policy,
  onPolicy,
}: {
  project: Project
  policy: PolicyOut
  onPolicy: (p: PolicyOut) => void
}) {
  const api = useApi()
  const location = useLocation()
  const navigate = useNavigate()
  const { health, failed, reload } = useHealth(project.id)
  const [uploading, setUploading] = useState(false)
  const [generating, setGenerating] = useState(false)
  // "Both": generate straight after the upload finishes.
  const [thenGenerate, setThenGenerate] = useState(false)
  const [gapHealth, setGapHealth] = useState<Health | null>(null)
  const [jobId, setJobId] = useState<string | null>(() =>
    recalledJob(project.id),
  )
  const [resumed, setResumed] = useState(jobId !== null)
  // True while a job is still going; a finished one stays on screen only as a message.
  const [running, setRunning] = useState(jobId !== null)
  const flagship = project.template_id === FLAGSHIP_TEMPLATE

  // The dashboard asks for the upload through router state; clear only that
  // key so other state (the assistant's first message) survives.
  const wantsUpload = (location.state as { openUpload?: boolean } | null)
    ?.openUpload
  useEffect(() => {
    if (!wantsUpload || flagship) return
    setUploading(true)
    const { openUpload: _drop, ...rest } = (location.state ?? {}) as Record<
      string,
      unknown
    >
    void _drop
    navigate(location.pathname, {
      replace: true,
      state: Object.keys(rest).length > 0 ? rest : null,
    })
  }, [wantsUpload, flagship, location.state, location.pathname, navigate])

  if (flagship) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Built with exact rules</CardTitle>
          <CardDescription>
            This example was built with our rules-based pipeline: across{" "}
            {policy.policy.options.length} buckets, labelled by exact rules.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <HealthPanel policy={policy.policy} health={health} failed={failed} />
        </CardContent>
      </Card>
    )
  }

  // The import may have added buckets as a new policy version.
  async function refreshAfterImport() {
    try {
      const { data } = await api.GET("/api/projects/{project_id}/policy", {
        params: { path: { project_id: project.id } },
      })
      if (data) onPolicy(data)
      else toast.error("Imported, but we couldn't refresh the buckets. Reload.")
    } catch {
      toast.error("Imported, but we couldn't refresh the buckets. Reload.")
    }
    setGapHealth(await reload())
  }

  function startJob(id: string) {
    rememberJob(project.id, id)
    setResumed(false)
    setRunning(true)
    setJobId(id)
    setGenerating(false)
  }

  function endJob() {
    rememberJob(project.id, null)
    setRunning(false)
    setJobId(null)
  }

  const cards = [
    {
      title: "Upload examples",
      text: "Bring past decisions from a spreadsheet.",
      icon: Upload,
      go: () => {
        setThenGenerate(false)
        setUploading(true)
      },
    },
    {
      title: "Generate examples",
      text: "Have the assistant write practice ones.",
      icon: Sparkles,
      go: () => {
        setGapHealth(health)
        setGenerating(true)
      },
    },
    {
      title: "Both",
      text: "Upload yours, then fill the gaps with practice ones.",
      icon: Layers,
      go: () => {
        setThenGenerate(true)
        setUploading(true)
      },
    },
  ]

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-3">
        {cards.map((c) => (
          <Card key={c.title} size="sm">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <c.icon className="size-4" /> {c.title}
              </CardTitle>
              <CardDescription>{c.text}</CardDescription>
            </CardHeader>
            <CardContent>
              <Button
                variant="outline"
                size="sm"
                disabled={running && c.title !== "Upload examples"}
                onClick={c.go}
              >
                {c.title}
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>

      {jobId && (
        <Card size="sm">
          <CardHeader>
            <CardTitle>Generating examples</CardTitle>
            {!running && (
              <CardAction>
                <Button size="sm" variant="ghost" onClick={endJob}>
                  Dismiss
                </Button>
              </CardAction>
            )}
          </CardHeader>
          <CardContent>
            <JobProgress
              key={jobId}
              jobId={jobId}
              resumed={resumed}
              onGone={endJob}
              onDone={() => {
                rememberJob(project.id, null)
                setRunning(false)
                void reload()
              }}
              onRetry={() => {
                endJob()
                setGapHealth(health)
                setGenerating(true)
              }}
            />
          </CardContent>
        </Card>
      )}

      <HealthPanel policy={policy.policy} health={health} failed={failed} />

      <UploadWizard
        open={uploading}
        projectId={project.id}
        policy={policy.policy}
        onClose={() => setUploading(false)}
        onImported={refreshAfterImport}
        onDone={(result) => {
          setUploading(false)
          toast.success(describeImport(result))
          if (thenGenerate) {
            setThenGenerate(false)
            setGenerating(true)
          }
        }}
      />
      <GenerateDialog
        open={generating}
        projectId={project.id}
        policy={policy.policy}
        health={gapHealth ?? health}
        onClose={() => setGenerating(false)}
        onStarted={startJob}
      />
    </div>
  )
}

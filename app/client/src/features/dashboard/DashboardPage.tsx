import { useCallback, useEffect, useState } from "react"
import { Link, useNavigate } from "react-router"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/lib/api/client"
import { readProblem, type Project, type Template } from "@/lib/api/types"
import { normalizeStage } from "@/features/workspace/stages"
import { NewProjectDialog, type StartMode } from "./NewProjectDialog"

export function DashboardPage() {
  const api = useApi()
  const navigate = useNavigate()
  const [projects, setProjects] = useState<Project[] | null>(null)
  const [templates, setTemplates] = useState<Template[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)

  const [loadError, setLoadError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoadError(null)
    try {
      const [p, t] = await Promise.all([
        api.GET("/api/projects"),
        api.GET("/api/templates"),
      ])
      if (p.data && t.data) {
        setProjects(p.data)
        setTemplates(t.data)
      } else {
        setLoadError(readProblem(p.error ?? t.error).message)
      }
    } catch {
      setLoadError("We couldn't reach the server.")
    }
  }, [api])

  useEffect(() => {
    void load()
  }, [load])

  async function create(
    name: string,
    templateId: string | null,
    description: string | null,
    next: { stage: string; state: Record<string, unknown> | null },
  ) {
    setBusy(true)
    const { data, error } = await api.POST("/api/projects", {
      body: { name, template_id: templateId, description },
    })
    setBusy(false)
    if (!data) {
      toast.error(readProblem(error).message)
      return
    }
    navigate(`/app/p/${data.id}/${next.stage}`, { state: next.state })
  }

  function start(mode: StartMode, name: string, deciding: string) {
    if (mode === "upload")
      void create(name, null, deciding || null, {
        stage: "data",
        state: { openUpload: true },
      })
    else if (mode === "documents")
      void create(name, null, deciding || null, {
        stage: "define",
        state: { openContext: true },
      })
    else
      void create(name, null, deciding || null, {
        stage: "define",
        state: {
          firstMessage: deciding || "Help me find a decision worth automating",
        },
      })
  }

  if (loadError) {
    return (
      <Card className="mx-auto max-w-md">
        <CardHeader>
          <CardTitle>We couldn't load your projects</CardTitle>
          <CardDescription>{loadError}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={() => void load()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Your projects</h1>
        <Button onClick={() => setDialogOpen(true)}>New project</Button>
      </div>
      {projects === null ? (
        <Skeleton className="h-24 w-full" />
      ) : projects.length === 0 ? (
        <Card className="mx-auto max-w-md text-center">
          <CardHeader>
            <CardTitle>Start your first project</CardTitle>
            <CardDescription>
              Pick a decision your team makes again and again, and teach a model
              to make it.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => setDialogOpen(true)}>New project</Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <Link
              key={p.id}
              to={`/app/p/${p.id}/${normalizeStage(p.stage) ?? "define"}`}
            >
              <Card className="h-full transition-colors hover:bg-muted/50">
                <CardHeader>
                  <CardTitle>{p.name}</CardTitle>
                  <CardDescription>
                    {p.description ?? "Open to keep working"}
                  </CardDescription>
                  <p className="text-xs text-muted-foreground">
                    Created {new Date(p.created_at).toLocaleDateString()}
                  </p>
                </CardHeader>
              </Card>
            </Link>
          ))}
        </div>
      )}

      <NewProjectDialog
        key={dialogOpen ? "open" : "closed"}
        open={dialogOpen}
        templates={templates}
        busy={busy}
        onClose={() => setDialogOpen(false)}
        onStart={start}
        onTemplate={(t, name) =>
          void create(name || t.name, t.id, null, {
            stage: "define",
            state: null,
          })
        }
      />
    </div>
  )
}

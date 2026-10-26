import { useCallback, useEffect, useState } from "react"
import { Pencil, Trash2 } from "lucide-react"
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
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/lib/api/client"
import {
  readProblem,
  type Project,
  type Template,
  type TrainedModel,
} from "@/lib/api/types"
import { ModelList } from "@/features/models/ModelList"
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
  const [models, setModels] = useState<TrainedModel[] | null>(null)

  // Loaded on its own, so the projects still show if this one fails.
  const loadModels = useCallback(async () => {
    try {
      const { data } = await api.GET("/api/models")
      setModels(data ?? [])
    } catch {
      setModels([])
    }
  }, [api])

  useEffect(() => {
    void loadModels()
  }, [loadModels])

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
            <ProjectCard
              key={p.id}
              project={p}
              onChanged={(next) =>
                setProjects((all) =>
                  (all ?? []).flatMap((x) =>
                    x.id !== p.id ? [x] : next ? [next] : [],
                  ),
                )
              }
            />
          ))}
        </div>
      )}

      {models && models.length > 0 && (
        <section className="space-y-3">
          <div>
            <h2 className="text-xl font-semibold tracking-tight">
              Your models
            </h2>
            <p className="text-sm text-muted-foreground">
              Every model your team has trained. The live one answers its
              project's endpoint.
            </p>
          </div>
          <Card>
            <CardContent>
              <ModelList
                models={models}
                showProject
                onLive={() => void loadModels()}
              />
            </CardContent>
          </Card>
        </section>
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

// A project card: click to open, with rename and delete beside it. Delete asks first, and only an admin can do it.
function ProjectCard({
  project,
  onChanged,
}: {
  project: Project
  // The renamed project, or null once it is deleted.
  onChanged: (next: Project | null) => void
}) {
  const api = useApi()
  const [renaming, setRenaming] = useState(false)
  const [name, setName] = useState(project.name)
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)

  async function rename() {
    const next = name.trim()
    if (!next || next === project.name) {
      setRenaming(false)
      setName(project.name)
      return
    }
    setBusy(true)
    try {
      const { data, error } = await api.PATCH("/api/projects/{project_id}", {
        params: { path: { project_id: project.id } },
        body: { name: next },
      })
      if (data) {
        onChanged(data)
        setRenaming(false)
      } else {
        toast.error(readProblem(error).message)
      }
    } catch {
      toast.error("We couldn't reach the server.")
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    setBusy(true)
    try {
      const { response, error } = await api.DELETE(
        "/api/projects/{project_id}",
        { params: { path: { project_id: project.id } } },
      )
      if (response.ok) {
        onChanged(null)
        toast("Project deleted")
      } else {
        toast.error(readProblem(error).message)
        setConfirming(false)
      }
    } catch {
      toast.error("We couldn't reach the server.")
    } finally {
      setBusy(false)
    }
  }

  const stage = normalizeStage(project.stage) ?? "define"
  // The title link is stretched over the whole card, so clicking anywhere opens the project; the action buttons sit
  // above it so they still get their own clicks.
  return (
    <Card className="relative h-full transition-colors hover:bg-muted/50">
      <CardHeader>
        {renaming ? (
          <Input
            autoFocus
            aria-label="Project name"
            value={name}
            maxLength={120}
            disabled={busy}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void rename()
              if (e.key === "Escape") {
                setRenaming(false)
                setName(project.name)
              }
            }}
            onBlur={() => !busy && void rename()}
          />
        ) : (
          <CardTitle>
            <Link
              to={`/app/p/${project.id}/${stage}`}
              className="after:absolute after:inset-0 after:content-['']"
            >
              {project.name}
            </Link>
          </CardTitle>
        )}
        <CardDescription>
          {project.description ?? "Open to keep working"}
        </CardDescription>
        <p className="text-xs text-muted-foreground">
          Created {new Date(project.created_at).toLocaleDateString()}
        </p>
        {confirming ? (
          <div className="relative z-10 flex items-center gap-2 text-sm">
            <span>Delete this project and its examples?</span>
            <Button
              size="sm"
              variant="destructive"
              disabled={busy}
              onClick={() => void remove()}
            >
              Delete
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => setConfirming(false)}
            >
              Keep
            </Button>
          </div>
        ) : (
          <div className="relative z-10 flex gap-1">
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setName(project.name)
                setRenaming(true)
              }}
            >
              <Pencil /> Rename
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setConfirming(true)}
            >
              <Trash2 /> Delete
            </Button>
          </div>
        )}
      </CardHeader>
    </Card>
  )
}

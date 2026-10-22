import { useCallback, useEffect, useState } from "react"
import { Link, useNavigate } from "react-router"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useApi } from "@/lib/api/client"
import { readProblem, type Project, type Template } from "@/lib/api/types"
import { isStage } from "@/features/workspace/stages"
import { NewProjectDialog } from "./NewProjectDialog"
import { TemplateCard } from "./TemplateCard"

export function DashboardPage() {
  const api = useApi()
  const navigate = useNavigate()
  const [projects, setProjects] = useState<Project[] | null>(null)
  const [templates, setTemplates] = useState<Template[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [dialog, setDialog] = useState<"describe" | "find" | null>(null)

  const load = useCallback(async () => {
    const [p, t] = await Promise.all([
      api.GET("/api/projects"),
      api.GET("/api/templates"),
    ])
    if (p.data) setProjects(p.data)
    else toast.error(readProblem(p.error).message)
    if (t.data) setTemplates(t.data)
    else toast.error(readProblem(t.error).message)
  }, [api])

  useEffect(() => {
    void load()
  }, [load])

  async function create(name: string, templateId: string | null) {
    setBusy(true)
    const { data, error } = await api.POST("/api/projects", {
      body: { name, template_id: templateId },
    })
    setBusy(false)
    if (!data) {
      toast.error(readProblem(error).message)
      return
    }
    // A template arrives with rules to look at; a blank project starts at the use case.
    navigate(`/app/p/${data.id}/${templateId ? "rules" : "usecase"}`)
  }

  return (
    <div className="space-y-10">
      <section className="space-y-4">
        <h1 className="text-2xl font-semibold tracking-tight">Your projects</h1>
        {projects === null ? (
          <Skeleton className="h-24 w-full" />
        ) : projects.length === 0 ? (
          <p className="text-muted-foreground">
            No projects yet. Pick a starting point below.
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((p) => (
              <Link
                key={p.id}
                to={`/app/p/${p.id}/${isStage(p.stage) ? p.stage : "usecase"}`}
              >
                <Card className="h-full transition-colors hover:bg-muted/50">
                  <CardHeader>
                    <CardTitle>{p.name}</CardTitle>
                    <CardDescription>
                      {p.description ?? "Open to keep working"}
                    </CardDescription>
                  </CardHeader>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">
            Start a new decision
          </h2>
          <p className="text-sm text-muted-foreground">
            Pick a decision your team makes again and again, or describe your
            own.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button onClick={() => setDialog("describe")}>
            Describe your own
          </Button>
          <Button variant="outline" onClick={() => setDialog("find")}>
            Help me find one
          </Button>
        </div>
        {templates === null ? (
          <Skeleton className="h-48 w-full" />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {templates.map((t) => (
              <TemplateCard
                key={t.id}
                template={t}
                busy={busy}
                onUse={() => void create(t.name, t.id)}
              />
            ))}
          </div>
        )}
      </section>

      <NewProjectDialog
        key={dialog ?? "closed"}
        mode={dialog}
        busy={busy}
        onClose={() => setDialog(null)}
        onCreate={(name) => void create(name, null)}
      />
    </div>
  )
}

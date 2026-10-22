import { useCallback, useEffect, useState } from "react"
import {
  Link,
  Navigate,
  useLocation,
  useNavigate,
  useParams,
} from "react-router"
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
import {
  readProblem,
  type PolicyInput,
  type PolicyOut,
  type Project,
} from "@/lib/api/types"
import { AgentPanel } from "@/features/agent/AgentPanel"
import type { CanvasEvent } from "@/features/agent/useAgent"
import { ImproveCanvas } from "@/features/improve/ImproveCanvas"
import { RulesCanvas } from "@/features/rules/RulesCanvas"
import { TryCanvas } from "@/features/playground/TryCanvas"
import { UseCanvas } from "@/features/use/UseCanvas"
import { UseCaseCanvas } from "@/features/usecase/UseCaseCanvas"
import { StageRail } from "./StageRail"
import { STAGES, isStage, type StageId } from "./stages"

function ComingSoon({ stage }: { stage: StageId }) {
  const label = STAGES.find((s) => s.id === stage)?.label
  return (
    <Card>
      <CardHeader>
        <CardTitle>{label}</CardTitle>
        <CardDescription>This step isn't ready yet.</CardDescription>
      </CardHeader>
    </Card>
  )
}

// Keyed on the project so nothing from the previous one leaks across.
export function WorkspacePage() {
  const { projectId } = useParams()
  return <Workspace key={projectId} />
}

function Workspace() {
  const { projectId, stage } = useParams()
  const api = useApi()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [policy, setPolicy] = useState<PolicyOut | null>(null)
  const [rulesDraft, setRulesDraft] = useState<PolicyInput | null>(null)
  const [missing, setMissing] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const location = useLocation()
  // A new blank project opens on the assistant, which is about to speak.
  const [panel, setPanel] = useState<"assistant" | "canvas">(
    (location.state as { firstMessage?: string } | null)?.firstMessage
      ? "assistant"
      : "canvas",
  )

  const load = useCallback(async () => {
    if (!projectId) return
    setLoadError(null)
    try {
      const [p, pol] = await Promise.all([
        api.GET("/api/projects/{project_id}", {
          params: { path: { project_id: projectId } },
        }),
        api.GET("/api/projects/{project_id}/policy", {
          params: { path: { project_id: projectId } },
        }),
      ])
      if (p.response.status === 404) {
        setMissing(true)
        return
      }
      if (p.data && pol.data) {
        setProject(p.data)
        setPolicy(pol.data)
      } else {
        setLoadError(readProblem(p.error ?? pol.error).message)
      }
    } catch {
      setLoadError("We couldn't reach the server.")
    }
  }, [api, projectId])

  // A saved policy becomes the new base: unsaved rules edits stay, but the
  // saved decision question wins so a later rules save can't revert it.
  const rebase = useCallback((saved: PolicyOut) => {
    setPolicy(saved)
    setRulesDraft((d) =>
      d
        ? {
            ...d,
            decision_question: saved.policy.decision_question,
            question_key: saved.policy.question_key,
          }
        : d,
    )
  }, [])

  // The assistant's rules replace the saved policy and discard any unsaved
  // rules draft: merging a half-edited draft into agent changes would be
  // guesswork. The saved draft was never written, so the PUT path (which
  // strips the client-only `_new` marker) is unaffected. The event carries no
  // validation issues, so they are refetched.
  const onCanvas = useCallback(
    (e: CanvasEvent) => {
      setPolicy({ policy: e.policy, version: e.version, issues: [] })
      setRulesDraft(null)
      toast("Your assistant updated the rules")
      if (!projectId) return
      void api
        .GET("/api/projects/{project_id}/policy", {
          params: { path: { project_id: projectId } },
        })
        .then(({ data }) => {
          if (data && data.version >= e.version) setPolicy(data)
        })
    },
    [api, projectId],
  )

  const onStage = useCallback(
    (next: string) => {
      if (isStage(next)) navigate(`/app/p/${projectId}/${next}`)
    },
    [navigate, projectId],
  )

  useEffect(() => {
    void load()
  }, [load])

  // Unsaved rule edits survive switching stages; leaving the page asks first.
  useEffect(() => {
    if (!rulesDraft) return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener("beforeunload", warn)
    return () => window.removeEventListener("beforeunload", warn)
  }, [rulesDraft])

  if (!isStage(stage)) {
    return <Navigate to={`/app/p/${projectId}/usecase`} replace />
  }
  if (missing) {
    return (
      <Card className="mx-auto max-w-md">
        <CardHeader>
          <CardTitle>We couldn't find that project</CardTitle>
          <CardDescription>
            It may belong to another team, or it was deleted.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button nativeButton={false} render={<Link to="/app" />}>
            Back to projects
          </Button>
        </CardContent>
      </Card>
    )
  }
  if (loadError) {
    return (
      <Card className="mx-auto max-w-md">
        <CardHeader>
          <CardTitle>We couldn't open this project</CardTitle>
          <CardDescription>{loadError}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button onClick={() => void load()}>Retry</Button>
        </CardContent>
      </Card>
    )
  }
  if (!project || !policy) {
    return <Skeleton className="h-96 w-full" />
  }

  const canvas =
    stage === "usecase" ? (
      <UseCaseCanvas
        project={project}
        policy={policy}
        onProject={setProject}
        onPolicy={rebase}
      />
    ) : stage === "rules" ? (
      <RulesCanvas
        project={project}
        policy={policy}
        draft={rulesDraft}
        onDraft={setRulesDraft}
        onPolicy={rebase}
      />
    ) : stage === "try" ? (
      <TryCanvas project={project} policy={policy} />
    ) : stage === "use" ? (
      <UseCanvas project={project} onProject={setProject} />
    ) : stage === "improve" ? (
      <ImproveCanvas project={project} policy={policy} />
    ) : (
      <ComingSoon stage={stage} />
    )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Link
          to="/app"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          All projects
        </Link>
        <span className="text-muted-foreground">/</span>
        <h1 className="truncate text-lg font-semibold">{project.name}</h1>
      </div>
      <StageRail projectId={project.id} current={stage} />

      <div className="flex gap-1 rounded-lg bg-muted p-1 lg:hidden">
        {(["assistant", "canvas"] as const).map((p) => (
          <Button
            key={p}
            size="sm"
            variant={panel === p ? "default" : "ghost"}
            className="flex-1"
            onClick={() => setPanel(p)}
          >
            {p === "assistant" ? "Assistant" : "Workspace"}
          </Button>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <div className={panel === "assistant" ? "" : "hidden lg:block"}>
          <AgentPanel project={project} onCanvas={onCanvas} onStage={onStage} />
        </div>
        <div
          className={panel === "canvas" ? "min-w-0" : "hidden min-w-0 lg:block"}
        >
          {canvas}
        </div>
      </div>
    </div>
  )
}

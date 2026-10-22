import { useEffect, useState } from "react"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { IssueList } from "@/features/rules/RulesCanvas"
import { useApi } from "@/lib/api/client"
import {
  readProblem,
  type PolicyIssue,
  type PolicyOut,
  type Project,
  type Template,
} from "@/lib/api/types"

const FIT: Record<string, string> = {
  good: "Good fit",
  workable: "Workable",
  poor: "Poor fit",
}

export function UseCaseCanvas({
  project,
  policy,
  onProject,
  onPolicy,
}: {
  project: Project
  policy: PolicyOut
  onProject: (p: Project) => void
  onPolicy: (p: PolicyOut) => void
}) {
  const api = useApi()
  const [name, setName] = useState(project.name)
  const [question, setQuestion] = useState(policy.policy.decision_question)
  const [template, setTemplate] = useState<Template | null>(null)
  const [issues, setIssues] = useState<PolicyIssue[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!project.template_id) return
    void api.GET("/api/templates").then(({ data }) => {
      setTemplate(data?.find((t) => t.id === project.template_id) ?? null)
    })
  }, [api, project.template_id])

  const dirty =
    name.trim() !== project.name ||
    question.trim() !== policy.policy.decision_question

  async function save() {
    setSaving(true)
    setIssues([])
    if (name.trim() !== project.name) {
      const { data, error } = await api.PATCH("/api/projects/{project_id}", {
        params: { path: { project_id: project.id } },
        body: { name: name.trim() },
      })
      if (!data) {
        setSaving(false)
        toast.error(readProblem(error).message)
        return
      }
      onProject(data)
    }
    if (question.trim() !== policy.policy.decision_question) {
      const { data, error } = await api.PUT(
        "/api/projects/{project_id}/policy",
        {
          params: { path: { project_id: project.id } },
          body: {
            policy: { ...policy.policy, decision_question: question.trim() },
          },
        },
      )
      if (!data) {
        const problem = readProblem(error)
        setIssues(problem.issues)
        setSaving(false)
        toast.error(problem.message)
        return
      }
      onPolicy(data)
    }
    setSaving(false)
    toast.success("Saved")
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h2 className="text-xl font-semibold tracking-tight">Use case</h2>
      <label className="block">
        <span className="mb-1 block text-sm font-medium">Project name</span>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={120}
        />
      </label>
      <label className="block">
        <span className="mb-1 block text-sm font-medium">
          The decision your team makes
        </span>
        <Input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="For example: Which queue should handle this ticket?"
        />
      </label>
      <IssueList issues={issues} />
      <Button
        disabled={!dirty || saving || !name.trim() || !question.trim()}
        onClick={() => void save()}
      >
        Save
      </Button>

      {template && (
        <div className="space-y-2 rounded-lg border p-4">
          <div className="flex items-center gap-2">
            <h3 className="font-medium">Started from: {template.name}</h3>
            <Badge variant={template.fit === "good" ? "default" : "secondary"}>
              {FIT[template.fit] ?? template.fit}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">{template.summary}</p>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {template.fit_reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

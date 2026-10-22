import { useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { useApi } from "@/lib/api/client"
import {
  readProblem,
  type PolicyInput,
  type PolicyIssue,
  type PolicyOut,
  type Project,
} from "@/lib/api/types"
import { InputsPanel } from "./InputsPanel"
import { OptionsPanel } from "./OptionsPanel"
import { RulesPanel } from "./RulesPanel"

// Blank lines in "covers" textareas are for typing; drop them before saving.
function tidy(policy: PolicyInput): PolicyInput {
  const clean = (xs?: string[]) =>
    (xs ?? []).map((x) => x.trim()).filter(Boolean)
  return {
    ...policy,
    options: policy.options.map((o) => ({
      ...o,
      covers: clean(o.covers),
      excludes: clean(o.excludes),
    })),
  }
}

export function IssueList({ issues }: { issues: PolicyIssue[] }) {
  if (issues.length === 0) return null
  return (
    <div
      role="alert"
      className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm"
    >
      <p className="font-medium text-destructive">
        Fix these before you save or try it out
      </p>
      <ul className="mt-1 list-disc space-y-0.5 pl-5">
        {issues.map((i, n) => (
          <li key={n}>
            {i.path ? (
              <span className="font-mono text-xs">{i.path}: </span>
            ) : null}
            {i.message}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function RulesCanvas({
  project,
  policy,
  draft: unsaved,
  onDraft,
  onPolicy,
}: {
  project: Project
  policy: PolicyOut
  // Unsaved edits live in the workspace so they survive switching stages.
  draft: PolicyInput | null
  onDraft: (d: PolicyInput | null) => void
  onPolicy: (p: PolicyOut) => void
}) {
  const api = useApi()
  const draft: PolicyInput = unsaved ?? policy.policy
  const dirty = unsaved !== null
  const savedKeys = new Set([
    ...policy.policy.options.map((o) => o.key),
    ...(policy.policy.inputs ?? []).map((f) => f.key),
  ])
  const [saving, setSaving] = useState(false)
  const [issues, setIssues] = useState<PolicyIssue[]>(policy.issues)

  const change = (next: PolicyInput) => onDraft(next)

  async function save() {
    setSaving(true)
    const { data, error } = await api.PUT("/api/projects/{project_id}/policy", {
      params: { path: { project_id: project.id } },
      body: { policy: tidy(draft) },
    })
    setSaving(false)
    if (data) {
      onDraft(null)
      setIssues([])
      onPolicy(data)
      toast.success("Rules saved")
      return
    }
    // The draft stays as typed so nothing is lost while fixing the problems.
    const problem = readProblem(error)
    setIssues(problem.issues)
    toast.error(problem.message)
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Rules</h2>
          <p className="text-sm text-muted-foreground">
            {draft.decision_question}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            disabled={!dirty || saving}
            onClick={() => {
              onDraft(null)
              setIssues(policy.issues)
            }}
          >
            Discard changes
          </Button>
          <Button disabled={!dirty || saving} onClick={() => void save()}>
            Save rules
          </Button>
        </div>
      </div>
      <IssueList issues={issues} />
      <InputsPanel policy={draft} savedKeys={savedKeys} onChange={change} />
      <OptionsPanel policy={draft} savedKeys={savedKeys} onChange={change} />
      <RulesPanel policy={draft} onChange={change} />
    </div>
  )
}

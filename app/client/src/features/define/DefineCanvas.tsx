import { ChevronDown, Sparkles } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useLocation, useNavigate } from "react-router"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { describeIssue } from "@/features/rules/issueText"
import { IssueList } from "@/features/rules/IssueList"
import { InputsPanel } from "@/features/rules/InputsPanel"
import { RulesPanel } from "@/features/rules/RulesPanel"
import { markNew } from "@/features/rules/newRow"
import { tidy } from "@/features/rules/tidy"
import { useApi } from "@/lib/api/client"
import {
  readProblem,
  type PolicyInput,
  type PolicyIssue,
  type PolicyOut,
  type Project,
} from "@/lib/api/types"
import { BucketsPanel } from "./BucketsPanel"
import {
  ContextPanel,
  OPEN_CONTEXT_EVENT,
  useContextDocs,
} from "./ContextPanel"
import { DraftDialog, type DraftSource } from "./DraftDialog"
import { GuidelinesPanel } from "./GuidelinesPanel"
import { QuickCheck } from "./QuickCheck"
import { SamplesPanel } from "./SamplesPanel"

const isAdvancedTarget = (t?: string) =>
  !!t && (t.startsWith("rule-") || t.startsWith("input-"))

export function DefineCanvas({
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
  const location = useLocation()
  const navigate = useNavigate()
  const draft: PolicyInput = unsaved ?? policy.policy
  const dirty = unsaved !== null
  const [saving, setSaving] = useState(false)
  // Issues come from the policy; a failed save overrides them only until the
  // policy object changes (a save, an agent edit, a refetch).
  const [override, setOverride] = useState<{
    base: PolicyOut
    issues: PolicyIssue[]
  } | null>(null)
  const issues = override?.base === policy ? override.issues : policy.issues
  const context = useContextDocs(project.id)
  const [contextOpen, setContextOpen] = useState(false)
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [drafting, setDrafting] = useState<DraftSource | null>(null)
  // null until the count has loaded (or failed): the menu doesn't claim "no
  // examples" for something it hasn't checked.
  const [exampleCount, setExampleCount] = useState<number | null>(null)
  const [countLoading, setCountLoading] = useState(false)
  const contextRef = useRef<HTMLDivElement>(null)

  const change = (next: PolicyInput) => onDraft(next)

  // The dashboard asks for the context dialog through router state; clear only
  // that key so the assistant's first message (also in state) survives.
  const wantsContext = (location.state as { openContext?: boolean } | null)
    ?.openContext
  useEffect(() => {
    if (!wantsContext) return
    setContextOpen(true)
    contextRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
    const { openContext: _drop, ...rest } = (location.state ?? {}) as Record<
      string,
      unknown
    >
    void _drop
    navigate(location.pathname, {
      replace: true,
      state: Object.keys(rest).length > 0 ? rest : null,
    })
  }, [wantsContext, location.state, location.pathname, navigate])

  useEffect(() => {
    const open = () => {
      setContextOpen(true)
      contextRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
    }
    window.addEventListener(OPEN_CONTEXT_EVENT, open)
    return () => window.removeEventListener(OPEN_CONTEXT_EVENT, open)
  }, [])

  async function loadExampleCount() {
    setCountLoading(true)
    setExampleCount(null)
    const { data } = await api.GET(
      "/api/projects/{project_id}/examples/health",
      { params: { path: { project_id: project.id } } },
    )
    if (data) {
      setExampleCount(
        Object.values(data.per_bucket)
          .flatMap((splits) => Object.values(splits))
          .reduce((a, b) => a + b, 0),
      )
    }
    setCountLoading(false)
  }

  async function save() {
    setSaving(true)
    const { data, error } = await api.PUT("/api/projects/{project_id}/policy", {
      params: { path: { project_id: project.id } },
      body: { policy: tidy(draft) },
    })
    setSaving(false)
    if (data) {
      onDraft(null)
      setOverride(null)
      onPolicy(data)
      toast.success("Saved")
      return
    }
    // The draft stays as typed so nothing is lost while fixing the problems.
    const problem = readProblem(error)
    setOverride({ base: policy, issues: problem.issues })
    if (
      problem.issues.some((i) =>
        isAdvancedTarget(describeIssue(i, draft).target),
      )
    )
      setAdvancedOpen(true)
    toast.error(problem.message)
  }

  // The delete route already changed the saved policy; refresh it and take the
  // bucket out of any unsaved draft so a later Save doesn't bring it back.
  async function bucketDeleted(key: string) {
    const { data } = await api.GET("/api/projects/{project_id}/policy", {
      params: { path: { project_id: project.id } },
    })
    if (!data) {
      toast.error(
        "The bucket was deleted, but we couldn't refresh this page. Reload to see the latest.",
      )
      return
    }
    onPolicy(data)
    if (unsaved) {
      onDraft({
        ...unsaved,
        options: unsaved.options.filter((o) => o.key !== key),
      })
    }
    toast.success("Bucket deleted")
  }

  const noDocs = (context.docs?.length ?? 0) === 0

  return (
    <div className="space-y-8">
      <div className="flex justify-end">
        <div className="flex gap-2">
          <Button
            variant="ghost"
            disabled={!dirty || saving}
            onClick={() => {
              onDraft(null)
              setOverride(null)
            }}
          >
            Discard changes
          </Button>
          <Button disabled={!dirty || saving} onClick={() => void save()}>
            Save
          </Button>
        </div>
      </div>
      <IssueList
        issues={issues}
        policy={draft}
        onJump={(t) => isAdvancedTarget(t) && setAdvancedOpen(true)}
      />

      <label className="block">
        <span className="mb-1 block text-sm font-medium">
          What are you deciding?
        </span>
        <Input
          value={draft.decision_question}
          onChange={(e) =>
            change({ ...draft, decision_question: e.target.value })
          }
          placeholder="For example: Which queue should handle this ticket?"
        />
      </label>

      <div className="space-y-6">
        <div className="flex justify-end">
          <DropdownMenu
            onOpenChange={(open) => {
              if (open) void loadExampleCount()
            }}
          >
            <DropdownMenuTrigger render={<Button variant="outline" />}>
              <Sparkles /> Draft my buckets <ChevronDown />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                disabled={exampleCount === 0 && !countLoading}
                onClick={() => setDrafting("examples")}
              >
                From my examples
                {countLoading && (
                  <span className="ml-2 text-xs text-muted-foreground">
                    Checking…
                  </span>
                )}
                {exampleCount === 0 && !countLoading && (
                  <span className="ml-2 text-xs text-muted-foreground">
                    Add examples first
                  </span>
                )}
              </DropdownMenuItem>
              <DropdownMenuItem
                disabled={noDocs}
                onClick={() => setDrafting("context")}
              >
                From my documents
                {noDocs && (
                  <span className="ml-2 text-xs text-muted-foreground">
                    Add a context file first
                  </span>
                )}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        <BucketsPanel
          projectId={project.id}
          policy={draft}
          onChange={change}
          onDeleted={bucketDeleted}
        />
        <GuidelinesPanel policy={draft} onChange={change} />
        <SamplesPanel policy={draft} onChange={change} />
        <div ref={contextRef} className="scroll-mt-4">
          <ContextPanel
            projectId={project.id}
            docs={context.docs}
            loadError={context.error}
            reload={context.reload}
            dialogOpen={contextOpen}
            onDialogOpen={setContextOpen}
          />
        </div>
      </div>

      <QuickCheck projectId={project.id} policy={policy} dirty={dirty} />

      <details
        className="rounded-lg border p-4"
        open={advancedOpen}
        onToggle={(e) => setAdvancedOpen(e.currentTarget.open)}
      >
        <summary className="cursor-pointer font-medium">Advanced</summary>
        <div className="mt-4 space-y-8">
          <p className="text-sm text-muted-foreground">
            Only needed if you want examples labelled automatically by exact
            rules.
          </p>
          <InputsPanel policy={draft} onChange={change} />
          <RulesPanel policy={draft} onChange={change} />
        </div>
      </details>

      <DraftDialog
        projectId={project.id}
        source={drafting}
        hasUnsaved={dirty}
        onLoad={(proposed, found) => {
          setDrafting(null)
          const saved = new Set(policy.policy.options.map((o) => o.key))
          onDraft({
            ...proposed,
            options: proposed.options.map((o) =>
              saved.has(o.key) ? o : markNew(o),
            ),
          })
          setOverride({ base: policy, issues: found })
          if (
            found.some((i) =>
              isAdvancedTarget(describeIssue(i, proposed).target),
            )
          )
            setAdvancedOpen(true)
          toast("Draft loaded. Fix the problems, then save.")
        }}
        onClose={() => setDrafting(null)}
        onApplied={(saved) => {
          setDrafting(null)
          onDraft(null)
          setOverride(null)
          onPolicy(saved)
          toast.success("Draft applied")
        }}
      />
    </div>
  )
}

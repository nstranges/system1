import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { describeIssue } from "@/features/rules/issueText"
import { useApi } from "@/lib/api/client"
import {
  readProblem,
  type PolicyInput,
  type PolicyIssue,
  type PolicyOut,
} from "@/lib/api/types"
import type { components } from "@/lib/api/schema"

type Draft = components["schemas"]["DraftOut"]
export type DraftSource = "examples" | "context"

const TITLES: Record<DraftSource, string> = {
  examples: "Buckets drafted from your examples",
  context: "Buckets drafted from your documents",
}

// Plain wording for the statuses the assistant can fail with.
function failure(status: number, message: string): string {
  if (status === 429)
    return `${message} Try again later, or write the buckets yourself.`
  if (status === 502 || status === 503)
    return "The assistant isn't available right now. Try again in a moment."
  return message
}

export function DraftDialog({
  projectId,
  source,
  hasUnsaved,
  onClose,
  onApplied,
  onLoad,
}: {
  projectId: string
  // null keeps the dialog closed.
  source: DraftSource | null
  hasUnsaved: boolean
  onClose: () => void
  onApplied: (saved: PolicyOut) => void
  // A proposal with problems can't be saved; it goes into the editor instead.
  onLoad: (proposed: PolicyInput, issues: PolicyIssue[]) => void
}) {
  // Closing while Apply is in flight would let onApplied run after Discard.
  const [applying, setApplying] = useState(false)
  return (
    <Dialog
      open={source !== null}
      onOpenChange={(o) => !o && !applying && onClose()}
    >
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        {source && (
          <Body
            // A new run each time the dialog opens.
            key={source}
            projectId={projectId}
            source={source}
            hasUnsaved={hasUnsaved}
            onClose={onClose}
            onApplied={onApplied}
            onLoad={onLoad}
            applying={applying}
            setApplying={setApplying}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function Body({
  projectId,
  source,
  hasUnsaved,
  onClose,
  onApplied,
  onLoad,
  applying,
  setApplying,
}: {
  projectId: string
  source: DraftSource
  hasUnsaved: boolean
  onClose: () => void
  onApplied: (saved: PolicyOut) => void
  onLoad: (proposed: PolicyInput, issues: PolicyIssue[]) => void
  applying: boolean
  setApplying: (b: boolean) => void
}) {
  const api = useApi()
  const [draft, setDraft] = useState<Draft | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [applyError, setApplyError] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    void api
      .POST("/api/projects/{project_id}/draft", {
        params: { path: { project_id: projectId } },
        body: { source },
      })
      .then(({ data, error: err, response }) => {
        if (!live) return
        if (data) setDraft(data)
        else setError(failure(response.status, readProblem(err).message))
      })
    return () => {
      live = false
    }
  }, [api, projectId, source])

  async function apply() {
    if (!draft) return
    setApplying(true)
    setApplyError(null)
    const { data, error: err } = await api.PUT(
      "/api/projects/{project_id}/policy",
      {
        params: { path: { project_id: projectId } },
        body: { policy: draft.policy },
      },
    )
    setApplying(false)
    if (data) {
      onApplied(data)
      return
    }
    setApplyError(readProblem(err).message)
  }

  const proposed = draft?.policy as PolicyInput | undefined

  return (
    <>
      <DialogHeader>
        <DialogTitle>{TITLES[source]}</DialogTitle>
        <DialogDescription>
          Read the proposal, then apply it or throw it away.
          {hasUnsaved && " Applying it replaces your unsaved changes."}
        </DialogDescription>
      </DialogHeader>
      {!draft && !error && (
        <div className="space-y-2" aria-busy="true">
          <p className="text-sm text-muted-foreground">
            The assistant is reading…
          </p>
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      {draft && proposed && (
        <div className="space-y-4 text-sm">
          <div className="space-y-2">
            <h4 className="font-medium">Buckets ({proposed.options.length})</h4>
            {proposed.options.map((o) => (
              <div key={o.key} className="rounded-lg border p-3">
                <p className="font-medium">{o.name}</p>
                {(o.covers ?? []).length > 0 && (
                  <ul className="mt-1 list-disc pl-5 text-muted-foreground">
                    {(o.covers ?? []).map((c, n) => (
                      <li key={n}>{c}</li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
          {(proposed.guidelines ?? []).length > 0 && (
            <div className="space-y-1">
              <h4 className="font-medium">Guidelines</h4>
              <ol className="list-decimal space-y-0.5 pl-5 text-muted-foreground">
                {(proposed.guidelines ?? []).map((g, n) => (
                  <li key={n}>{g}</li>
                ))}
              </ol>
            </div>
          )}
          {draft.notes.length > 0 && (
            <div className="space-y-1">
              <h4 className="font-medium">Notes from the assistant</h4>
              <ul className="list-disc space-y-0.5 pl-5 text-muted-foreground">
                {draft.notes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            </div>
          )}
          {draft.issues.length > 0 && (
            <div
              role="alert"
              className="rounded-lg border border-destructive/40 bg-destructive/5 p-3"
            >
              <p className="font-medium text-destructive">
                This proposal has problems. Load it into the editor to fix them
              </p>
              <ul className="mt-1 list-disc pl-5">
                {draft.issues.map((issue, n) => (
                  <li key={n}>{describeIssue(issue, proposed).text}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      {applyError && (
        <p role="alert" className="text-sm text-destructive">
          {applyError}
        </p>
      )}
      <DialogFooter>
        <Button variant="ghost" disabled={applying} onClick={onClose}>
          Discard
        </Button>
        {draft && draft.issues.length > 0 ? (
          <Button onClick={() => onLoad(draft.policy, draft.issues)}>
            Load into editor
          </Button>
        ) : (
          <Button disabled={!draft || applying} onClick={() => void apply()}>
            {applying ? "Applying…" : "Apply"}
          </Button>
        )}
      </DialogFooter>
    </>
  )
}

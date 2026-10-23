import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { NativeSelect } from "@/features/rules/fields"
import { useApi } from "@/lib/api/client"
import { readProblem, type PolicyOption } from "@/lib/api/types"

export interface DeleteTarget {
  key: string
  name: string
  examples: number
}

export function DeleteBucketDialog({
  projectId,
  target,
  others,
  onClose,
  onDeleted,
}: {
  projectId: string
  target: DeleteTarget | null
  others: PolicyOption[]
  onClose: () => void
  onDeleted: (key: string) => Promise<void>
}) {
  return (
    <Dialog open={target !== null} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        {target && (
          <Body
            // Fresh state for each bucket.
            key={target.key}
            projectId={projectId}
            target={target}
            others={others}
            onClose={onClose}
            onDeleted={onDeleted}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function Body({
  projectId,
  target,
  others,
  onClose,
  onDeleted,
}: {
  projectId: string
  target: DeleteTarget
  others: PolicyOption[]
  onClose: () => void
  onDeleted: (key: string) => Promise<void>
}) {
  const api = useApi()
  const [mode, setMode] = useState<"drop" | "move">("drop")
  const [to, setTo] = useState(others[0]?.key ?? "")
  const [needsReset, setNeedsReset] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit() {
    setBusy(true)
    setError(null)
    const { data, error: err } = await api.POST(
      "/api/projects/{project_id}/buckets/{key}/delete",
      {
        params: { path: { project_id: projectId, key: target.key } },
        body: {
          mode,
          to: mode === "move" ? to : null,
          reset_test: needsReset && confirmed,
        },
      },
    )
    if (data) {
      await onDeleted(target.key)
      return
    }
    setBusy(false)
    const problem = readProblem(err)
    if (problem.code === "test_reset_required") {
      setNeedsReset(true)
      return
    }
    setError(problem.message)
  }

  const count = `${target.examples} ${target.examples === 1 ? "example" : "examples"}`

  return (
    <>
      <DialogHeader>
        <DialogTitle>Delete "{target.name}"?</DialogTitle>
        <DialogDescription>
          {count} {target.examples === 1 ? "uses" : "use"} this bucket. What
          should happen to {target.examples === 1 ? "it" : "them"}?
        </DialogDescription>
      </DialogHeader>
      <fieldset className="space-y-2 text-sm">
        <legend className="sr-only">What happens to the examples</legend>
        <label className="flex items-center gap-2">
          <input
            type="radio"
            name="mode"
            checked={mode === "drop"}
            onChange={() => setMode("drop")}
          />
          Drop its examples
        </label>
        <label className="flex items-center gap-2">
          <input
            type="radio"
            name="mode"
            checked={mode === "move"}
            disabled={others.length === 0}
            onChange={() => setMode("move")}
          />
          Move them to…
        </label>
        {mode === "move" && (
          <NativeSelect value={to} onChange={(e) => setTo(e.target.value)}>
            {others.map((o) => (
              <option key={o.key} value={o.key}>
                {o.name || o.key}
              </option>
            ))}
          </NativeSelect>
        )}
      </fieldset>
      {needsReset && (
        <div
          role="alert"
          className="space-y-2 rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm"
        >
          <p>
            Your test examples are locked. Deleting this bucket resets the test
            set, and earlier results can't be compared.
          </p>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            Reset the test set
          </label>
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <DialogFooter>
        <Button variant="ghost" onClick={onClose}>
          Keep bucket
        </Button>
        <Button
          variant="destructive"
          disabled={
            busy || (mode === "move" && !to) || (needsReset && !confirmed)
          }
          onClick={() => void submit()}
        >
          {busy ? "Deleting…" : "Delete bucket"}
        </Button>
      </DialogFooter>
    </>
  )
}

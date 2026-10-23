import { Plus, X } from "lucide-react"
import { useRef, useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { FieldLabel } from "@/features/rules/fields"
import { isNew, markNew } from "@/features/rules/newRow"
import { useApi } from "@/lib/api/client"
import {
  readProblem,
  type PolicyInput,
  type PolicyOption,
} from "@/lib/api/types"
import { DeleteBucketDialog, type DeleteTarget } from "./DeleteBucketDialog"

export const MAX_BUCKETS = 15
export const MIN_BUCKETS = 2

const slug = (text: string) =>
  text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "")

export function BucketsPanel({
  projectId,
  policy,
  onChange,
  onDeleted,
}: {
  projectId: string
  policy: PolicyInput
  onChange: (next: PolicyInput) => void
  // The server already removed the bucket from the saved policy.
  onDeleted: (key: string) => Promise<void>
}) {
  const api = useApi()
  const options = policy.options
  const [target, setTarget] = useState<DeleteTarget | null>(null)
  const [checking, setChecking] = useState(false)
  // The health request is async; removal must apply to the policy as it is
  // when the answer arrives, not as it was when the click happened.
  const latest = useRef({ policy, onChange })
  latest.current = { policy, onChange }
  const set = (i: number, patch: Partial<PolicyOption>) =>
    onChange({
      ...policy,
      options: options.map((o, j) => (j === i ? { ...o, ...patch } : o)),
    })
  const drop = (i: number) =>
    onChange({ ...policy, options: options.filter((_, j) => j !== i) })

  async function remove(i: number) {
    const o = options[i]
    const users = (policy.rules ?? []).filter((r) => r.label === o.key)
    if (o.key && users.length > 0) {
      toast.error(
        `${users.map((r) => r.id).join(", ")} still ${users.length === 1 ? "points" : "point"} to "${o.name || o.key}". Change ${users.length === 1 ? "that exact rule" : "those exact rules"} first (under Advanced).`,
      )
      return
    }
    // A bucket that was never saved has no examples to worry about.
    if (!o.key || isNew(o)) return drop(i)
    if (checking) return
    setChecking(true)
    const { data, error } = await api.GET(
      "/api/projects/{project_id}/examples/health",
      { params: { path: { project_id: projectId } } },
    )
    setChecking(false)
    const dropKey = () => {
      const { policy: p, onChange: change } = latest.current
      change({ ...p, options: p.options.filter((x) => x.key !== o.key) })
    }
    if (!data) {
      toast.error(readProblem(error).message)
      return
    }
    const splits = data.per_bucket[o.key] ?? {}
    const total = Object.values(splits).reduce((a, b) => a + b, 0)
    if (total === 0) return dropKey()
    setTarget({
      key: o.key,
      name: o.name || o.key,
      examples: total,
    })
  }

  return (
    <section id="define-buckets" className="space-y-3 rounded-lg">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="font-medium">Buckets ({options.length})</h3>
          <p className="text-sm text-muted-foreground">
            The possible outcomes of the decision. Pick between {MIN_BUCKETS}{" "}
            and {MAX_BUCKETS}.
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          disabled={options.length >= MAX_BUCKETS}
          title={
            options.length >= MAX_BUCKETS
              ? `${MAX_BUCKETS} buckets is the most`
              : undefined
          }
          onClick={() =>
            onChange({
              ...policy,
              options: [
                ...options,
                markNew({ key: "", name: "", example: "" }),
              ],
            })
          }
        >
          <Plus /> Add bucket
        </Button>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {options.map((o, i) => (
          <div
            id={`option-${i}`}
            key={i}
            className="space-y-2 rounded-lg border p-3"
          >
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <FieldLabel>Name</FieldLabel>
                <Input
                  value={o.name}
                  onChange={(e) =>
                    set(i, {
                      name: e.target.value,
                      ...(isNew(o) ? { key: slug(e.target.value) } : {}),
                    })
                  }
                />
              </div>
              <Button
                size="icon"
                variant="ghost"
                aria-label={`Remove ${o.name || "bucket"}`}
                disabled={options.length <= MIN_BUCKETS || checking}
                title={
                  options.length <= MIN_BUCKETS
                    ? `You need at least ${MIN_BUCKETS} buckets`
                    : undefined
                }
                onClick={() => void remove(i)}
              >
                <X />
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Key:{" "}
              <span className="font-mono">{o.key || "(from the name)"}</span>
            </p>
            <div>
              <FieldLabel>Use this when… (one per line)</FieldLabel>
              <Textarea
                rows={3}
                value={(o.covers ?? []).join("\n")}
                onChange={(e) => set(i, { covers: e.target.value.split("\n") })}
              />
            </div>
            <div>
              <FieldLabel>Example (optional)</FieldLabel>
              <Input
                value={o.example ?? ""}
                onChange={(e) => set(i, { example: e.target.value })}
              />
            </div>
          </div>
        ))}
      </div>
      <DeleteBucketDialog
        projectId={projectId}
        target={target}
        others={options.filter(
          (o) => o.key && !isNew(o) && o.key !== target?.key,
        )}
        onClose={() => setTarget(null)}
        onDeleted={async (key) => {
          setTarget(null)
          await onDeleted(key)
        }}
      />
    </section>
  )
}

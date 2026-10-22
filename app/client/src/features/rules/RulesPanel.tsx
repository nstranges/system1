import { ArrowDown, ArrowUp, Plus, X } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import type { PolicyInput } from "@/lib/api/types"
import { NativeSelect } from "./fields"

export function RulesPanel({
  policy,
  onChange,
}: {
  policy: PolicyInput
  onChange: (next: PolicyInput) => void
}) {
  const rules = policy.rules ?? []
  const labels = policy.options.map((o) => o.key).filter(Boolean)
  const setRules = (next: typeof rules) => onChange({ ...policy, rules: next })
  const set = (i: number, patch: Partial<(typeof rules)[number]>) =>
    setRules(rules.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  const move = (i: number, by: number) => {
    const next = [...rules]
    ;[next[i], next[i + by]] = [next[i + by], next[i]]
    setRules(next)
  }
  const nextId = () => {
    let n = rules.length + 1
    while (rules.some((r) => r.id === `R${String(n).padStart(2, "0")}`)) n++
    return `R${String(n).padStart(2, "0")}`
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-medium">Rules</h3>
          <p className="text-sm text-muted-foreground">
            Checked from the top. The first rule that fits decides.
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() =>
            setRules([
              ...rules,
              { id: nextId(), text: "", label: labels[0] ?? "" },
            ])
          }
        >
          <Plus /> Add
        </Button>
      </div>
      <ol className="space-y-2">
        {rules.map((r, i) => (
          <li key={r.id + i} className="flex gap-2 rounded-lg border p-3">
            <div className="flex flex-col items-center gap-1">
              <span className="text-xs font-medium text-muted-foreground">
                {i + 1}
              </span>
              <Button
                size="icon-xs"
                variant="ghost"
                aria-label="Move up"
                disabled={i === 0}
                onClick={() => move(i, -1)}
              >
                <ArrowUp />
              </Button>
              <Button
                size="icon-xs"
                variant="ghost"
                aria-label="Move down"
                disabled={i === rules.length - 1}
                onClick={() => move(i, 1)}
              >
                <ArrowDown />
              </Button>
            </div>
            <div className="min-w-0 flex-1 space-y-2">
              <Textarea
                rows={2}
                value={r.text}
                onChange={(e) => set(i, { text: e.target.value })}
              />
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm text-muted-foreground">then</span>
                <NativeSelect
                  className="w-auto max-w-full"
                  value={r.label}
                  onChange={(e) => set(i, { label: e.target.value })}
                >
                  {!labels.includes(r.label) && (
                    <option value={r.label}>
                      {r.label || "Pick an option"}
                    </option>
                  )}
                  {labels.map((l) => (
                    <option key={l} value={l}>
                      {l}
                    </option>
                  ))}
                </NativeSelect>
                {r.when ? (
                  <Badge variant="default">testable</Badge>
                ) : (
                  <Badge variant="secondary">needs judgment</Badge>
                )}
                <span className="font-mono text-xs text-muted-foreground">
                  {r.id}
                </span>
              </div>
            </div>
            <Button
              size="icon"
              variant="ghost"
              aria-label="Remove rule"
              onClick={() => setRules(rules.filter((_, j) => j !== i))}
            >
              <X />
            </Button>
          </li>
        ))}
      </ol>
    </section>
  )
}

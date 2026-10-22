import { Plus, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import type { PolicyInput, PolicyOption } from "@/lib/api/types"
import { FieldLabel } from "./fields"

const lines = (text: string) => text.split("\n")
const slug = (text: string) =>
  text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "")

export function OptionsPanel({
  policy,
  onChange,
}: {
  policy: PolicyInput
  onChange: (next: PolicyInput) => void
}) {
  const options = policy.options
  const set = (i: number, patch: Partial<PolicyOption>) =>
    onChange({
      ...policy,
      options: options.map((o, j) => (j === i ? { ...o, ...patch } : o)),
    })

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-medium">Options ({options.length})</h3>
          <p className="text-sm text-muted-foreground">
            Every answer the decision can give. Pick between 2 and 15.
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() =>
            onChange({
              ...policy,
              options: [...options, { key: "", name: "", example: "" }],
            })
          }
        >
          <Plus /> Add
        </Button>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {options.map((o, i) => (
          <div key={i} className="space-y-2 rounded-lg border p-3">
            <div className="flex items-end gap-2">
              <div className="flex-1">
                <FieldLabel>Name</FieldLabel>
                <Input
                  value={o.name}
                  onChange={(e) =>
                    set(i, {
                      name: e.target.value,
                      ...(o.key === "" || o.key === slug(o.name)
                        ? { key: slug(e.target.value) }
                        : {}),
                    })
                  }
                />
              </div>
              <Button
                size="icon"
                variant="ghost"
                aria-label={`Remove ${o.name || "option"}`}
                onClick={() =>
                  onChange({
                    ...policy,
                    options: options.filter((_, j) => j !== i),
                  })
                }
              >
                <X />
              </Button>
            </div>
            <div>
              <FieldLabel>Short name (used in answers)</FieldLabel>
              <Input
                className="font-mono text-xs"
                value={o.key}
                onChange={(e) => set(i, { key: e.target.value })}
              />
            </div>
            <div>
              <FieldLabel>Covers, one per line</FieldLabel>
              <Textarea
                rows={2}
                value={(o.covers ?? []).join("\n")}
                onChange={(e) => set(i, { covers: lines(e.target.value) })}
              />
            </div>
            <div>
              <FieldLabel>Doesn't cover, one per line</FieldLabel>
              <Textarea
                rows={2}
                value={(o.excludes ?? []).join("\n")}
                onChange={(e) => set(i, { excludes: lines(e.target.value) })}
              />
            </div>
            <div>
              <FieldLabel>Example</FieldLabel>
              <Input
                value={o.example ?? ""}
                onChange={(e) => set(i, { example: e.target.value })}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

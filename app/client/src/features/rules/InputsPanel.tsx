import { Plus, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { InputField, PolicyInput } from "@/lib/api/types"
import { isNew, markNew } from "./newRow"
import { FieldLabel, NativeSelect } from "./fields"

const TYPES: { value: InputField["type"]; label: string }[] = [
  { value: "enum", label: "One of a list" },
  { value: "int", label: "Whole number" },
  { value: "float", label: "Number" },
  { value: "bool", label: "Yes or no" },
  { value: "text", label: "Text" },
]

function slug(text: string) {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "")
}

export function InputsPanel({
  policy,
  onChange,
}: {
  policy: PolicyInput
  onChange: (next: PolicyInput) => void
}) {
  const inputs = policy.inputs ?? []
  const set = (i: number, patch: Partial<InputField>) =>
    onChange({
      ...policy,
      inputs: inputs.map((f, j) => (j === i ? { ...f, ...patch } : f)),
    })

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-medium">Facts it looks at</h3>
          <p className="text-sm text-muted-foreground">
            The details your rules depend on, like the amount or the plan.
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={() =>
            onChange({
              ...policy,
              inputs: [
                ...inputs,
                markNew({
                  key: "",
                  label: "",
                  type: "text",
                  nullable: true,
                  description: "",
                }),
              ],
            })
          }
        >
          <Plus /> Add
        </Button>
      </div>
      <div className="space-y-2">
        {inputs.map((f, i) => (
          <div key={i} className="rounded-lg border p-3">
            <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
              <div>
                <FieldLabel>Name</FieldLabel>
                <Input
                  value={f.label}
                  onChange={(e) =>
                    set(i, {
                      label: e.target.value,
                      // Only facts that were never saved take their short name from the label.
                      ...(isNew(f) ? { key: slug(e.target.value) } : {}),
                    })
                  }
                />
              </div>
              <div>
                <FieldLabel>Kind</FieldLabel>
                <NativeSelect
                  value={f.type}
                  onChange={(e) =>
                    set(i, { type: e.target.value as InputField["type"] })
                  }
                >
                  {TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </NativeSelect>
              </div>
              <div className="flex items-end">
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label={`Remove ${f.label || "fact"}`}
                  onClick={() =>
                    onChange({
                      ...policy,
                      inputs: inputs.filter((_, j) => j !== i),
                    })
                  }
                >
                  <X />
                </Button>
              </div>
            </div>
            {f.type === "enum" && (
              <div className="mt-2">
                <FieldLabel>Allowed values, separated by commas</FieldLabel>
                <Input
                  value={(f.values ?? []).join(", ")}
                  onChange={(e) =>
                    set(i, {
                      values: e.target.value
                        .split(",")
                        .map((v) => v.trim())
                        .filter(Boolean),
                    })
                  }
                />
              </div>
            )}
            <div className="mt-2">
              <FieldLabel>Where it comes from</FieldLabel>
              <Input
                value={f.description ?? ""}
                onChange={(e) => set(i, { description: e.target.value })}
              />
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

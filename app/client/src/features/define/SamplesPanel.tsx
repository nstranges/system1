import { Plus, X } from "lucide-react"
import { Hint } from "@/components/Hint"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import type { PolicyInput } from "@/lib/api/types"

export const MAX_SAMPLES = 3
export const MAX_SAMPLE_CHARS = 6000

export function SamplesPanel({
  policy,
  onChange,
}: {
  policy: PolicyInput
  onChange: (next: PolicyInput) => void
}) {
  const items = policy.sample_inputs ?? []
  const set = (next: string[]) => onChange({ ...policy, sample_inputs: next })

  return (
    <section id="define-samples" className="space-y-3 rounded-lg">
      <div className="flex items-center justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-medium">What comes in</h3>
            <Hint text="Paste one or two real inputs, like a ticket or an email. They help the assistant write realistic practice examples." />
          </div>
          <p className="text-sm text-muted-foreground">
            Paste one or two real inputs, like a ticket or an email. They help
            the assistant write realistic practice examples.
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          disabled={items.length >= MAX_SAMPLES}
          title={
            items.length >= MAX_SAMPLES
              ? `${MAX_SAMPLES} samples is the most`
              : undefined
          }
          onClick={() => set([...items, ""])}
        >
          <Plus /> Add
        </Button>
      </div>
      <div className="space-y-3">
        {items.map((s, i) => (
          <div key={i} className="space-y-1 rounded-lg border p-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">
                Input {i + 1}
              </span>
              <Button
                size="icon"
                variant="ghost"
                aria-label={`Remove input ${i + 1}`}
                onClick={() => set(items.filter((_, j) => j !== i))}
              >
                <X />
              </Button>
            </div>
            <Textarea
              rows={5}
              className="font-voice text-[15px]!"
              value={s}
              maxLength={MAX_SAMPLE_CHARS}
              aria-label={`Sample input ${i + 1}`}
              onChange={(e) =>
                set(items.map((x, j) => (j === i ? e.target.value : x)))
              }
            />
            <p className="text-right text-xs text-muted-foreground">
              {s.length} / {MAX_SAMPLE_CHARS}
            </p>
          </div>
        ))}
      </div>
    </section>
  )
}

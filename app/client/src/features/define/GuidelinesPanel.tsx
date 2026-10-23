import { ArrowDown, ArrowUp, Plus, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { PolicyInput } from "@/lib/api/types"

export const MAX_GUIDELINES = 20
export const MAX_GUIDELINE_CHARS = 300

export function GuidelinesPanel({
  policy,
  onChange,
}: {
  policy: PolicyInput
  onChange: (next: PolicyInput) => void
}) {
  const items = policy.guidelines ?? []
  const set = (next: string[]) => onChange({ ...policy, guidelines: next })
  const move = (i: number, by: -1 | 1) => {
    const next = [...items]
    ;[next[i], next[i + by]] = [next[i + by], next[i]]
    set(next)
  }

  return (
    <section id="define-guidelines" className="space-y-3 rounded-lg">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="font-medium">Guidelines ({items.length})</h3>
          <p className="text-sm text-muted-foreground">
            Plain sentences that say how to decide, most important first. For
            example: "A customer who can't log in is urgent."
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          disabled={items.length >= MAX_GUIDELINES}
          title={
            items.length >= MAX_GUIDELINES
              ? `${MAX_GUIDELINES} guidelines is the most`
              : undefined
          }
          onClick={() => set([...items, ""])}
        >
          <Plus /> Add
        </Button>
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No guidelines yet. They're optional, and they make the assistant's
          practice examples closer to how you decide.
        </p>
      ) : (
        <ol className="space-y-2">
          {items.map((g, i) => (
            <li key={i} className="flex items-start gap-2">
              <span className="mt-2 w-5 text-right text-sm text-muted-foreground">
                {i + 1}.
              </span>
              <div className="flex-1">
                <Input
                  value={g}
                  maxLength={MAX_GUIDELINE_CHARS}
                  aria-label={`Guideline ${i + 1}`}
                  onChange={(e) =>
                    set(items.map((x, j) => (j === i ? e.target.value : x)))
                  }
                />
                {g.length > MAX_GUIDELINE_CHARS * 0.8 && (
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {g.length} / {MAX_GUIDELINE_CHARS}
                  </p>
                )}
              </div>
              <Button
                size="icon"
                variant="ghost"
                aria-label={`Move guideline ${i + 1} up`}
                disabled={i === 0}
                onClick={() => move(i, -1)}
              >
                <ArrowUp />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                aria-label={`Move guideline ${i + 1} down`}
                disabled={i === items.length - 1}
                onClick={() => move(i, 1)}
              >
                <ArrowDown />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                aria-label={`Remove guideline ${i + 1}`}
                onClick={() => set(items.filter((_, j) => j !== i))}
              >
                <X />
              </Button>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

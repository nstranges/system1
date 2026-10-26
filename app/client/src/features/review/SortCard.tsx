import { useState } from "react"
import { BucketChip, BucketSwatch } from "@/components/BucketChip"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import type { components } from "@/lib/api/schema"
import { bucketIndex } from "@/lib/buckets"
import type { PolicyOption } from "@/lib/api/types"
import { cn } from "@/lib/utils"

export type ReviewExample = components["schemas"]["ExampleOut"]
const LONG = 280

function inputText(input: ReviewExample["input"]): string {
  return typeof input === "string"
    ? input
    : Object.entries(input)
        .map(([k, v]) => `${k}: ${String(v)}`)
        .join("\n")
}

export function SortCard({
  example,
  buckets,
  busy,
  active,
  index,
  onAgree,
  onMove,
}: {
  example: ReviewExample
  buckets: PolicyOption[]
  busy: boolean
  // The card the keyboard shortcuts act on.
  active: boolean
  // Its position in the list, for the id the list scrolls to.
  index: number
  onAgree: () => void
  onMove: (to: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const text = inputText(example.input)
  const long = text.length > LONG
  const current = buckets.find((b) => b.key === example.label)
  const sure =
    example.how_sure === null
      ? null
      : Math.round(Math.min(1, Math.max(0, example.how_sure)) * 100)

  return (
    <Card
      size="sm"
      id={`review-card-${index}`}
      aria-current={active ? "true" : undefined}
      className={cn(active && "ring-2 ring-ring")}
    >
      <CardContent className="space-y-3">
        <p className="font-voice whitespace-pre-wrap">
          {long && !expanded ? `${text.slice(0, LONG)}…` : text}
        </p>
        {long && (
          <button
            type="button"
            className="text-xs text-muted-foreground hover:text-foreground"
            onClick={() => setExpanded((e) => !e)}
          >
            {expanded ? "Show less" : "Show more"}
          </button>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <BucketChip
            name={current?.name ?? example.label}
            index={bucketIndex(buckets, example.label)}
          />
          {sure !== null && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <div
                role="progressbar"
                aria-label="How sure"
                aria-valuenow={sure}
                aria-valuemin={0}
                aria-valuemax={100}
                className="h-1.5 w-24 overflow-hidden rounded-full bg-muted"
              >
                <div
                  className="h-full bg-primary"
                  style={{ width: `${sure}%` }}
                />
              </div>
              How sure: {sure}%
            </div>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" disabled={busy} onClick={onAgree}>
            Looks right
          </Button>
          {buckets.map((b, i) => {
            const isCurrent = b.key === example.label
            return (
              <Button
                key={b.key}
                size="sm"
                variant={isCurrent ? "secondary" : "outline"}
                aria-pressed={isCurrent}
                disabled={busy}
                onClick={() => (isCurrent ? onAgree() : onMove(b.key))}
              >
                <BucketSwatch index={i} />
                {b.name}
                {i < 9 && (
                  <span className="text-[13px] text-muted-foreground tabular-nums">
                    {i + 1}
                  </span>
                )}
              </Button>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

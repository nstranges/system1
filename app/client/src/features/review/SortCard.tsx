import { ChevronDown } from "lucide-react"
import { useState } from "react"
import { BucketChip } from "@/components/BucketChip"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { components } from "@/lib/api/schema"
import { bucketIndex } from "@/lib/buckets"
import type { PolicyOption } from "@/lib/api/types"

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
  onAgree,
  onMove,
}: {
  example: ReviewExample
  buckets: PolicyOption[]
  busy: boolean
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
    <Card size="sm">
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
        <div className="flex gap-2">
          <Button size="sm" disabled={busy} onClick={onAgree}>
            Looks right
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger
              render={<Button size="sm" variant="outline" disabled={busy} />}
            >
              Move to… <ChevronDown />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start">
              {buckets
                .filter((b) => b.key !== example.label)
                .map((b) => (
                  <DropdownMenuItem key={b.key} onClick={() => onMove(b.key)}>
                    {b.name}
                  </DropdownMenuItem>
                ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardContent>
    </Card>
  )
}

import { useState } from "react"
import type { TrainedModel } from "@/lib/api/types"

const W = 320
const H = 120
const PAD_X = 12
const PAD_Y = 12

const pct = (v: number) => `${Math.round(v * 100)}%`

// Test accuracy of each trained version, oldest to newest, next to Jev on the same test examples. Only versions
// scored on the current test set are drawn, since scores on different test sets don't compare.
export function ModelHistory({ models }: { models: TrainedModel[] }) {
  const [hover, setHover] = useState<number | null>(null)
  const latestSet = Math.max(...models.map((m) => m.test_set_version))
  const points = models
    .filter((m) => m.test_set_version === latestSet && m.accuracy != null)
    .sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at))
  if (points.length < 2) return null

  const values = points.flatMap((m) => [
    m.accuracy!,
    m.jev_accuracy ?? m.accuracy!,
  ])
  const y0 = Math.max(0, Math.min(...values) - 0.05)
  const y1 = Math.min(1, Math.max(...values) + 0.05)
  const sx = (i: number) =>
    PAD_X + (i / Math.max(1, points.length - 1)) * (W - 2 * PAD_X)
  const sy = (y: number) =>
    H - PAD_Y - ((y - y0) / Math.max(1e-9, y1 - y0)) * (H - 2 * PAD_Y)
  const ours = points.map((m, i) => `${sx(i)},${sy(m.accuracy!)}`).join(" ")
  const jevPoints = points.filter((m) => m.jev_accuracy != null)
  const jev = points
    .map((m, i) =>
      m.jev_accuracy != null ? `${sx(i)},${sy(m.jev_accuracy)}` : null,
    )
    .filter(Boolean)
    .join(" ")
  const active = hover === null ? null : points[hover]

  function onMove(e: React.PointerEvent<SVGSVGElement>) {
    const box = e.currentTarget.getBoundingClientRect()
    const x = ((e.clientX - box.left) / box.width) * W
    let nearest = 0
    points.forEach((_, i) => {
      if (Math.abs(sx(i) - x) < Math.abs(sx(nearest) - x)) nearest = i
    })
    setHover(nearest)
  }

  return (
    <figure className="space-y-2">
      <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <svg width="16" height="8" aria-hidden>
            <line
              x1="0"
              y1="4"
              x2="16"
              y2="4"
              className="stroke-model"
              strokeWidth="2"
            />
          </svg>
          Your model
        </span>
        {jevPoints.length > 0 && (
          <span className="flex items-center gap-1.5">
            <svg width="16" height="8" aria-hidden>
              <line
                x1="0"
                y1="4"
                x2="16"
                y2="4"
                className="stroke-jev"
                strokeWidth="2"
                strokeDasharray="4 3"
              />
            </svg>
            Jev
          </span>
        )}
        <span>Ringed point: the live model</span>
      </div>
      <div className="relative">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="h-40 w-full touch-none"
          role="img"
          aria-label="Test accuracy of each trained version"
          onPointerMove={onMove}
          onPointerLeave={() => setHover(null)}
        >
          <line
            x1={PAD_X}
            x2={W - PAD_X}
            y1={H - PAD_Y}
            y2={H - PAD_Y}
            className="stroke-border"
            strokeWidth="1"
          />
          {jev && (
            <polyline
              fill="none"
              className="stroke-jev"
              strokeWidth="2"
              strokeDasharray="4 3"
              points={jev}
            />
          )}
          <polyline
            fill="none"
            className="stroke-model"
            strokeWidth="2"
            strokeLinejoin="round"
            points={ours}
          />
          {points.map((m, i) => (
            <circle
              key={m.id}
              cx={sx(i)}
              cy={sy(m.accuracy!)}
              r={m.live ? 6 : 4}
              className={
                m.live ? "fill-card stroke-model" : "fill-model stroke-card"
              }
              strokeWidth="2"
            />
          ))}
          {active && (
            <line
              x1={sx(hover!)}
              x2={sx(hover!)}
              y1={PAD_Y / 2}
              y2={H - PAD_Y}
              className="stroke-muted-foreground"
              strokeWidth="1"
              strokeDasharray="2 2"
            />
          )}
        </svg>
        <span className="pointer-events-none absolute top-0 left-0 text-[10px] text-muted-foreground tabular-nums">
          {pct(y1)}
        </span>
        <span className="pointer-events-none absolute bottom-0 left-0 text-[10px] text-muted-foreground tabular-nums">
          {pct(y0)}
        </span>
        {active && (
          <div className="pointer-events-none absolute top-1 right-1 rounded-md border bg-popover px-2 py-1 text-xs shadow-sm tabular-nums">
            <div className="text-muted-foreground">
              Version {hover! + 1} ·{" "}
              {new Date(active.created_at).toLocaleDateString(undefined, {
                month: "short",
                day: "numeric",
                hour: "numeric",
                minute: "2-digit",
              })}
              {active.live && " · live"}
            </div>
            <div>Your model {pct(active.accuracy!)}</div>
            {active.jev_accuracy != null && (
              <div>Jev {pct(active.jev_accuracy)}</div>
            )}
            {active.corrections_used ? (
              <div className="text-muted-foreground">
                Learned from {active.corrections_used} checked answers
              </div>
            ) : null}
          </div>
        )}
      </div>
    </figure>
  )
}

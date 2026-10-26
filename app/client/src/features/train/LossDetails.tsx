import { useState } from "react"

// What the trainer last reported, as the server relays it from Modal. Every field is optional: a run that has not
// started learning yet has none of it.
export interface TrainingDetail {
  step?: number
  total_steps?: number
  epoch?: number
  history?: [number, number][]
  eval_history?: [number, number][]
}

export function readDetail(result: unknown): TrainingDetail | null {
  const t = (result as { training?: unknown } | null | undefined)?.training
  return t && typeof t === "object" ? (t as TrainingDetail) : null
}

const W = 320
const H = 120
const PAD_X = 8
const PAD_Y = 10

// Held-out loss is logged by epoch; place it on the step axis so both lines share one x scale.
function evalPoints(detail: TrainingDetail): [number, number][] {
  const evals = detail.eval_history ?? []
  const lastEpoch = Math.max(detail.epoch ?? 0, ...evals.map(([e]) => e))
  if (!detail.total_steps || lastEpoch <= 0) return []
  const perEpoch = detail.total_steps / lastEpoch
  return evals.map(([e, y]) => [e * perEpoch, y])
}

function Chart({ detail }: { detail: TrainingDetail }) {
  const [hover, setHover] = useState<number | null>(null)
  const points = detail.history ?? []
  const held = evalPoints(detail)
  if (points.length < 2) return null

  const all = [...points, ...held]
  const x0 = Math.min(...all.map(([x]) => x))
  const x1 = Math.max(...all.map(([x]) => x))
  const y0 = Math.min(...all.map(([, y]) => y))
  const y1 = Math.max(...all.map(([, y]) => y))
  const sx = (x: number) =>
    PAD_X + ((x - x0) / Math.max(1e-9, x1 - x0)) * (W - 2 * PAD_X)
  const sy = (y: number) =>
    H - PAD_Y - ((y - y0) / Math.max(1e-9, y1 - y0)) * (H - 2 * PAD_Y)
  const line = (pts: [number, number][]) =>
    pts.map(([x, y]) => `${sx(x)},${sy(y)}`).join(" ")

  const active = hover === null ? null : points[hover]
  const activeHeld =
    active && held.length
      ? held.reduce((best, p) =>
          Math.abs(p[0] - active[0]) < Math.abs(best[0] - active[0]) ? p : best,
        )
      : null

  function onMove(e: React.PointerEvent<SVGSVGElement>) {
    const box = e.currentTarget.getBoundingClientRect()
    const x = ((e.clientX - box.left) / box.width) * W
    let nearest = 0
    points.forEach(([px], i) => {
      if (Math.abs(sx(px) - x) < Math.abs(sx(points[nearest][0]) - x))
        nearest = i
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
          Loss on training examples
        </span>
        {held.length > 0 && (
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
            Loss on held-out examples
          </span>
        )}
      </div>
      <div className="relative">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="h-40 w-full touch-none"
          role="img"
          aria-label="Training loss by step"
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
          <polyline
            fill="none"
            className="stroke-model"
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
            points={line(points)}
          />
          {held.length > 0 && (
            <>
              <polyline
                fill="none"
                className="stroke-jev"
                strokeWidth="2"
                strokeDasharray="4 3"
                points={line(held)}
              />
              {held.map(([x, y]) => (
                <circle
                  key={x}
                  cx={sx(x)}
                  cy={sy(y)}
                  r="4"
                  className="fill-jev stroke-card"
                  strokeWidth="2"
                />
              ))}
            </>
          )}
          {active && (
            <>
              <line
                x1={sx(active[0])}
                x2={sx(active[0])}
                y1={PAD_Y / 2}
                y2={H - PAD_Y}
                className="stroke-muted-foreground"
                strokeWidth="1"
                strokeDasharray="2 2"
              />
              <circle
                cx={sx(active[0])}
                cy={sy(active[1])}
                r="4"
                className="fill-model stroke-card"
                strokeWidth="2"
              />
            </>
          )}
        </svg>
        <span className="pointer-events-none absolute top-0 left-0 text-[10px] text-muted-foreground tabular-nums">
          {y1.toFixed(2)}
        </span>
        <span className="pointer-events-none absolute bottom-0 left-0 text-[10px] text-muted-foreground tabular-nums">
          {y0.toFixed(2)}
        </span>
        {active && (
          <div className="pointer-events-none absolute top-1 right-1 rounded-md border bg-popover px-2 py-1 text-xs shadow-sm tabular-nums">
            <div className="text-muted-foreground">Step {active[0]}</div>
            <div>Loss {active[1].toFixed(3)}</div>
            {activeHeld && <div>Held-out {activeHeld[1].toFixed(3)}</div>}
          </div>
        )}
      </div>
    </figure>
  )
}

// How learning went: loss should fall as the model learns. Collapsed while training; the report card opens it.
export function LossDetails({
  detail,
  open = false,
}: {
  detail: TrainingDetail | null
  open?: boolean
}) {
  const last = detail?.history?.at(-1)
  const lastEval = detail?.eval_history?.at(-1)

  return (
    <details className="rounded-lg border p-3 text-sm" open={open}>
      <summary className="cursor-pointer font-medium">Learning curve</summary>
      <div className="mt-3 space-y-3">
        {detail?.step == null ? (
          <p className="text-muted-foreground">
            Nothing to show yet. Details appear once the model starts learning.
          </p>
        ) : (
          <>
            <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Stat
                label="Step"
                value={`${detail.step}${detail.total_steps ? ` of ${detail.total_steps}` : ""}`}
              />
              <Stat label="Epoch" value={detail.epoch?.toString() ?? "–"} />
              <Stat label="Loss" value={last ? last[1].toFixed(3) : "–"} />
              <Stat
                label="Held-out loss"
                value={lastEval ? lastEval[1].toFixed(3) : "–"}
              />
            </dl>
            <Chart detail={detail} />
            <p className="text-xs text-muted-foreground">
              Loss is how wrong the model's answers are on the examples it
              learns from. It should fall over time. If held-out loss, which
              uses examples it doesn't learn from, starts rising while loss
              keeps falling, the model is memorising instead of learning.
            </p>
          </>
        )}
      </div>
    </details>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="tabular-nums font-medium">{value}</dd>
    </div>
  )
}

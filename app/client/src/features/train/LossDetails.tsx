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
const PAD = 6

// An optional look at how learning is going: loss should fall as the model learns.
export function LossDetails({ detail }: { detail: TrainingDetail | null }) {
  const points = detail?.history ?? []
  const evals = detail?.eval_history ?? []
  const last = points.at(-1)
  const lastEval = evals.at(-1)

  let chart = null
  if (points.length >= 2) {
    const xs = points.map(([x]) => x)
    const ys = points.map(([, y]) => y)
    const x0 = Math.min(...xs)
    const x1 = Math.max(...xs)
    const y1 = Math.max(...ys)
    const y0 = Math.min(...ys)
    const sx = (x: number) =>
      PAD + ((x - x0) / Math.max(1e-9, x1 - x0)) * (W - 2 * PAD)
    const sy = (y: number) =>
      H - PAD - ((y - y0) / Math.max(1e-9, y1 - y0)) * (H - 2 * PAD)
    chart = (
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-32 w-full text-primary"
        role="img"
        aria-label="Training loss by step"
      >
        <polyline
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          points={points.map(([x, y]) => `${sx(x)},${sy(y)}`).join(" ")}
        />
      </svg>
    )
  }

  return (
    <details className="rounded-lg border p-3 text-sm">
      <summary className="cursor-pointer font-medium">Learning details</summary>
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
            {chart}
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

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import type { components } from "@/lib/api/schema"
import { LossDetails, type TrainingDetail } from "./LossDetails"

type Report = components["schemas"]["Report"]

const SHOWN = 5

const pct = (v: number) => `${Math.round(v * 100)}%`

function minutes(seconds: number): string {
  if (seconds < 90) return `${Math.round(seconds)} s`
  return `${Math.round(seconds / 60)} min`
}

// calibrate() reports its metrics under names that vary by version; read the expected-calibration-error one if present.
function calibrationError(metrics: Record<string, unknown>): number | null {
  const cal = metrics.calibration
  if (!cal || typeof cal !== "object") return null
  const ece = (cal as Record<string, unknown>).ece
  return typeof ece === "number" ? ece : null
}

// What a finished run tells you beyond the score: how it learned, where it beats Jev and where it doesn't, and
// what it mixes up. Everything here comes from the saved report card, so it stays after the run.
export function RunInsights({
  report,
  names,
}: {
  report: Report
  names: Map<string, string>
}) {
  const details = report.details ?? {}
  const rows = new Map((report.rows ?? []).map((r) => [r.key, r]))
  const mine = rows.get("sys1")
  const jev = rows.get("jev")
  const scored = mine?.status === "ok" && mine.accuracy != null
  const training = (details.training ?? null) as TrainingDetail | null
  const ece = calibrationError(details.training_metrics ?? {})
  const name = (k: string) => names.get(k) ?? k

  const tiles: { label: string; value: string; note?: string }[] = []
  if (scored && jev?.accuracy != null) {
    const points = Math.round((mine.accuracy! - jev.accuracy) * 100)
    tiles.push({
      label: "Versus Jev",
      value: `${points >= 0 ? "+" : ""}${points} points`,
      note: `${pct(mine.accuracy!)} vs ${pct(jev.accuracy)} right`,
    })
  }
  if (mine?.median_latency_ms && jev?.median_latency_ms) {
    const ratio = jev.median_latency_ms / mine.median_latency_ms
    tiles.push({
      label: "Speed",
      value:
        ratio >= 1
          ? `${ratio.toFixed(1)}× faster`
          : `${(1 / ratio).toFixed(1)}× slower`,
      note: `${Math.round(mine.median_latency_ms)} ms vs ${Math.round(jev.median_latency_ms)} ms`,
    })
  }
  if (details.train_examples != null) {
    tiles.push({
      label: "Learned from",
      value: `${details.train_examples.toLocaleString()} examples`,
      note:
        details.training_seconds != null
          ? `in ${minutes(details.training_seconds)}`
          : undefined,
    })
  }
  if (ece != null) {
    tiles.push({
      label: "Sureness gap",
      value: pct(ece),
      note: "How far its stated sureness is from how often it's right",
    })
  }

  // Per-bucket accuracy on the same test examples, so the gap is like for like.
  const ours = details.per_bucket?.sys1 ?? {}
  const theirs = details.per_bucket?.jev ?? {}
  const gaps = Object.keys(ours)
    .filter((k) => k in theirs)
    .map((k) => ({
      key: k,
      ours: ours[k],
      theirs: theirs[k],
      gap: ours[k] - theirs[k],
    }))
  const wins = gaps
    .filter((g) => g.gap > 0)
    .sort((a, b) => b.gap - a.gap)
    .slice(0, SHOWN)
  const losses = gaps
    .filter((g) => g.gap < 0)
    .sort((a, b) => a.gap - b.gap)
    .slice(0, SHOWN)
  const mixups = (details.confusions?.sys1 ?? []).slice(0, SHOWN)

  if (!tiles.length && !training && !gaps.length && !mixups.length) return null

  return (
    <Card>
      <CardHeader>
        <CardTitle>About this run</CardTitle>
        <CardDescription>
          How your model learned, and where it's strong and weak next to Jev.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {tiles.length > 0 && (
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {tiles.map((t) => (
              <div key={t.label} className="rounded-lg border p-3">
                <dt className="text-xs text-muted-foreground">{t.label}</dt>
                <dd className="text-lg font-semibold tabular-nums">
                  {t.value}
                </dd>
                {t.note && (
                  <dd className="text-xs text-muted-foreground">{t.note}</dd>
                )}
              </div>
            ))}
          </dl>
        )}

        {training && <LossDetails detail={training} open />}

        {(wins.length > 0 || losses.length > 0) && (
          <div className="grid gap-4 sm:grid-cols-2">
            <BucketList
              title="Where it beats Jev most"
              empty="Nowhere yet."
              items={wins}
              name={name}
            />
            <BucketList
              title="Where Jev does better"
              empty="Nowhere: it matches or beats Jev on every bucket."
              items={losses}
              name={name}
            />
          </div>
        )}

        {mixups.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium">What it mixes up most</h4>
            <ul className="divide-y rounded-lg border text-sm">
              {mixups.map((c) => (
                <li
                  key={`${c.gold}-${c.pred}`}
                  className="flex items-center justify-between gap-3 p-2"
                >
                  <span className="min-w-0">
                    <span className="font-medium">{name(c.gold)}</span>
                    <span className="text-muted-foreground"> answered as </span>
                    <span className="font-medium">{name(c.pred)}</span>
                  </span>
                  <span className="shrink-0 tabular-nums text-muted-foreground">
                    {c.count}×
                  </span>
                </li>
              ))}
            </ul>
            <p className="text-xs text-muted-foreground">
              More examples of these buckets, or a clearer line between them,
              usually fixes these.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function BucketList({
  title,
  empty,
  items,
  name,
}: {
  title: string
  empty: string
  items: { key: string; ours: number; theirs: number }[]
  name: (k: string) => string
}) {
  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium">{title}</h4>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{empty}</p>
      ) : (
        <ul className="divide-y rounded-lg border text-sm">
          {items.map((g) => (
            <li
              key={g.key}
              className="flex items-center justify-between gap-3 p-2"
            >
              <span className="min-w-0 truncate">{name(g.key)}</span>
              <span className="shrink-0 tabular-nums text-muted-foreground">
                {pct(g.ours)} vs Jev {pct(g.theirs)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

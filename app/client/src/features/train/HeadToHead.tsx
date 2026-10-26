import { useEffect, useState } from "react"
import type { components } from "@/lib/api/schema"
import { cn } from "@/lib/utils"
import { reportBars, type Bar, type Tone } from "./reportBars"

type Report = components["schemas"]["Report"]

const FILL: Record<Tone, string> = {
  model: "bg-model",
  jev: "bg-jev",
  base: "bg-muted-foreground/60",
}

const reducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches

// The verdict as the headline, then one bar per model on a fixed 0 to 100%
// axis. The bars grow in once; with reduced motion they start in place.
export function HeadToHead({ report }: { report: Report }) {
  const bars = reportBars(report.rows ?? [])
  const [grown, setGrown] = useState(reducedMotion)
  useEffect(() => {
    const frame = requestAnimationFrame(() => setGrown(true))
    return () => cancelAnimationFrame(frame)
  }, [])

  return (
    <div className="space-y-6">
      <p className="max-w-[30ch] text-[32px] leading-[1.1] font-semibold tracking-[-0.02em] text-balance sm:text-[40px]">
        {report.verdict?.sentence ??
          "How each model did on your test examples."}
      </p>
      <div>
        <ul>
          {bars.map((bar) => (
            <BarRow key={bar.key} bar={bar} grown={grown} />
          ))}
        </ul>
        <div className="grid grid-cols-[minmax(8rem,12rem)_1fr_4.5rem] gap-4 text-[13px] text-muted-foreground tabular-nums">
          <span />
          <span className="flex justify-between">
            <span>0%</span>
            <span>100%</span>
          </span>
          <span />
        </div>
      </div>
    </div>
  )
}

function BarRow({ bar, grown }: { bar: Bar; grown: boolean }) {
  const scored = bar.value != null
  return (
    <li
      className="grid grid-cols-[minmax(8rem,12rem)_1fr_4.5rem] items-center gap-4 py-2"
      title={
        scored
          ? `${bar.value}% right, likely between ${bar.low}% and ${bar.high}%`
          : (bar.note ?? undefined)
      }
    >
      <div>
        <div className="font-medium">{bar.label}</div>
        {bar.latencyMs != null && (
          <div className="text-[13px] text-muted-foreground tabular-nums">
            {Math.round(bar.latencyMs)} ms typical
          </div>
        )}
      </div>
      {scored ? (
        <div className="relative h-2.5 rounded-full bg-muted">
          <div
            className={cn(
              "absolute inset-y-0 left-0 rounded-l-full rounded-r-[4px] motion-safe:transition-[width] motion-safe:duration-700 motion-safe:ease-out",
              FILL[bar.tone],
            )}
            style={{ width: grown ? `${bar.value}%` : 0 }}
          />
          {bar.low != null && bar.high != null && (
            <Whisker low={bar.low} high={bar.high} />
          )}
        </div>
      ) : (
        <p className="rounded-md border border-dashed px-3 py-1.5 text-sm text-muted-foreground">
          {bar.note}
        </p>
      )}
      <div className="text-right text-lg font-semibold tabular-nums">
        {scored ? `${Math.round(bar.value ?? 0)}%` : ""}
      </div>
    </li>
  )
}

// The server's confidence interval: a hairline with a short cap at each end.
function Whisker({ low, high }: { low: number; high: number }) {
  return (
    <div
      aria-hidden
      className="absolute top-1/2 h-px bg-foreground/50"
      style={{ left: `${low}%`, width: `${Math.max(high - low, 0)}%` }}
    >
      <span className="absolute top-1/2 left-0 h-1.5 w-px -translate-y-1/2 bg-foreground/50" />
      <span className="absolute top-1/2 right-0 h-1.5 w-px -translate-y-1/2 bg-foreground/50" />
    </div>
  )
}

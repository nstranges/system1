import type { components } from "@/lib/api/schema"

type ReportRow = components["schemas"]["ReportRow"]

export type Tone = "model" | "jev" | "base"

export interface Bar {
  key: string
  label: string
  // Percent, 0 to 100.
  value: number | null
  low: number | null
  high: number | null
  tone: Tone
  // Shown in place of the bar when there is no score.
  note: string | null
  latencyMs: number | null
}

const percent = (v: number | null | undefined) =>
  v == null ? null : Math.round(v * 1000) / 10

// Keeps the server's row order: it already puts your model first.
export function reportBars(rows: ReportRow[]): Bar[] {
  return rows.map((row) => {
    const scored = row.status === "ok" && row.accuracy != null
    return {
      key: row.key,
      label: row.label,
      value: scored ? percent(row.accuracy) : null,
      low: scored ? percent(row.ci_low) : null,
      high: scored ? percent(row.ci_high) : null,
      tone:
        row.key === "sys1"
          ? "model"
          : row.key === "jev" || row.key === "jev_labels"
            ? "jev"
            : "base",
      note: scored
        ? null
        : row.status === "errored"
          ? "Too many failed answers"
          : (row.message ?? "Not available"),
      latencyMs: row.median_latency_ms ?? null,
    }
  })
}

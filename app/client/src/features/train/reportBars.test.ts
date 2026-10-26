import { expect, test } from "bun:test"
import type { components } from "@/lib/api/schema"
import { reportBars } from "./reportBars"

type ReportRow = components["schemas"]["ReportRow"]

function row(partial: Partial<ReportRow>): ReportRow {
  return {
    key: "sys1",
    label: partial.key ?? "sys1",
    status: "ok",
    message: null,
    accuracy: 0.5,
    ci_low: 0.4,
    ci_high: 0.6,
    n: 100,
    errors: 0,
    median_latency_ms: null,
    avg_p_gold: null,
    ...partial,
  }
}

test("scores become percents with their range", () => {
  const [b] = reportBars([
    row({ key: "sys1", accuracy: 0.913, ci_low: 0.86, ci_high: 0.95 }),
  ])
  expect(b).toMatchObject({
    value: 91.3,
    low: 86,
    high: 95,
    tone: "model",
    note: null,
  })
})

test("both Jev rows share Jev's tone, others are base", () => {
  expect(
    reportBars([
      row({ key: "jev" }),
      row({ key: "jev_labels" }),
      row({ key: "base" }),
    ]).map((b) => b.tone),
  ).toEqual(["jev", "jev", "base"])
})

test("a preview row shows its message instead of a bar", () => {
  const [b] = reportBars([
    row({
      key: "sys1",
      status: "preview",
      accuracy: null,
      message: "Real training connects soon.",
    }),
  ])
  expect(b.value).toBeNull()
  expect(b.note).toBe("Real training connects soon.")
})

test("an errored row says so", () => {
  expect(reportBars([row({ status: "errored", accuracy: null })])[0].note).toBe(
    "Too many failed answers",
  )
})

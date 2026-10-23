import type { PolicyInput } from "@/lib/api/types"
import { unmark } from "./newRow"

// Blank lines in textareas are for typing; drop them before saving.
export function tidy(policy: PolicyInput): PolicyInput {
  const clean = (xs?: string[]) =>
    (xs ?? []).map((x) => x.trim()).filter(Boolean)
  return {
    ...policy,
    inputs: policy.inputs?.map(unmark),
    options: policy.options.map((o) => ({
      ...unmark(o),
      covers: clean(o.covers),
      excludes: clean(o.excludes),
    })),
    guidelines: clean(policy.guidelines),
    sample_inputs: (policy.sample_inputs ?? []).filter((s) => s.trim()),
  }
}

export const STAGES = [
  {
    id: "define",
    label: "Define",
    hint: "Say what you're deciding and what the possible outcomes (buckets) are.",
  },
  {
    id: "data",
    label: "Data",
    hint: "Add examples of past decisions: upload them, generate practice ones, or both.",
  },
  {
    id: "review",
    label: "Review",
    hint: "Check the examples the model is least sure about.",
  },
  {
    id: "train",
    label: "Train",
    hint: "Teach your own model from your examples and see how it compares.",
  },
  {
    id: "use",
    label: "Use",
    hint: "Try your model, then connect it to your app.",
  },
  {
    id: "improve",
    label: "Improve",
    hint: "Fix the answers your model was unsure about and teach it again.",
  },
] as const

export type StageId = (typeof STAGES)[number]["id"]

export function isStage(value: string | undefined): value is StageId {
  return STAGES.some((s) => s.id === value)
}

// Old URLs and stored values used the earlier seven-step names.
const LEGACY: Record<string, StageId> = {
  usecase: "define",
  rules: "define",
  examples: "data",
  try: "use",
}

export function normalizeStage(legacy: string): StageId | null {
  if (isStage(legacy)) return legacy
  return LEGACY[legacy] ?? null
}

export function stageHint(id: StageId): string {
  return STAGES.find((s) => s.id === id)?.hint ?? ""
}

// Where "Continue" points once the current stage is finished: the next stage
// that isn't blocked, so the person is never sent to a step they can't use yet.
export function nextAfter(
  stages: { id: StageId; status: "done" | "ready" | "blocked" }[],
  current: StageId,
): StageId | null {
  if (stages.find((s) => s.id === current)?.status !== "done") return null
  const after = STAGES.findIndex((s) => s.id === current) + 1
  for (const { id } of STAGES.slice(after)) {
    const status = stages.find((s) => s.id === id)?.status
    if (status && status !== "blocked") return id
  }
  return null
}

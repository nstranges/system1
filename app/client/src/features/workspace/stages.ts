export const STAGES = [
  { id: "usecase", label: "Use case", ready: true },
  { id: "rules", label: "Rules", ready: true },
  { id: "try", label: "Try", ready: true },
  { id: "examples", label: "Examples", ready: false },
  { id: "train", label: "Train", ready: false },
  { id: "use", label: "Use", ready: true },
  { id: "improve", label: "Improve", ready: false },
] as const

export type StageId = (typeof STAGES)[number]["id"]

export function isStage(value: string | undefined): value is StageId {
  return STAGES.some((s) => s.id === value)
}

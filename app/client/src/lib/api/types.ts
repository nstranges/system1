import type { components } from "./schema"

export type Project = components["schemas"]["ProjectOut"]
export type Template = components["schemas"]["TemplateOut"]
export type PolicyOut = components["schemas"]["PolicyOut"]
export type Policy = components["schemas"]["Policy-Output"]
export type PolicyInput = components["schemas"]["Policy-Input"]
export type InputField = components["schemas"]["InputField"]
export type PolicyOption = components["schemas"]["Option"]
export type Rule = components["schemas"]["Rule-Output"]
export type PolicyIssue = components["schemas"]["PolicyIssue"]
export type Sample = components["schemas"]["SampleOut"]
export type LaneResult = components["schemas"]["LaneResult"]
export type TryResult = components["schemas"]["TryResult"]
export type ApiKeyOut = components["schemas"]["KeyOut"]
export type ApiKeyCreated = components["schemas"]["KeyCreated"]
export type TrainedModel = components["schemas"]["ModelOut"]

// Server errors are `{"detail": {"code", "message", "issues"?}}`. Anything else
// (a network failure, a framework 422) falls back to the generic text.
export interface ApiProblem {
  code: string
  message: string
  issues: PolicyIssue[]
}

export function readProblem(error: unknown): ApiProblem {
  const detail = (error as { detail?: unknown } | undefined)?.detail
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const d = detail as Partial<ApiProblem>
    return {
      code: d.code ?? "error",
      message: d.message ?? "Something went wrong.",
      issues: d.issues ?? [],
    }
  }
  if (typeof detail === "string") {
    return { code: "error", message: detail, issues: [] }
  }
  return { code: "error", message: "Something went wrong.", issues: [] }
}

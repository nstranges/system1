import type { PolicyInput, PolicyIssue } from "@/lib/api/types"

// Condition trees are {field,op}, {all:[…]}, {any:[…]} or {not:…}.
export function fieldsOf(when: unknown): string[] {
  if (!when || typeof when !== "object") return []
  const w = when as Record<string, unknown>
  if (typeof w.field === "string") return [w.field]
  if (Array.isArray(w.all)) return w.all.flatMap(fieldsOf)
  if (Array.isArray(w.any)) return w.any.flatMap(fieldsOf)
  if (w.not) return fieldsOf(w.not)
  return []
}

export function rulesUsingInput(policy: PolicyInput, key: string) {
  return (policy.rules ?? []).filter((r) => fieldsOf(r.when).includes(key))
}

const short = (text: string, n = 40) =>
  text.length > n ? `${text.slice(0, n).trimEnd()}…` : text

export interface IssueView {
  text: string
  // Element id of the row to scroll to, when the issue points at one.
  target?: string
}

// Turns the server's path-and-message issues into plain words. Unmapped
// issues fall back to the raw message.
export function describeIssue(
  issue: PolicyIssue,
  policy: PolicyInput,
): IssueView {
  if (issue.path === "guidelines" || /^guidelines\[\d+\]$/.test(issue.path)) {
    const n = /\[(\d+)\]/.exec(issue.path)
    return {
      text: n
        ? `Guideline ${Number(n[1]) + 1}: ${issue.message}`
        : `Guidelines: ${issue.message}`,
      target: "define-guidelines",
    }
  }
  if (/^sample_inputs(\[\d+\])?$/.test(issue.path)) {
    return {
      text: `What comes in: ${issue.message}`,
      target: "define-samples",
    }
  }
  const m = /^(rules|options|inputs)\[(\d+)\]\.?(\w*)$/.exec(issue.path)
  if (!m) return { text: issue.message }
  const [, kind, idx, field] = m
  const i = Number(idx)
  if (kind === "rules") {
    const rule = policy.rules?.[i]
    const who = rule
      ? `Rule ${i + 1} (${rule.id}${rule.text ? `: ${short(rule.text)}` : ""})`
      : `Rule ${i + 1}`
    const target = `rule-${i}`
    if (field === "label") {
      return { text: `${who} points to a bucket that doesn't exist.`, target }
    }
    const unknown = /^unknown input '(.+)'$/.exec(issue.message)
    if (field === "when" && unknown) {
      const label =
        policy.inputs?.find((f) => f.key === unknown[1])?.label || unknown[1]
      return {
        text: `${who} uses the fact "${label}", which no longer exists.`,
        target,
      }
    }
    return { text: `${who}: ${issue.message}`, target }
  }
  if (kind === "options") {
    const o = policy.options[i]
    const who = `Bucket ${i + 1}${o?.name ? ` (${o.name})` : ""}`
    if (field === "key") {
      return {
        text: /duplicate/.test(issue.message)
          ? `${who} has the same key as another bucket.`
          : `${who} needs a key with only lowercase letters, numbers and underscores.`,
        target: `option-${i}`,
      }
    }
    return { text: `${who}: ${issue.message}`, target: `option-${i}` }
  }
  const f = policy.inputs?.[i]
  return {
    text: `Fact ${i + 1}${f?.label ? ` (${f.label})` : ""}: ${issue.message}`,
    target: `input-${i}`,
  }
}

export function describeOptionCount(issue: PolicyIssue): string | null {
  return issue.path === "options" ? "Pick between 2 and 100 buckets." : null
}

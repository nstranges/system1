import type { PolicyInput, PolicyIssue } from "@/lib/api/types"
import { describeIssue, describeOptionCount } from "./issueText"

export function IssueList({
  issues,
  policy,
  title = "Fix these before you save or try it out",
}: {
  issues: PolicyIssue[]
  policy: PolicyInput
  title?: string
}) {
  if (issues.length === 0) return null
  return (
    <div
      role="alert"
      className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-sm"
    >
      <p className="font-medium text-destructive">{title}</p>
      <ul className="mt-1 list-disc space-y-0.5 pl-5">
        {issues.map((issue, n) => {
          const view = describeIssue(issue, policy)
          const text = describeOptionCount(issue) ?? view.text
          return (
            <li key={n}>
              {view.target ? (
                <button
                  type="button"
                  className="text-left underline-offset-2 hover:underline"
                  onClick={() => {
                    const el = document.getElementById(view.target!)
                    el?.scrollIntoView({ behavior: "smooth", block: "center" })
                    el?.classList.add("ring-2", "ring-destructive")
                    setTimeout(
                      () => el?.classList.remove("ring-2", "ring-destructive"),
                      2000,
                    )
                  }}
                >
                  {text}
                </button>
              ) : (
                text
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { useApi } from "@/lib/api/client"
import { readProblem, type LaneResult, type PolicyOut } from "@/lib/api/types"
import { MAX_SAMPLE_CHARS } from "./SamplesPanel"

const LANES = [
  { lane: "jev", name: "Jev with your guidelines" },
  { lane: "jev_labels", name: "Jev with buckets only" },
] as const

function Row({
  name,
  result,
  bucketName,
}: {
  name: string
  result: LaneResult | undefined
  bucketName: (key: string) => string
}) {
  const probs = Object.values(result?.probabilities ?? {})
  const sure = probs.length > 0 ? Math.max(...probs) : null
  return (
    <div className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1 rounded-lg border bg-card p-3 sm:grid-cols-[13rem_1fr_9rem]">
      <div className="flex items-center gap-2 text-sm font-medium">
        <span className="size-2 rounded-full bg-jev" />
        {name}
      </div>
      {result?.error || !result ? (
        <p className="col-span-2 text-sm text-destructive sm:col-span-2">
          {result?.error ?? "No answer"}
        </p>
      ) : (
        <>
          <div className="text-sm font-medium">
            {result.label ? bucketName(result.label) : "No answer"}
          </div>
          <div className="col-span-2 flex items-center gap-2 sm:col-span-1">
            {sure !== null && (
              <>
                <div
                  className="h-2 flex-1 overflow-hidden rounded-full bg-muted"
                  role="img"
                  aria-label={`How sure: ${Math.round(sure * 100)}%`}
                >
                  <div
                    className="h-full bg-jev"
                    style={{ width: `${Math.round(sure * 100)}%` }}
                  />
                </div>
                <span className="w-10 text-right text-xs text-muted-foreground">
                  {Math.round(sure * 100)}%
                </span>
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}

export function QuickCheck({
  projectId,
  policy,
  dirty,
}: {
  projectId: string
  // The saved policy: Quick check runs against it, not the unsaved draft.
  policy: PolicyOut
  dirty: boolean
}) {
  const api = useApi()
  const [text, setText] = useState("")
  const [results, setResults] = useState<LaneResult[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  const blocked =
    policy.policy.options.length < 2
      ? "Add at least 2 buckets, and save, to run a quick check."
      : policy.issues.length > 0
        ? "Fix the problems above and save to run a quick check."
        : null
  const names = new Map(policy.policy.options.map((o) => [o.key, o.name]))

  async function run() {
    setRunning(true)
    setError(null)
    const { data, error: err } = await api.POST(
      "/api/projects/{project_id}/try",
      { params: { path: { project_id: projectId } }, body: { text } },
    )
    setRunning(false)
    if (data) setResults(data.results)
    else setError(readProblem(err).message)
  }

  return (
    <section
      id="define-quick-check"
      className="space-y-3 rounded-lg border p-4"
    >
      <div>
        <h3 className="font-medium">Quick check</h3>
        <p className="text-sm text-muted-foreground">
          Checks whether your buckets make sense. This isn't your model.
        </p>
      </div>
      <Textarea
        rows={4}
        value={text}
        maxLength={MAX_SAMPLE_CHARS}
        placeholder="Paste an input, like a ticket or an email"
        aria-label="Input for the quick check"
        onChange={(e) => setText(e.target.value)}
      />
      <div className="flex flex-wrap items-center gap-3">
        <Button
          disabled={running || blocked !== null || !text.trim()}
          onClick={() => void run()}
        >
          {running ? "Checking…" : "Run quick check"}
        </Button>
        {blocked ? (
          <p className="text-sm text-muted-foreground">{blocked}</p>
        ) : (
          dirty && (
            <p className="text-sm text-muted-foreground">
              Uses your last saved buckets and guidelines.
            </p>
          )
        )}
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      {results && (
        <div className="space-y-2">
          {LANES.map(({ lane, name }) => (
            <Row
              key={lane}
              name={name}
              result={results.find((r) => r.lane === lane)}
              bucketName={(k) => names.get(k) ?? k}
            />
          ))}
        </div>
      )}
    </section>
  )
}

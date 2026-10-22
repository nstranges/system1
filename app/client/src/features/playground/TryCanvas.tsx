import { useEffect, useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { IssueList } from "@/features/rules/RulesCanvas"
import { NativeSelect } from "@/features/rules/fields"
import { useApi } from "@/lib/api/client"
import {
  readProblem,
  type PolicyOut,
  type Project,
  type Sample,
  type TryResult,
} from "@/lib/api/types"
import { ResultRow } from "./ResultRow"

// Mirrors the server's MAX_INPUT_CHARS so the message appears before sending.
const MAX_CHARS = 6000
const LANE_ORDER = ["jev_labels", "jev", "sys1"]

// Samples are ticket-shaped for the flagship; fall back to raw JSON otherwise.
function sampleText(s: Sample): string {
  const st = s.state
  if (st && typeof st === "object" && !Array.isArray(st)) {
    const ticket = (st as Record<string, unknown>).ticket as
      { subject?: string; body?: string } | undefined
    if (ticket && (ticket.subject || ticket.body)) {
      return [ticket.subject, ticket.body].filter(Boolean).join("\n\n")
    }
  }
  return typeof st === "string" ? st : JSON.stringify(st, null, 2)
}

export function TryCanvas({
  project,
  policy,
}: {
  project: Project
  policy: PolicyOut
}) {
  const api = useApi()
  const [text, setText] = useState("")
  const [samples, setSamples] = useState<Sample[]>([])
  const [sampleId, setSampleId] = useState("")
  const [result, setResult] = useState<TryResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  useEffect(() => {
    // Only flagship templates have samples; everything else answers 404, which
    // simply means there is nothing to pick from.
    void api
      .GET("/api/projects/{project_id}/samples", {
        params: { path: { project_id: project.id } },
      })
      .then(({ data }) => setSamples(data ?? []))
  }, [api, project.id])

  const hasIssues = policy.issues.length > 0
  const tooLong = text.length > MAX_CHARS
  const canTry = !hasIssues && !running && text.trim().length > 0 && !tooLong

  function pick(id: string) {
    setSampleId(id)
    setResult(null)
    const sample = samples.find((s) => s.id === id)
    if (sample) setText(sampleText(sample))
  }

  async function run() {
    setRunning(true)
    setError(null)
    const { data, error: err } = await api.POST(
      "/api/projects/{project_id}/try",
      {
        params: { path: { project_id: project.id } },
        body: sampleId ? { sample_id: sampleId } : { text },
      },
    )
    setRunning(false)
    if (!data) {
      const message = readProblem(err).message
      setError(message)
      toast.error(message)
      return
    }
    setResult(data)
  }

  const rows = result
    ? [...result.results].sort(
        (a, b) => LANE_ORDER.indexOf(a.lane) - LANE_ORDER.indexOf(b.lane),
      )
    : []
  const sys1Recorded = result?.recorded?.sys1

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold tracking-tight">Try it</h2>
          <p className="text-sm text-muted-foreground">
            Paste a real example and see how each one decides.
          </p>
        </div>
        {samples.length > 0 && (
          <div className="w-full sm:w-72">
            <NativeSelect
              aria-label="Sample from test set"
              value={sampleId}
              onChange={(e) => pick(e.target.value)}
            >
              <option value="">Sample from test set</option>
              {samples.map((s, i) => (
                <option key={s.id} value={s.id}>
                  {i + 1}. {sampleText(s).replace(/\s+/g, " ").slice(0, 60)}
                </option>
              ))}
            </NativeSelect>
          </div>
        )}
      </div>

      {hasIssues && <IssueList issues={policy.issues} />}

      <Textarea
        rows={6}
        value={text}
        aria-invalid={tooLong}
        placeholder="Paste a ticket, request or message here"
        onChange={(e) => {
          setText(e.target.value)
          // Editing a sample turns it into your own text.
          if (sampleId) setSampleId("")
        }}
      />
      <div className="flex items-center justify-between gap-3">
        <p
          className={
            tooLong
              ? "text-sm text-destructive"
              : "text-xs text-muted-foreground"
          }
        >
          {tooLong
            ? `That's too long. Keep it under ${MAX_CHARS.toLocaleString()} characters (it's ${text.length.toLocaleString()}).`
            : `${text.length.toLocaleString()} / ${MAX_CHARS.toLocaleString()} characters`}
        </p>
        <Button disabled={!canTry} onClick={() => void run()}>
          {running ? "Working…" : "Try"}
        </Button>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      {result && (
        <div className="space-y-3">
          {sys1Recorded !== undefined && (
            <p className="rounded-lg bg-jev/20 px-3 py-2 text-sm text-jev-foreground">
              Sample numbers. The real benchmark isn't in yet.
            </p>
          )}
          <div className="hidden grid-cols-[12rem_1fr_9rem_5rem] gap-x-4 px-3 text-xs text-muted-foreground sm:grid">
            <span />
            <span>Answer</span>
            <span>How sure</span>
            <span className="text-right">Time</span>
          </div>
          {rows.map((r) => (
            <ResultRow
              key={r.lane}
              result={r}
              gold={result.gold ?? null}
              recordedAnswer={r.lane === "sys1" ? sys1Recorded : undefined}
            />
          ))}
          {result.gold && (
            <p className="text-sm">
              <span className="text-muted-foreground">
                Correct by your rules:{" "}
              </span>
              <span className="font-mono font-medium">{result.gold}</span>
              {result.rule_id && (
                <span className="text-muted-foreground">
                  {" "}
                  ({result.rule_id})
                </span>
              )}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

import { Upload } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useApi } from "@/lib/api/client"
import { readProblem, type Policy } from "@/lib/api/types"
import type { components } from "@/lib/api/schema"
import { cn } from "@/lib/utils"

type Staged = components["schemas"]["Staged"]
type LabelCount = components["schemas"]["LabelCount"]
export type ImportResult = components["schemas"]["ImportResult"]

const MAX_BYTES = 5_000_000
const MAX_BUCKETS = 15
const NEW = "__new"
const DROP = "__drop"
const STEPS = [
  "Choose a file",
  "Input columns",
  "Decision column",
  "Match labels",
  "Import",
]

export function describeImport(r: ImportResult): string {
  const parts = [`Added ${r.added} examples.`]
  if (r.skipped_duplicates > 0)
    parts.push(`${r.skipped_duplicates} duplicates skipped.`)
  if (r.dropped_rows > 0) {
    const long = r.too_long > 0 ? ` (${r.too_long} were too long)` : ""
    parts.push(`${r.dropped_rows} rows dropped${long}.`)
  }
  return parts.join(" ")
}

export function UploadWizard({
  open,
  projectId,
  policy,
  onClose,
  onImported,
  onDone,
}: {
  open: boolean
  projectId: string
  policy: Policy
  onClose: () => void
  // Refresh the policy and counts: the import may have added buckets.
  onImported: () => Promise<void>
  onDone: (result: ImportResult) => void
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
        {open && (
          <Body
            projectId={projectId}
            policy={policy}
            onClose={onClose}
            onImported={onImported}
            onDone={onDone}
          />
        )}
      </DialogContent>
    </Dialog>
  )
}

function Body({
  projectId,
  policy,
  onClose,
  onImported,
  onDone,
}: {
  projectId: string
  policy: Policy
  onClose: () => void
  onImported: () => Promise<void>
  onDone: (result: ImportResult) => void
}) {
  const api = useApi()
  const input = useRef<HTMLInputElement>(null)
  const [step, setStep] = useState(0)
  const [staged, setStaged] = useState<Staged | null>(null)
  const [inputs, setInputs] = useState<string[]>([])
  const [decision, setDecision] = useState<string | null>(null)
  const [labels, setLabels] = useState<LabelCount[] | null>(null)
  const [choices, setChoices] = useState<Record<string, string>>({})
  const [result, setResult] = useState<ImportResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [over, setOver] = useState(false)
  const [error, setError] = useState<string | null>(null)
  // Closing at the result step (Esc, X) runs the same follow-up as Done.
  const finished = useRef<ImportResult | null>(null)
  const doneRef = useRef(onDone)
  useEffect(() => {
    doneRef.current = onDone
    finished.current = result
  })
  useEffect(
    () => () => {
      const r = finished.current
      if (r) {
        finished.current = null
        doneRef.current(r)
      }
    },
    [],
  )

  async function stage(file: File | undefined) {
    if (!file || busy) return
    setError(null)
    if (file.size > MAX_BYTES) {
      setError("That file is over 5 MB. Try a smaller one.")
      return
    }
    if (!/\.(csv|xlsx|jsonl)$/i.test(file.name)) {
      setError("Use a .csv, .xlsx or .jsonl file.")
      return
    }
    setBusy(true)
    try {
      const {
        data,
        error: err,
        response,
      } = await api.POST("/api/projects/{project_id}/uploads", {
        params: { path: { project_id: projectId } },
        // The typed body is a string placeholder; the serializer sends the file.
        body: { file: "" },
        bodySerializer: () => {
          const fd = new FormData()
          fd.append("file", file)
          return fd
        },
      })
      if (data) {
        setStaged(data)
        setInputs([])
        setDecision(null)
        setStep(1)
      } else {
        setError(
          response.status === 413
            ? "That file is too big. The limit is 5 MB and 5,000 rows."
            : readProblem(err).message,
        )
      }
    } catch {
      setError("We couldn't reach the server.")
    } finally {
      setBusy(false)
    }
  }

  async function loadLabels() {
    if (!staged || !decision || busy) return
    setBusy(true)
    setError(null)
    try {
      const { data, error: err } = await api.GET(
        "/api/projects/{project_id}/uploads/{upload_id}/labels",
        {
          params: {
            path: { project_id: projectId, upload_id: staged.upload_id },
            query: { column: decision },
          },
        },
      )
      if (!data) {
        setError(readProblem(err).message)
        return
      }
      const values = data.values
      setLabels(values)
      setChoices(
        Object.fromEntries(
          values.map((v) => {
            const hit = policy.options.find(
              (o) =>
                o.name.toLowerCase() === v.value.trim().toLowerCase() ||
                o.key.toLowerCase() === v.value.trim().toLowerCase(),
            )
            return [v.value, hit ? hit.key : NEW]
          }),
        ),
      )
      setStep(3)
    } catch {
      setError("We couldn't reach the server.")
    } finally {
      setBusy(false)
    }
  }

  async function runImport() {
    if (!staged || !decision || !labels || busy) return
    setBusy(true)
    setError(null)
    const createBuckets = labels.some((l) => choices[l.value] === NEW)
    const labelMap: Record<string, string | null> = {}
    for (const l of labels) {
      const c = choices[l.value]
      if (c === DROP) labelMap[l.value] = null
      else if (c !== NEW) labelMap[l.value] = c
    }
    try {
      const { data, error: err } = await api.POST(
        "/api/projects/{project_id}/uploads/{upload_id}/import",
        {
          params: {
            path: { project_id: projectId, upload_id: staged.upload_id },
          },
          body: {
            input_columns: inputs,
            label_column: decision,
            label_map: labelMap,
            create_buckets: createBuckets,
          },
        },
      )
      if (!data) {
        setError(readProblem(err).message)
        return
      }
      setResult(data)
      setStep(4)
      await onImported()
    } catch {
      setError("We couldn't reach the server.")
    } finally {
      setBusy(false)
    }
  }

  const newCount = labels
    ? labels.filter((l) => choices[l.value] === NEW).length
    : 0
  const tooMany = policy.options.length + newCount > MAX_BUCKETS
  const kept = labels
    ? labels.filter((l) => choices[l.value] !== DROP).length
    : 0

  const back = () => {
    setError(null)
    setStep((s) => Math.max(0, s - 1))
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Upload examples</DialogTitle>
        <DialogDescription>
          Step {step + 1} of {STEPS.length}: {STEPS[step]}
        </DialogDescription>
      </DialogHeader>

      {step === 0 && (
        <div
          onDragOver={(e) => {
            e.preventDefault()
            setOver(true)
          }}
          onDragLeave={() => setOver(false)}
          onDrop={(e) => {
            e.preventDefault()
            setOver(false)
            void stage(e.dataTransfer.files[0])
          }}
          className={cn(
            "flex flex-col items-center gap-2 rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground",
            over && "border-primary bg-primary/5",
          )}
        >
          <Upload className="size-5" />
          <p>Drop a spreadsheet of past decisions here, or</p>
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => input.current?.click()}
          >
            {busy ? "Reading your file…" : "Choose file"}
          </Button>
          <p className="text-xs">
            .csv, .xlsx or .jsonl. Up to 5 MB and 5,000 rows.
          </p>
          <input
            ref={input}
            type="file"
            accept=".csv,.xlsx,.jsonl"
            className="hidden"
            onChange={(e) => {
              void stage(e.target.files?.[0])
              e.target.value = ""
            }}
          />
        </div>
      )}

      {step === 1 && staged && (
        <div className="space-y-3">
          <p className="text-sm">
            Which columns describe the case? These are what the model reads.
            Found {staged.row_count} rows.
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {staged.columns.map((c) => (
              <label key={c} className="flex items-center gap-1.5 text-sm">
                <input
                  type="checkbox"
                  checked={inputs.includes(c)}
                  onChange={(e) =>
                    setInputs((cur) =>
                      e.target.checked
                        ? [...cur, c]
                        : cur.filter((x) => x !== c),
                    )
                  }
                />
                {c}
              </label>
            ))}
          </div>
          <Preview staged={staged} highlight={inputs} />
        </div>
      )}

      {step === 2 && staged && (
        <div className="space-y-3">
          <p className="text-sm">
            Which column holds the decision that was made?
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {staged.columns.map((c) => {
              const used = inputs.includes(c)
              return (
                <label
                  key={c}
                  className={cn(
                    "flex items-center gap-1.5 text-sm",
                    used && "text-muted-foreground",
                  )}
                >
                  <input
                    type="radio"
                    name="decision"
                    disabled={used}
                    checked={decision === c}
                    onChange={() => setDecision(c)}
                  />
                  {c}
                  {used && " (input)"}
                </label>
              )
            })}
          </div>
          <Preview staged={staged} highlight={decision ? [decision] : []} />
        </div>
      )}

      {step === 3 && labels && (
        <div className="space-y-3">
          <p className="text-sm">
            Match each decision in your file to a bucket.
          </p>
          <div className="space-y-2">
            {labels.map((l) => (
              <div key={l.value} className="flex items-center gap-3 text-sm">
                <span className="min-w-0 flex-1 truncate" title={l.value}>
                  {l.value || "(empty)"}
                  <span className="ml-2 text-xs text-muted-foreground">
                    {l.count} {l.count === 1 ? "row" : "rows"}
                  </span>
                </span>
                <select
                  aria-label={`Bucket for ${l.value}`}
                  className="h-8 max-w-[14rem] rounded-lg border border-input bg-background px-2 text-sm"
                  value={choices[l.value]}
                  onChange={(e) =>
                    setChoices((c) => ({ ...c, [l.value]: e.target.value }))
                  }
                >
                  {policy.options.map((o) => (
                    <option key={o.key} value={o.key}>
                      {o.name}
                    </option>
                  ))}
                  <option value={NEW}>New bucket</option>
                  <option value={DROP}>Don't import</option>
                </select>
              </div>
            ))}
          </div>
          <p className="text-sm text-muted-foreground">
            {newCount > 0
              ? `${newCount} new ${newCount === 1 ? "bucket" : "buckets"} will be created.`
              : "No new buckets will be created."}
          </p>
          {tooMany && (
            <p role="alert" className="text-sm text-destructive">
              That would make {policy.options.length + newCount} buckets. Keep
              it to {MAX_BUCKETS} or fewer by matching some to existing ones.
            </p>
          )}
        </div>
      )}

      {step === 4 && result && (
        <div className="space-y-2 text-sm" role="status">
          <p>{describeImport(result)}</p>
          {result.created_buckets.length > 0 && (
            <p className="text-muted-foreground">
              New buckets: {result.created_buckets.join(", ")}.
            </p>
          )}
        </div>
      )}

      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}

      <DialogFooter>
        {step === 4 ? (
          <Button onClick={onClose}>Done</Button>
        ) : (
          <>
            {step === 0 ? (
              <Button variant="ghost" onClick={onClose}>
                Cancel
              </Button>
            ) : (
              <Button variant="ghost" disabled={busy} onClick={back}>
                Back
              </Button>
            )}
            {step === 1 && (
              <Button
                disabled={inputs.length === 0}
                onClick={() => {
                  if (decision && inputs.includes(decision)) setDecision(null)
                  setError(null)
                  setStep(2)
                }}
              >
                Next
              </Button>
            )}
            {step === 2 && (
              <Button
                disabled={!decision || busy}
                onClick={() => void loadLabels()}
              >
                {busy ? "Reading…" : "Next"}
              </Button>
            )}
            {step === 3 && (
              <Button
                disabled={busy || tooMany || kept === 0}
                onClick={() => void runImport()}
              >
                {busy ? "Importing…" : "Import"}
              </Button>
            )}
          </>
        )}
      </DialogFooter>
    </>
  )
}

function Preview({
  staged,
  highlight,
}: {
  staged: Staged
  highlight: string[]
}) {
  return (
    <div className="max-h-64 overflow-auto rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            {staged.columns.map((c) => (
              <TableHead
                key={c}
                className={cn(highlight.includes(c) && "bg-primary/10")}
              >
                {c}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {staged.preview.slice(0, 20).map((row, i) => (
            <TableRow key={i}>
              {staged.columns.map((c) => (
                <TableCell
                  key={c}
                  className={cn(
                    "max-w-56 truncate",
                    highlight.includes(c) && "bg-primary/5",
                  )}
                  title={row[c]}
                >
                  {row[c]}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

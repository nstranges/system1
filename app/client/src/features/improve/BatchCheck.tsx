import { useRef, useState } from "react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { useApi } from "@/lib/api/client"
import { readProblem } from "@/lib/api/types"
import { JobProgress } from "@/features/data/JobProgress"

// Mirrors the server's BATCH_MAX_ROWS so the limit is stated up front.
const MAX_ROWS = 1000

interface BatchResult {
  batch_id: string
  answered: number
  unsure: number
  failed: number
  skipped: number
  top: { key: string; count: number }[]
}

// Runs the live model over a file of new messages at once, so the inbox fills without wiring up the endpoint.
export function BatchCheck({
  projectId,
  names,
  disabled,
  onDone,
}: {
  projectId: string
  names: Map<string, string>
  // Why it can't run yet, if it can't.
  disabled: string | null
  onDone: () => void
}) {
  const api = useApi()
  const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [result, setResult] = useState<BatchResult | null>(null)
  const [busy, setBusy] = useState(false)
  const name = (k: string) => names.get(k) ?? k

  async function start() {
    if (!file) return
    setBusy(true)
    setResult(null)
    try {
      const { data, error } = await api.POST(
        "/api/projects/{project_id}/batches",
        {
          params: { path: { project_id: projectId } },
          // The typed body is a string placeholder; the serializer sends the file.
          body: { file: "" },
          bodySerializer: () => {
            const fd = new FormData()
            fd.append("file", file)
            return fd
          },
        },
      )
      if (data) setJobId(data.job_id)
      else toast.error(readProblem(error).message)
    } catch {
      toast.error("We couldn't reach the server.")
    } finally {
      setBusy(false)
    }
  }

  async function finished() {
    const id = jobId
    setJobId(null)
    setFile(null)
    if (input.current) input.current.value = ""
    if (id) {
      const { data } = await api.GET("/api/jobs/{job_id}", {
        params: { path: { job_id: id } },
      })
      const r = data?.result as BatchResult | null | undefined
      if (data?.status === "failed")
        toast.error(data.message ?? "That batch didn't finish.")
      else if (r?.batch_id) setResult(r)
    }
    onDone()
  }

  async function download(batchId: string) {
    try {
      const { data } = await api.GET(
        "/api/projects/{project_id}/batches/{batch_id}/download",
        {
          params: { path: { project_id: projectId, batch_id: batchId } },
          parseAs: "blob",
        },
      )
      if (!data) return void toast.error("We couldn't download that batch.")
      const url = URL.createObjectURL(data as Blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `batch-${batchId.slice(0, 8)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error("We couldn't reach the server.")
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Check a batch</CardTitle>
        <CardDescription>
          Upload new messages, such as last week's tickets, and your live model
          answers them all at once. The ones it isn't sure about land in "To
          check" below. Up to {MAX_ROWS.toLocaleString()} rows; the text column
          is found by name, or the first column is used.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {jobId ? (
          <JobProgress jobId={jobId} onDone={() => void finished()} />
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            <input
              ref={input}
              type="file"
              accept=".csv,.tsv,.xlsx,.json,.jsonl"
              aria-label="File of messages to check"
              disabled={disabled !== null}
              className="max-w-full text-sm file:mr-3 file:rounded-md file:border file:bg-background file:px-3 file:py-1.5 file:text-sm"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <Button
              disabled={!file || busy || disabled !== null}
              onClick={() => void start()}
            >
              {busy ? "Uploading…" : "Check batch"}
            </Button>
          </div>
        )}
        {disabled && (
          <p className="text-sm text-muted-foreground">{disabled}</p>
        )}
        {result && (
          <div className="space-y-3 rounded-lg border p-3">
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <Stat label="Answered" value={result.answered} />
              <Stat label="Not sure" value={result.unsure} />
              <Stat
                label="Skipped"
                value={result.skipped + result.failed}
                note={
                  result.failed
                    ? `${result.failed} got no answer`
                    : "Empty or too long"
                }
              />
            </dl>
            {result.top.length > 0 && (
              <p className="text-sm">
                <span className="text-muted-foreground">Came up most: </span>
                {result.top
                  .map((t) => `${name(t.key)} (${t.count})`)
                  .join(", ")}
              </p>
            )}
            <Button
              size="sm"
              variant="outline"
              onClick={() => void download(result.batch_id)}
            >
              Download answers as CSV
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function Stat({
  label,
  value,
  note,
}: {
  label: string
  value: number
  note?: string
}) {
  return (
    <div>
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-lg font-semibold tabular-nums">
        {value.toLocaleString()}
      </dd>
      {note && <dd className="text-xs text-muted-foreground">{note}</dd>}
    </div>
  )
}

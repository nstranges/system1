import { FileText, Upload, X } from "lucide-react"
import { useCallback, useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Hint } from "@/components/Hint"
import { useApi } from "@/lib/api/client"
import { readProblem } from "@/lib/api/types"
import type { components } from "@/lib/api/schema"
import { cn } from "@/lib/utils"

export type ContextDoc = components["schemas"]["ContextDocOut"]

// The assistant's paperclip (in another part of the page) asks the Define
// step to open its context dialog through this event.
export const OPEN_CONTEXT_EVENT = "system1:open-context"
export function openContextDialog() {
  window.dispatchEvent(new Event(OPEN_CONTEXT_EVENT))
}

function size(chars: number) {
  return chars >= 1000
    ? `${(chars / 1000).toFixed(chars >= 10000 ? 0 : 1)}k characters`
    : `${chars} characters`
}

export function useContextDocs(projectId: string) {
  const api = useApi()
  const [docs, setDocs] = useState<ContextDoc[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    const { data, error: err } = await api.GET(
      "/api/projects/{project_id}/context",
      { params: { path: { project_id: projectId } } },
    )
    if (data) {
      setDocs(data)
      setError(null)
    } else {
      setError(readProblem(err).message)
    }
  }, [api, projectId])

  useEffect(() => {
    void reload()
  }, [reload])

  return { docs, error, reload }
}

// Drop zone, file picker and paste box. Server messages for limits (file too
// big, too many files, unsupported type) are shown as they come.
const MAX_FILES = 10
const MAX_BYTES = 2_000_000

function AddZone({
  projectId,
  existing,
  onAdded,
}: {
  projectId: string
  existing: number
  onAdded: () => Promise<void>
}) {
  const api = useApi()
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [note, setNote] = useState<string | null>(null)
  const [pasting, setPasting] = useState(false)
  const [name, setName] = useState("")
  const [text, setText] = useState("")

  async function upload(files: File[]) {
    if (files.length === 0) return
    setBusy(true)
    setError(null)
    setNote(null)
    let added = 0
    const failed: string[] = []
    let count = existing
    try {
      for (const file of files) {
        if (count >= MAX_FILES) {
          failed.push(
            `${file.name}: a project can hold up to ${MAX_FILES} context files`,
          )
          continue
        }
        if (file.size > MAX_BYTES) {
          failed.push(`${file.name}: over 2 MB, try a shorter one`)
          continue
        }
        const { error: err, response } = await api.POST(
          "/api/projects/{project_id}/context",
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
        if (response.ok) {
          added += 1
          count += 1
        } else {
          failed.push(
            `${file.name}: ${
              response.status === 413
                ? "over 2 MB, try a shorter one"
                : readProblem(err).message
            }`,
          )
        }
      }
    } catch {
      failed.push("We couldn't reach the server")
    } finally {
      setBusy(false)
    }
    if (failed.length > 0) {
      setError(
        files.length === 1
          ? failed[0]
          : `${added} added, ${failed.length} failed: ${failed.join("; ")}`,
      )
    } else if (files.length > 1) {
      setNote(`${added} added`)
    }
    await onAdded()
  }

  async function paste() {
    setBusy(true)
    setError(null)
    let result
    try {
      result = await api.POST("/api/projects/{project_id}/context/paste", {
        params: { path: { project_id: projectId } },
        body: { name: name.trim() || "Pasted text", text },
      })
    } catch {
      setError("We couldn't reach the server.")
      return
    } finally {
      setBusy(false)
    }
    const { response, error: err } = result
    if (!response.ok) {
      setError(readProblem(err).message)
      return
    }
    setName("")
    setText("")
    setPasting(false)
    await onAdded()
  }

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setOver(false)
          void upload(Array.from(e.dataTransfer.files))
        }}
        className={cn(
          "flex flex-col items-center gap-2 rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground",
          over && "border-primary bg-primary/5",
        )}
      >
        <Upload className="size-5" />
        <p>Drop a file here, or</p>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => input.current?.click()}
          >
            Choose file
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => setPasting((p) => !p)}
          >
            Paste text
          </Button>
        </div>
        <input
          ref={input}
          type="file"
          multiple
          hidden
          onChange={(e) => {
            const files = Array.from(e.target.files ?? [])
            e.target.value = ""
            void upload(files)
          }}
        />
      </div>
      {pasting && (
        <div className="space-y-2 rounded-lg border p-3">
          <Input
            placeholder="Name (optional)"
            value={name}
            maxLength={200}
            onChange={(e) => setName(e.target.value)}
          />
          <Textarea
            rows={6}
            placeholder="Paste your policy, guide or FAQ here"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => setPasting(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              disabled={busy || !text.trim()}
              onClick={() => void paste()}
            >
              Add text
            </Button>
          </div>
        </div>
      )}
      {busy && <p className="text-sm text-muted-foreground">Adding…</p>}
      {note && <p className="text-sm text-muted-foreground">{note}</p>}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}

export function ContextPanel({
  projectId,
  docs,
  loadError,
  reload,
  dialogOpen,
  onDialogOpen,
}: {
  projectId: string
  docs: ContextDoc[] | null
  loadError: string | null
  reload: () => Promise<void>
  dialogOpen: boolean
  onDialogOpen: (open: boolean) => void
}) {
  const api = useApi()
  const [removeError, setRemoveError] = useState<string | null>(null)

  // A file dropped outside the zone would make the browser navigate away and
  // lose unsaved edits.
  useEffect(() => {
    const stop = (e: DragEvent) => e.preventDefault()
    window.addEventListener("dragover", stop)
    window.addEventListener("drop", stop)
    return () => {
      window.removeEventListener("dragover", stop)
      window.removeEventListener("drop", stop)
    }
  }, [])

  async function remove(doc: ContextDoc) {
    setRemoveError(null)
    const { response, error } = await api.DELETE(
      "/api/projects/{project_id}/context/{doc_id}",
      { params: { path: { project_id: projectId, doc_id: doc.id } } },
    )
    if (!response.ok) {
      setRemoveError(readProblem(error).message)
      return
    }
    await reload()
  }

  return (
    <section id="define-context" className="space-y-3 rounded-lg">
      <div>
        <div className="flex items-center gap-2">
          <h3 className="font-medium">Context</h3>
          <Hint text="Policies, guides or FAQs. The assistant reads them to help." />
        </div>
        <p className="text-sm text-muted-foreground">
          Policies, guides or FAQs. The assistant reads them to help.
        </p>
      </div>
      <AddZone
        projectId={projectId}
        existing={docs?.length ?? 0}
        onAdded={reload}
      />
      {loadError && <p className="text-sm text-destructive">{loadError}</p>}
      {removeError && (
        <p role="alert" className="text-sm text-destructive">
          {removeError}
        </p>
      )}
      {docs && docs.length > 0 && (
        <ul className="divide-y rounded-lg border">
          {docs.map((d) => (
            <li key={d.id} className="flex items-center gap-3 p-2.5 text-sm">
              <FileText className="size-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0 flex-1 truncate">{d.name}</span>
              <span className="text-xs text-muted-foreground">
                {d.kind} · {size(d.chars)}
              </span>
              <Button
                size="icon"
                variant="ghost"
                aria-label={`Remove ${d.name}`}
                onClick={() => void remove(d)}
              >
                <X />
              </Button>
            </li>
          ))}
        </ul>
      )}
      <Dialog open={dialogOpen} onOpenChange={onDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add context</DialogTitle>
            <DialogDescription>
              Policies, guides or FAQs. The assistant reads them to help.
            </DialogDescription>
          </DialogHeader>
          <AddZone
            projectId={projectId}
            existing={docs?.length ?? 0}
            onAdded={reload}
          />
          {docs && docs.length > 0 && (
            <p className="text-sm text-muted-foreground">
              {docs.length} added so far.
            </p>
          )}
        </DialogContent>
      </Dialog>
    </section>
  )
}

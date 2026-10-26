import { useAuth } from "@clerk/react"
import { Trash2 } from "lucide-react"
import { useState } from "react"
import { Link } from "react-router"
import { toast } from "sonner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useApi } from "@/lib/api/client"
import { readProblem, type Project, type TrainedModel } from "@/lib/api/types"

const pct = (v: number | null | undefined) =>
  v == null ? "–" : `${Math.round(v * 100)}%`

// Trained models with the live one marked. An admin can make another one live, which changes what the
// project's endpoint answers with from the next call on.
export function ModelList({
  models,
  showProject,
  onChange,
}: {
  models: TrainedModel[]
  showProject: boolean
  onChange: (project: Project) => void
}) {
  const api = useApi()
  const { orgRole } = useAuth()
  const isAdmin = orgRole === "org:admin"
  const [busy, setBusy] = useState<string | null>(null)
  const [confirming, setConfirming] = useState<string | null>(null)
  const adminHint = isAdmin ? undefined : "Only an admin can change this."

  async function makeLive(id: string) {
    setBusy(id)
    try {
      const { data, error } = await api.POST("/api/models/{model_id}/live", {
        params: { path: { model_id: id } },
      })
      if (data) {
        onChange(data)
        toast("That model now answers your endpoint")
      } else {
        toast.error(readProblem(error).message)
      }
    } catch {
      toast.error("We couldn't reach the server.")
    } finally {
      setBusy(null)
    }
  }

  async function turnOff(id: string) {
    setBusy(id)
    try {
      const { data, error } = await api.DELETE("/api/models/{model_id}/live", {
        params: { path: { model_id: id } },
      })
      if (data) {
        onChange(data)
        toast("Your endpoint has no live model now")
      } else {
        toast.error(readProblem(error).message)
      }
    } catch {
      toast.error("We couldn't reach the server.")
    } finally {
      setBusy(null)
    }
  }

  async function remove(m: TrainedModel) {
    setBusy(m.id)
    try {
      const { data, error } = await api.DELETE("/api/models/{model_id}", {
        params: { path: { model_id: m.id } },
      })
      if (data) {
        onChange(data)
        toast("Model deleted")
      } else {
        toast.error(readProblem(error).message)
      }
    } catch {
      toast.error("We couldn't reach the server.")
    } finally {
      setBusy(null)
      setConfirming(null)
    }
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {showProject && <TableHead>Project</TableHead>}
          <TableHead>Trained</TableHead>
          <TableHead>Right answers</TableHead>
          <TableHead>Typical speed</TableHead>
          <TableHead className="text-right">Endpoint</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {models.map((m) => (
          <TableRow key={m.id}>
            {showProject && (
              <TableCell className="font-medium">
                <Link to={`/app/p/${m.project_id}/use`}>{m.project_name}</Link>
              </TableCell>
            )}
            <TableCell>
              {new Date(m.created_at).toLocaleString(undefined, {
                dateStyle: "medium",
                timeStyle: "short",
              })}
              <span className="block text-xs text-muted-foreground">
                <span className="capitalize">{m.size ?? "small"}</span>
                {" · "}
                <span className="font-mono">{m.id.slice(0, 8)}</span>
              </span>
            </TableCell>
            <TableCell>
              {pct(m.accuracy)}
              <span className="block text-xs text-muted-foreground">
                Jev {pct(m.jev_accuracy)}
                {m.test_examples != null && ` · ${m.test_examples} tests`}
              </span>
            </TableCell>
            <TableCell>
              {m.median_latency_ms != null
                ? `${Math.round(m.median_latency_ms)} ms`
                : "–"}
            </TableCell>
            <TableCell className="text-right">
              {confirming === m.id ? (
                <span className="inline-flex flex-wrap items-center justify-end gap-2 text-sm">
                  {m.live ? "Delete the live model?" : "Delete this model?"}
                  <Button
                    size="sm"
                    variant="destructive"
                    disabled={busy !== null}
                    onClick={() => void remove(m)}
                  >
                    Delete
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy !== null}
                    onClick={() => setConfirming(null)}
                  >
                    Keep
                  </Button>
                </span>
              ) : (
                <span className="inline-flex items-center justify-end gap-2">
                  {m.live ? (
                    <>
                      <Badge>Live</Badge>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={!isAdmin || busy !== null}
                        title={adminHint}
                        onClick={() => void turnOff(m.id)}
                      >
                        Turn off
                      </Button>
                    </>
                  ) : (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!isAdmin || busy !== null}
                      title={adminHint}
                      onClick={() => void makeLive(m.id)}
                    >
                      Make live
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label="Delete model"
                    disabled={!isAdmin || busy !== null}
                    title={adminHint}
                    onClick={() => setConfirming(m.id)}
                  >
                    <Trash2 />
                  </Button>
                </span>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

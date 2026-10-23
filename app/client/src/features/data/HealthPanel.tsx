import { Lock } from "lucide-react"
import { useCallback, useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { useApi } from "@/lib/api/client"
import type { Policy } from "@/lib/api/types"
import type { components } from "@/lib/api/schema"

export type Health = components["schemas"]["Health"]

// Mirrors the server's per-bucket minimum for training.
export const MIN_PER_BUCKET = 30

export const SOURCE_LABELS: Record<string, string> = {
  uploaded: "Uploaded",
  generated: "Generated",
  corrected: "Corrected",
}

export function useHealth(projectId: string) {
  const api = useApi()
  const [health, setHealth] = useState<Health | null>(null)
  const [failed, setFailed] = useState(false)

  const reload = useCallback(async (): Promise<Health | null> => {
    try {
      const { data } = await api.GET(
        "/api/projects/{project_id}/examples/health",
        { params: { path: { project_id: projectId } } },
      )
      if (data) {
        setHealth(data)
        setFailed(false)
        return data
      }
      setFailed(true)
    } catch {
      setFailed(true)
    }
    return null
  }, [api, projectId])

  useEffect(() => {
    void reload()
  }, [reload])

  return { health, failed, reload }
}

export function totalOf(health: Health | null, key: string): number {
  return health?.per_bucket[key]?.total ?? 0
}

export function exampleTotal(health: Health | null): number {
  return Object.values(health?.sources ?? {}).reduce((a, b) => a + b, 0)
}

export function HealthPanel({
  policy,
  health,
  failed,
}: {
  policy: Policy
  health: Health | null
  failed: boolean
}) {
  if (!health) {
    return (
      <p className="text-sm text-muted-foreground">
        {failed
          ? "We couldn't load your example counts."
          : "Loading your example counts…"}
      </p>
    )
  }
  if (exampleTotal(health) === 0) {
    return (
      <p className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
        No examples yet. Upload your past decisions or generate practice ones.
      </p>
    )
  }
  const splits = (["train", "cal", "test"] as const).map((s) => ({
    s,
    n: Object.values(health.per_bucket).reduce((a, b) => a + (b[s] ?? 0), 0),
  }))
  const rows = policy.options.map((o) => ({ key: o.key, name: o.name }))
  for (const k of Object.keys(health.per_bucket))
    if (!rows.some((r) => r.key === k)) rows.push({ key: k, name: k })

  return (
    <div className="space-y-3">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Bucket</TableHead>
            <TableHead className="text-right">Train</TableHead>
            <TableHead className="text-right">Calibrate</TableHead>
            <TableHead className="text-right">Test</TableHead>
            <TableHead className="text-right">Total</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => {
            const c = health.per_bucket[r.key]
            const total = c?.total ?? 0
            return (
              <TableRow key={r.key}>
                <TableCell className="font-medium">{r.name}</TableCell>
                <TableCell className="text-right">{c?.train ?? 0}</TableCell>
                <TableCell className="text-right">{c?.cal ?? 0}</TableCell>
                <TableCell className="text-right">{c?.test ?? 0}</TableCell>
                <TableCell className="text-right">{total}</TableCell>
                <TableCell>
                  {total < MIN_PER_BUCKET && (
                    <Badge variant="outline">
                      needs {MIN_PER_BUCKET - total} more
                    </Badge>
                  )}
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {Object.entries(health.sources)
          .filter(([, n]) => n > 0)
          .map(([k, n]) => (
            <Badge key={k} variant="secondary">
              {SOURCE_LABELS[k] ?? k}: {n}
            </Badge>
          ))}
        <span className="text-muted-foreground">
          {splits
            .map((x) => `${x.n} ${x.s === "cal" ? "calibrate" : x.s}`)
            .join(" · ")}
        </span>
      </div>
      {health.frozen && (
        <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <Lock className="size-3.5" /> Your test examples are locked.
        </p>
      )}
      {health.synthetic_test && (
        <p className="text-sm text-muted-foreground">
          Your test examples are all made up, so scores will look better than
          real life.
        </p>
      )}
    </div>
  )
}

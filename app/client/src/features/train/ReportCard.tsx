import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { components } from "@/lib/api/schema"
import { HeadToHead } from "./HeadToHead"

type Report = components["schemas"]["Report"]
type Row = components["schemas"]["ReportRow"]

const pct = (v: number) => `${Math.round(v * 100)}%`

function score(row: Row): string {
  if (row.status !== "ok" || row.accuracy == null) {
    if (row.status === "errored") return "Too many failed answers"
    return row.message ?? "Not available"
  }
  return pct(row.accuracy)
}

export function ReportCard({ report }: { report: Report }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Report card</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex flex-wrap gap-2 empty:hidden">
          {report.is_fixture && (
            <Badge variant="secondary">Recorded sample numbers</Badge>
          )}
          {report.details?.size && (
            <Badge variant="secondary" className="capitalize">
              {report.details?.size} model
            </Badge>
          )}
          {report.is_preview && (
            <Badge variant="secondary">Preview: no model was trained</Badge>
          )}
        </div>
        <HeadToHead report={report} />
        <details>
          <summary className="cursor-pointer text-sm text-muted-foreground hover:text-foreground">
            Show as a table
          </summary>
          <Table className="mt-3">
            <TableHeader>
              <TableRow>
                <TableHead>Model</TableHead>
                <TableHead>Right answers</TableHead>
                <TableHead>How sure of the right answer</TableHead>
                <TableHead className="text-right">Typical speed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(report.rows ?? []).map((row) => (
                <TableRow key={row.key}>
                  <TableCell className="font-medium">{row.label}</TableCell>
                  <TableCell>
                    {score(row)}
                    {row.status === "ok" && row.errors > 0 && (
                      <span className="block text-xs text-muted-foreground">
                        {row.message}
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    {row.avg_p_gold != null ? pct(row.avg_p_gold) : "–"}
                  </TableCell>
                  <TableCell className="text-right">
                    {row.median_latency_ms != null
                      ? `${Math.round(row.median_latency_ms)} ms`
                      : "–"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </details>
      </CardContent>
    </Card>
  )
}

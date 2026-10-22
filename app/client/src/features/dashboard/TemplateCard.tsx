import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import type { Template } from "@/lib/api/types"

const FIT: Record<
  string,
  { label: string; variant: "default" | "secondary" | "outline" }
> = {
  good: { label: "Good fit", variant: "default" },
  workable: { label: "Workable", variant: "secondary" },
  poor: { label: "Poor fit", variant: "outline" },
}

export function TemplateCard({
  template,
  busy,
  onUse,
}: {
  template: Template
  busy: boolean
  onUse: () => void
}) {
  const fit = FIT[template.fit] ?? FIT.workable
  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle>{template.name}</CardTitle>
          <Badge variant={fit.variant}>{fit.label}</Badge>
        </div>
        <CardDescription>{template.summary}</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="list-disc space-y-1 pl-4 text-sm text-muted-foreground">
          {template.fit_reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </CardContent>
      <CardFooter className="mt-auto">
        <Button variant="outline" disabled={busy} onClick={onUse}>
          Use this template
        </Button>
      </CardFooter>
    </Card>
  )
}

import { Link } from "react-router"
import { Button } from "@/components/ui/button"
import type { ProjectProgress } from "@/lib/api/types"
import { STAGES, nextAfter, stageHint, type StageId } from "./stages"

// Once a stage is finished, point at the next one so the journey hands off
// instead of leaving the person to find the rail.
export function NextStep({
  projectId,
  current,
  progress,
}: {
  projectId: string
  current: StageId
  progress: ProjectProgress | null
}) {
  const next = progress ? nextAfter(progress.stages, current) : null
  if (!next) return null
  const label = STAGES.find((s) => s.id === next)?.label ?? ""
  return (
    <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t pt-4">
      <p className="max-w-[60ch] text-muted-foreground">
        Next: {label}. {stageHint(next)}
      </p>
      <Button
        nativeButton={false}
        render={<Link to={`/app/p/${projectId}/${next}`} />}
      >
        Continue to {label}
      </Button>
    </div>
  )
}

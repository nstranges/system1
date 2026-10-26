import type { ProjectProgress } from "@/lib/api/types"
import { cn } from "@/lib/utils"
import { STAGES } from "@/features/workspace/stages"

// One segment per journey stage, so a project's whole state reads at a glance.
export function ProgressStrip({
  progress,
}: {
  progress: ProjectProgress | null
}) {
  const done = progress?.stages.filter((s) => s.status === "done").length ?? 0
  return (
    <div
      role="img"
      aria-label={`${done} of ${STAGES.length} steps done`}
      className="flex gap-1"
    >
      {STAGES.map((stage) => {
        const status = progress?.stages.find((s) => s.id === stage.id)?.status
        return (
          <span
            key={stage.id}
            className={cn(
              "h-1.5 flex-1 rounded-full",
              status === "done"
                ? "bg-model"
                : status === "ready"
                  ? "bg-model/25"
                  : "bg-muted",
            )}
          />
        )
      })}
    </div>
  )
}

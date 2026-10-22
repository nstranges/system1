import { Link } from "react-router"
import { cn } from "@/lib/utils"
import { STAGES, type StageId } from "./stages"

export function StageRail({
  projectId,
  current,
}: {
  projectId: string
  current: StageId
}) {
  return (
    <nav aria-label="Stages" className="overflow-x-auto">
      <ol className="flex min-w-max items-center gap-1">
        {STAGES.map((stage, i) => (
          <li key={stage.id}>
            <Link
              to={`/app/p/${projectId}/${stage.id}`}
              aria-current={stage.id === current ? "step" : undefined}
              className={cn(
                "flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-colors hover:bg-muted",
                stage.id === current
                  ? "bg-primary/10 font-medium text-primary"
                  : "text-muted-foreground",
              )}
            >
              <span
                className={cn(
                  "flex size-5 items-center justify-center rounded-full border text-xs",
                  stage.id === current && "border-primary",
                )}
              >
                {i + 1}
              </span>
              {stage.label}
            </Link>
          </li>
        ))}
      </ol>
    </nav>
  )
}

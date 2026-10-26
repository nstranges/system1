import { Check, Lock } from "lucide-react"
import { Link } from "react-router"
import type { ProjectProgress } from "@/lib/api/types"
import { cn } from "@/lib/utils"
import { STAGES, type StageId } from "./stages"

export function StageRail({
  projectId,
  current,
  progress,
}: {
  projectId: string
  current: StageId
  progress: ProjectProgress | null
}) {
  return (
    <nav aria-label="Stages">
      <ol className="flex gap-1 overflow-x-auto lg:flex-col lg:gap-0.5 lg:overflow-visible">
        {STAGES.map((stage, i) => {
          const state = progress?.stages.find((s) => s.id === stage.id)
          const status = state?.status
          const isCurrent = stage.id === current
          const spoken =
            status === "blocked" ? `blocked: ${state?.note}` : status
          return (
            <li key={stage.id} className="shrink-0">
              <Link
                to={`/app/p/${projectId}/${stage.id}`}
                aria-current={isCurrent ? "step" : undefined}
                aria-label={spoken ? `${stage.label}, ${spoken}` : undefined}
                className={cn(
                  "flex items-start gap-2.5 rounded-md px-2.5 py-1.5 transition-colors hover:bg-muted",
                  isCurrent && "bg-card ring-1 ring-border",
                )}
              >
                <StatusGlyph index={i} status={status} />
                <span className="min-w-0">
                  <span
                    className={cn(
                      "block text-[15px] font-medium",
                      status === "blocked" && "text-muted-foreground",
                    )}
                  >
                    {stage.label}
                  </span>
                  {state && (
                    <span
                      aria-hidden
                      className="hidden text-[13px] leading-snug text-muted-foreground lg:block"
                    >
                      {state.note}
                    </span>
                  )}
                </span>
              </Link>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

function StatusGlyph({
  index,
  status,
}: {
  index: number
  status: "done" | "ready" | "blocked" | undefined
}) {
  const base =
    "mt-px flex size-5 shrink-0 items-center justify-center rounded-full"
  if (status === "done")
    return (
      <span aria-hidden className={cn(base, "bg-model text-white")}>
        <Check className="size-3" strokeWidth={3} />
      </span>
    )
  if (status === "ready")
    return <span aria-hidden className={cn(base, "border-2 border-model")} />
  if (status === "blocked")
    return (
      <span aria-hidden className={cn(base, "bg-muted text-muted-foreground")}>
        <Lock className="size-3" />
      </span>
    )
  return (
    <span
      aria-hidden
      className={cn(base, "border text-[13px] text-muted-foreground")}
    >
      {index + 1}
    </span>
  )
}

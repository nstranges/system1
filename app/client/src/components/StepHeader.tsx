import type { ReactNode } from "react"
import { Hint } from "@/components/Hint"

export function StepHeader({
  title,
  hint,
  children,
}: {
  title: string
  hint: string
  children?: ReactNode
}) {
  return (
    <header className="space-y-1">
      <div className="flex items-center gap-2">
        <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
        <Hint text={hint} />
      </div>
      <p className="text-sm text-muted-foreground">{hint}</p>
      {children}
    </header>
  )
}

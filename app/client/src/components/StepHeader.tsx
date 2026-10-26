import type { ReactNode } from "react"

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
      <h2 className="text-[28px] leading-tight font-semibold tracking-[-0.015em]">
        {title}
      </h2>
      <p className="text-muted-foreground">{hint}</p>
      {children}
    </header>
  )
}

import type { ComponentProps } from "react"
import { cn } from "@/lib/utils"

// Native select: the label lists are long and change as options are edited,
// and a native control keeps keyboard and mobile behaviour for free.
export function NativeSelect({
  className,
  ...props
}: ComponentProps<"select">) {
  return (
    <select
      className={cn(
        "h-9 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50",
        className,
      )}
      {...props}
    />
  )
}

export function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <span className="mb-1 block text-xs font-medium text-muted-foreground">
      {children}
    </span>
  )
}

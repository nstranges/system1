import { bucketVar } from "@/lib/buckets"
import { cn } from "@/lib/utils"

export function BucketSwatch({ index }: { index: number }) {
  return (
    <span
      aria-hidden
      className={cn(
        "size-2.5 shrink-0 rounded-[3px]",
        bucketVar(index) === null && "opacity-40",
      )}
      style={{ background: bucketVar(index) ?? "var(--muted-foreground)" }}
    />
  )
}

export function BucketChip({
  name,
  index,
  className,
}: {
  name: string
  index: number
  className?: string
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border bg-card px-2 py-0.5 text-sm text-foreground",
        className,
      )}
    >
      <BucketSwatch index={index} />
      {name}
    </span>
  )
}

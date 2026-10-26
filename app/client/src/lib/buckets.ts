// Slot order is the validated categorical palette order. A ninth hue is never generated:
// buckets past the eighth get a neutral swatch instead.
export function bucketVar(index: number): string | null {
  return Number.isInteger(index) && index >= 0 && index < 8
    ? `var(--bucket-${index + 1})`
    : null
}

export function bucketIndex(options: { key: string }[], key: string): number {
  return options.findIndex((o) => o.key === key)
}

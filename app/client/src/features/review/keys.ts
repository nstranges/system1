export type ReviewAction =
  | { kind: "agree" }
  // Index into the project's buckets.
  | { kind: "move"; index: number }
  | { kind: "next" }
  | { kind: "prev" }

export function reviewKey(
  key: string,
  bucketCount: number,
): ReviewAction | null {
  if (key === "Enter" || key === "y" || key === "Y") return { kind: "agree" }
  if (/^[1-9]$/.test(key)) {
    const index = Number(key) - 1
    return index < bucketCount ? { kind: "move", index } : null
  }
  if (key === "j" || key === "ArrowDown") return { kind: "next" }
  if (key === "k" || key === "ArrowUp") return { kind: "prev" }
  return null
}

// Keys typed into a field belong to the field (the assistant's composer, a search box).
export function isTypingTarget(
  el: { tagName?: string; isContentEditable?: boolean } | null,
): boolean {
  if (!el) return false
  return (
    el.tagName === "INPUT" ||
    el.tagName === "TEXTAREA" ||
    el.tagName === "SELECT" ||
    el.isContentEditable === true
  )
}

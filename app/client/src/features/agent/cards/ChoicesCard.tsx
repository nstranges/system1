import { Button } from "@/components/ui/button"

export function ChoicesCard({
  question,
  options,
  active,
  onPick,
}: {
  question: string
  options: string[]
  // Only the latest unanswered set can be clicked.
  active: boolean
  onPick: (text: string) => void
}) {
  return (
    <div className="space-y-2">
      <p className="text-sm">{question}</p>
      <div className="flex flex-wrap gap-2">
        {options.map((o) => (
          <Button
            key={o}
            size="sm"
            variant="outline"
            disabled={!active}
            className="h-auto whitespace-normal py-1.5 text-left"
            onClick={() => onPick(o)}
          >
            {o}
          </Button>
        ))}
      </div>
    </div>
  )
}

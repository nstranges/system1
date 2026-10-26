import { useEffect, useState } from "react"
import { BucketChip } from "@/components/BucketChip"
import { cn } from "@/lib/utils"

// Tallyfern's test ticket t0005 and the recorded answers for it. Tallyfern's
// first bucket is Trust & Safety, so it takes the first bucket colour.
const TICKET = {
  subject: "Someone logged into our account!!",
  body: "We just got an alert that someone signed in to our Tallyfern account from a country none of us have ever been to, and now there are two invoices in drafts that NOBODY here created.",
}

const ANSWERS = [
  { lane: "Your model", sure: 85, bar: "bg-model" },
  { lane: "Jev + your guidelines", sure: 70, bar: "bg-jev" },
]

const reducedMotion = () =>
  typeof window !== "undefined" &&
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches

// The page's one load moment: the ticket settles, then each answer's bar fills.
// With reduced motion everything starts in its final state.
export function DecisionDemo() {
  const [filled, setFilled] = useState(reducedMotion)
  useEffect(() => {
    const timer = setTimeout(() => setFilled(true), 450)
    return () => clearTimeout(timer)
  }, [])

  return (
    <figure className="space-y-4">
      <div className="rounded-[10px] border bg-card p-5 duration-[400ms] motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2">
        <p className="font-medium">{TICKET.subject}</p>
        <p className="font-voice mt-2">{TICKET.body}</p>
      </div>
      <ul className="space-y-2">
        {ANSWERS.map((a, i) => (
          <li
            key={a.lane}
            className="flex flex-wrap items-center gap-x-3 gap-y-1"
          >
            <span className="basis-full text-sm font-medium sm:w-44 sm:basis-auto">
              {a.lane}
            </span>
            <BucketChip name="Trust & Safety" index={0} />
            <span
              role="img"
              aria-label={`${a.sure}% sure`}
              className="h-1.5 w-24 rounded-full bg-muted"
            >
              <span
                className={cn(
                  "block h-full rounded-full motion-safe:transition-[width] motion-safe:duration-700 motion-safe:ease-out",
                  a.bar,
                )}
                style={{
                  width: filled ? `${a.sure}%` : 0,
                  transitionDelay: `${i * 150}ms`,
                }}
              />
            </span>
            <span className="text-sm tabular-nums">{a.sure}% sure</span>
          </li>
        ))}
      </ul>
      <figcaption className="text-[13px] text-muted-foreground">
        Sample numbers from the Tallyfern example project.
      </figcaption>
    </figure>
  )
}

import { Show } from "@clerk/react"
import { Navigate, Link } from "react-router"
import { Button } from "@/components/ui/button"
import { STAGES } from "@/features/workspace/stages"
import { DecisionDemo } from "./DecisionDemo"

function LandingContent() {
  return (
    <div className="min-h-svh bg-background">
      <header className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
        <span className="text-lg font-semibold tracking-tight">
          system<span className="text-primary">1</span>
        </span>
        <Button
          variant="ghost"
          nativeButton={false}
          render={<Link to="/sign-in" />}
        >
          Sign in
        </Button>
      </header>

      <main className="mx-auto max-w-6xl px-4">
        <section className="grid items-center gap-12 py-16 sm:py-24 lg:grid-cols-[1.1fr_1fr]">
          <div>
            <h1 className="max-w-[18ch] text-[32px] leading-[1.1] font-semibold tracking-[-0.02em] text-balance sm:text-[40px]">
              Decisions made the way your team makes them.
            </h1>
            <p className="mt-6 max-w-[60ch] text-lg text-muted-foreground">
              Your team makes the same call hundreds of times a week: which
              queue a ticket goes to, whether a refund gets approved. system1
              turns that call into written guidelines and a small model trained
              on your own decisions, behind the same API as Jev.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button
                size="lg"
                nativeButton={false}
                render={<Link to="/sign-up" />}
              >
                Sign up
              </Button>
              <Button
                size="lg"
                variant="outline"
                nativeButton={false}
                render={<Link to="/sign-in" />}
              >
                Sign in
              </Button>
            </div>
          </div>
          <DecisionDemo />
        </section>

        <section className="pb-24">
          <h2 className="mb-6 text-[22px] font-semibold tracking-[-0.01em]">
            How it works
          </h2>
          <ol className="grid gap-6 sm:grid-cols-2 lg:grid-cols-6">
            {STAGES.map((stage, i) => (
              <li key={stage.id}>
                <span className="flex size-6 items-center justify-center rounded-full border-2 border-model text-[13px] font-medium tabular-nums">
                  {i + 1}
                </span>
                <h3 className="mt-3 font-medium">{stage.label}</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  {stage.hint}
                </p>
              </li>
            ))}
          </ol>
        </section>
      </main>

      <footer className="mx-auto max-w-6xl px-4 pb-10 text-[13px] text-muted-foreground">
        Built for Build North 2026 by Thomas Michalski and Nicholas Stranges.
      </footer>
    </div>
  )
}

export function LandingPage() {
  return (
    <>
      <Show when="signed-in">
        <Navigate to="/app" replace />
      </Show>
      <Show when="signed-out">
        <LandingContent />
      </Show>
    </>
  )
}

import { Show } from "@clerk/react"
import { Navigate, Link } from "react-router"
import { Button } from "@/components/ui/button"

const steps = [
  {
    title: "Write your rules",
    body: "Tell the agent how your team makes the call. It turns your words into clear, editable rules.",
  },
  {
    title: "Try it",
    body: "Paste a real ticket and see the decision right away, powered by Jev with your rules attached.",
  },
  {
    title: "Get your model",
    body: "We make labelled examples from your rules and train a small model that learns how your team decides.",
  },
  {
    title: "Improve it",
    body: "Correct any decision. Your corrections feed the next version of your model.",
  },
]

function LandingContent() {
  return (
    <div className="min-h-svh bg-background">
      <header className="mx-auto flex h-16 max-w-5xl items-center justify-between px-4">
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

      <main className="mx-auto max-w-5xl px-4">
        <section className="py-16 sm:py-24">
          <p className="mb-4 text-sm font-medium text-primary">
            For support-ops leads
          </p>
          <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
            Jev knows decisions.{" "}
            <span className="text-primary">
              Your model knows your decisions.
            </span>
          </h1>
          <p className="mt-6 max-w-2xl text-lg text-muted-foreground">
            Your team makes the same call hundreds of times a week: which queue
            a ticket goes to, whether a refund gets approved. Describe the
            decision once. system1 gives you written rules, a working decision
            endpoint in minutes, and a model of your own that keeps getting
            better from your corrections.
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
        </section>

        <section className="pb-24">
          <h2 className="mb-6 text-sm font-medium text-muted-foreground">
            How it works
          </h2>
          <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {steps.map((step, i) => (
              <li key={step.title} className="rounded-xl border p-5">
                <span className="text-sm font-medium text-primary">
                  {i + 1}
                </span>
                <h3 className="mt-2 font-medium">{step.title}</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  {step.body}
                </p>
              </li>
            ))}
          </ol>
        </section>
      </main>
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

import { expect, test } from "bun:test"
import { nextAfter } from "./stages"

const s = (...statuses: ("done" | "ready" | "blocked")[]) =>
  (["define", "data", "review", "train", "use", "improve"] as const).map(
    (id, i) => ({ id, status: statuses[i] }),
  )

test("a done stage hands off to the next open one", () => {
  expect(
    nextAfter(
      s("done", "ready", "blocked", "blocked", "ready", "blocked"),
      "define",
    ),
  ).toBe("data")
})
test("skips blocked stages", () => {
  expect(
    nextAfter(
      s("done", "done", "done", "blocked", "ready", "blocked"),
      "review",
    ),
  ).toBe("use")
})
test("nothing while the current stage isn't done", () => {
  expect(
    nextAfter(
      s("ready", "blocked", "blocked", "blocked", "blocked", "blocked"),
      "define",
    ),
  ).toBeNull()
})
test("nothing after the last stage", () => {
  expect(
    nextAfter(s("done", "done", "done", "done", "done", "ready"), "improve"),
  ).toBeNull()
})

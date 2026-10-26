import { expect, test } from "bun:test"
import { isTypingTarget, reviewKey } from "./keys"

test("digits pick a bucket by position", () => {
  expect(reviewKey("1", 4)).toEqual({ kind: "move", index: 0 })
  expect(reviewKey("4", 4)).toEqual({ kind: "move", index: 3 })
  expect(reviewKey("5", 4)).toBeNull()
  expect(reviewKey("0", 4)).toBeNull()
})
test("enter and y keep the label", () => {
  expect(reviewKey("Enter", 3)).toEqual({ kind: "agree" })
  expect(reviewKey("y", 3)).toEqual({ kind: "agree" })
  expect(reviewKey("Y", 3)).toEqual({ kind: "agree" })
})
test("j/k and arrows move between cards", () => {
  expect(reviewKey("j", 3)).toEqual({ kind: "next" })
  expect(reviewKey("ArrowDown", 3)).toEqual({ kind: "next" })
  expect(reviewKey("k", 3)).toEqual({ kind: "prev" })
  expect(reviewKey("ArrowUp", 3)).toEqual({ kind: "prev" })
})
test("anything else is not a shortcut", () => {
  expect(reviewKey("a", 3)).toBeNull()
  expect(reviewKey(" ", 3)).toBeNull()
})
test("typing in a field is never a shortcut", () => {
  expect(isTypingTarget({ tagName: "TEXTAREA" })).toBe(true)
  expect(isTypingTarget({ tagName: "INPUT" })).toBe(true)
  expect(isTypingTarget({ tagName: "SELECT" })).toBe(true)
  expect(isTypingTarget({ tagName: "DIV", isContentEditable: true })).toBe(true)
  expect(isTypingTarget({ tagName: "BUTTON" })).toBe(false)
  expect(isTypingTarget(null)).toBe(false)
})

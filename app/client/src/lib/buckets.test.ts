import { describe, expect, test } from "bun:test"
import { bucketIndex, bucketVar } from "./buckets"

describe("bucketVar", () => {
  test("first eight slots map to tokens in order", () => {
    expect(bucketVar(0)).toBe("var(--bucket-1)")
    expect(bucketVar(7)).toBe("var(--bucket-8)")
  })
  test("no hue past the eighth bucket or for unknown ones", () => {
    expect(bucketVar(8)).toBeNull()
    expect(bucketVar(14)).toBeNull()
    expect(bucketVar(-1)).toBeNull()
  })
})

test("bucketIndex finds a key by position", () => {
  const options = [{ key: "a" }, { key: "b" }]
  expect(bucketIndex(options, "b")).toBe(1)
  expect(bucketIndex(options, "z")).toBe(-1)
})

# UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give system1 its own look (bucket colours, a serif for the customer's voice), a journey that shows progress and hands off from step to step, and a Train verdict that reads at a glance.

**Architecture:** One new server endpoint (`GET /api/projects/{id}/progress`) computes each stage's status from data the server already has. The client reads it in the stage rail, the next-step footer and the dashboard cards. Everything else is client-only: design tokens in `index.css`, a `BucketChip` used wherever a bucket appears, a head-to-head chart on Train, keyboard Review, and a new landing page. Pure logic lives in small `.ts` files tested with `bun test`, which needs no new dependency.

**Tech Stack:** FastAPI, SQLAlchemy and pytest (server, `uv`). React 19, Tailwind 4, shadcn/base-ui, lucide-react and next-themes (client, `bun`).

**Spec:** [docs/superpowers/specs/2026-10-25-ui-redesign-design.md](../specs/2026-10-25-ui-redesign-design.md)

## Global Constraints

- **Deadline and tiers:** the submission deadline is Oct 25, 23:59 ET.
  - **Tier 1** (Tasks 1–7) is the demo path, and stops at **Gate A**, where Thomas checks it in the browser.
  - **Tier 2** (Tasks 8–10) stops at **Gate B**.
  - **Tier 3** (Task 11) is optional.
  - Cut from the end, never from the middle of a task.
- **Words on screen:**
  - Always "how sure", never "confidence" or "probability".
  - Always "buckets", "guidelines", "examples" and "what comes in".
  - Sentence case throughout.
- **Typography bans:** no all-caps labels, no eyebrow labels, no monospace small labels, no middle-dot meta strings, no "→" on buttons, and no single accented word in a headline.
- **Bucket colours:** slots 1–8 come from the spec's table, in that order. Buckets 9+ get a neutral swatch. A bucket's name always sits next to its swatch, in ink, never in the bucket's colour.
- **Motion:** only the two orchestrated moments (landing load, report bars), both under `motion-safe:`. Everything else moves only in response to an action.
- **Toolchain:**
  - `bun add` / `bun remove` on the client and `uv` on the server.
  - Run `make docs` after the API change, and never hand-edit `openapi.json` or `schema.d.ts`.
  - Run `make format` before every commit (agent edits don't format on save).
- **Commits:**
  - On `ui-redesign` only.
  - `type(scope): description`, imperative and lowercase, 72 characters or less, with the why in the body.
  - No Claude attribution lines.
- **Library behaviour:** check the installed source or types for base-ui, next-themes and Tailwind 4 rather than memory, before using an API not already used in this repo.
- **Comments** explain intent and trade-offs only, and never reference tasks or plan steps.

## Review Focus

1. **A project with no policy options and no examples:** every stage gets a status, the rail renders without a crash, and the next step is `define`. *(Test: Task 2, `test_blank_project_progress`.)*
2. **The flagship template, which has fixture results and no review queue:** Review and Train are done, and the note says "Labelled by exact rules". *(Test: Task 2, `test_flagship_progress`.)*
3. **A preview training run** must not read as a trained model. The Train note is "Preview run, no model yet", and accuracy is `null`. *(Test: Task 2, `test_preview_training_is_not_a_model`.)*
4. **More than eight buckets** (the flagship has 13): buckets 9+ render a neutral swatch, and no hue is generated. *(Test: Task 1, `bucketVar(8) === null`.)*
5. **Review keys pressed while typing** in an input or textarea (the assistant's composer) must not sort cards. *(Test: Task 8, `isTypingTarget` cases.)*

---

### Task 1: Design tokens, fonts, bucket colours and the client test runner

**Files:**
- Modify: `app/client/src/index.css` (`@theme inline` and `:root` / `.dark` blocks)
- Modify: `app/client/package.json` (via `bun add` / `bun remove`)
- Create: `app/client/src/lib/buckets.ts`
- Create: `app/client/src/lib/buckets.test.ts`
- Create: `app/client/src/components/BucketChip.tsx`
- Modify: `app/Makefile` (the `test` target)

**Interfaces:**
- Produces:
  - `bucketVar(index: number): string | null`. It returns `"var(--bucket-1)"` through `"var(--bucket-8)"` for indexes 0–7, and `null` otherwise, including negative indexes.
  - `bucketIndex(options: { key: string }[], key: string): number`, which returns `-1` when the key isn't found.
  - `BucketSwatch({ index }: { index: number })`
  - `BucketChip({ name, index, className }: { name: string; index: number; className?: string })`
  - CSS tokens `--paper`, `--ink`, `--muted-ink`, `--rule`, `--model`, `--jev`, `--bucket-1…8`.
  - Tailwind colours `model`, `jev`, `bucket-1…8`.
  - The font utility `font-voice`.

- [ ] **Step 1: Write the failing test** `app/client/src/lib/buckets.test.ts`

```ts
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
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `cd app/client && bun test src/lib/buckets.test.ts`
Expected: FAIL (cannot find module `./buckets`).

- [ ] **Step 3: Implement `bucketVar` and `bucketIndex`** in `app/client/src/lib/buckets.ts`. Add a one-line comment saying slot order is the validated categorical order, and that a ninth hue is never generated.

- [ ] **Step 4: Run it to make sure it passes**

Run: `cd app/client && bun test src/lib/buckets.test.ts`
Expected: 3 pass.

- [ ] **Step 5: Swap the fonts**

Run:
- `cd app/client && bun add @fontsource-variable/instrument-sans @fontsource-variable/newsreader`
- `bun remove @fontsource-variable/geist`

If either package name doesn't resolve, use the non-variable `@fontsource/instrument-sans` or `@fontsource/newsreader` with weights 400, 500 and 600 instead, and say so in the commit body.

- [ ] **Step 6: Rewrite the tokens in `index.css`**

1. Replace the Geist import with the two new font imports.
2. In `@theme inline`, add these:
   - `--font-sans: "Instrument Sans Variable", ui-sans-serif, sans-serif`
   - `--font-voice: "Newsreader Variable", Georgia, serif`
   - `--color-model: var(--model)`
   - `--color-bucket-1` through `--color-bucket-8`
3. Remove `--color-series-1/2`, and keep `--color-jev`. Run `grep -rn "series-" src` and replace each use with `model` (series-1) or `jev` (series-2).
4. In `:root`, set the values from the spec's colour table:
   - `--background: var(--paper)`, `--foreground: var(--ink)` and `--muted-foreground: var(--muted-ink)`
   - `--border` and `--input` set to `var(--rule)`
   - `--primary: #1C5CAB` with `--primary-foreground: #FFFFFF`
   - `--ring: #2A78D6`
   - `--jev-foreground: var(--ink)`
   - `--radius: 0.625rem` (unchanged)
   - the light bucket hexes
   - `--secondary`, `--muted` and `--accent` set to `#E7EBE9`
5. In `.dark`, set the dark column the same way: `--primary: #5598E7` with `--primary-foreground: #0D1A2B`, and `--secondary`, `--muted` and `--accent` set to `#262D34`.
6. In `@layer base`, give `body` the classes `text-[15px] antialiased`.
7. Add `.font-voice { font-size: 15px; line-height: 1.6; }` under `@layer components`, so the serif sits at its intended size wherever it's used.

- [ ] **Step 7: Build `BucketChip.tsx`**

- `BucketSwatch` is a `span` with `aria-hidden`, `size-2.5 shrink-0 rounded-[3px]`, and a background of `bucketVar(index) ?? "var(--muted-foreground)"`. Buckets past slot 8 also get `opacity-40`.
- `BucketChip` is `inline-flex items-center gap-1.5 rounded-md border bg-card px-2 py-0.5 text-sm text-foreground` around the swatch and the name.

- [ ] **Step 8: Run client tests from `make test`**

In `app/Makefile`'s `test` target, after pytest, add:

```
@if [ -d client/node_modules ]; then cd client && bun test; else echo "skip: client not installed"; fi
```

- [ ] **Step 9: Verify**

Run: `make -C app check && make -C app test`
Expected: ruff clean, `tsc` clean, pytest passes, and `bun test` reports 3 passing.

- [ ] **Step 10: Commit**

```bash
make format
git add app/client/src/index.css app/client/package.json app/client/bun.lock app/client/src/lib/buckets.ts app/client/src/lib/buckets.test.ts app/client/src/components/BucketChip.tsx app/Makefile
git commit -m "feat(client): give buckets fixed colours and set the new type and palette"
```

---

### Task 2: Project progress endpoint

**Files:**
- Create: `app/server/src/system1/progress/__init__.py` (empty)
- Create: `app/server/src/system1/progress/schemas.py`
- Create: `app/server/src/system1/progress/service.py`
- Create: `app/server/src/system1/progress/router.py`
- Modify: `app/server/src/system1/main.py` (`api.include_router(progress_router)` beside the others)
- Create: `app/server/tests/test_progress.py`
- Regenerate: `app/client/src/lib/api/openapi.json` and `schema.d.ts` (via `make docs`)
- Modify: `app/client/src/lib/api/types.ts` (add `export type ProjectProgress = components["schemas"]["ProjectProgress"]` and `export type StageState = components["schemas"]["StageState"]`)

It's a separate package, so it can import the datasets, report and gateway services without a cycle through `projects`.

**Interfaces:**
- Consumes:
  - `project_service.get_project(session, principal, project_id)`
  - `project_service.latest_policy(session, project) -> (Policy, int)`
  - `validate_policy(policy) -> list[PolicyIssue]`
  - `dataset_service.health(session, project) -> Health`
  - `dataset_service.review_queue(session, project) -> list[Example]`
  - `report_service.report(session, project) -> Report`
  - `keys.list_keys(session, project) -> list[ApiKey]`
  - `REVIEW_CARDS` (30) from `datasets.constants`
  - `FLAGSHIP = "tallyfern-triage"`
- Produces:

```python
StageId = Literal["define", "data", "review", "train", "use", "improve"]

class StageState(BaseModel):
    id: StageId
    status: Literal["done", "ready", "blocked"]
    note: str

class ProjectProgress(BaseModel):
    stages: list[StageState]          # always six, in journey order
    next: StageId | None              # first stage whose status is "ready"
    examples: int
    accuracy: float | None            # the "sys1" report row's accuracy, 0..1
    jev_accuracy: float | None        # the "jev" report row's accuracy, 0..1
```

The service is `progress(session: Session, project: Project) -> ProjectProgress`, and the route is `GET /api/projects/{project_id}/progress -> ProjectProgress`. The route resolves the project with `get_project` first, so another org's project is a 404.

**Rules, in order.** "total" is the sum of `health.per_bucket[*]["total"]`, and "short" is `len(health.below_minimum)`.

| Stage | Status and note |
|---|---|
| define | `done` with `f"{n} buckets"` if there are 2 or more options and `validate_policy` finds no issues. Otherwise `ready`: with fewer than 2 options the note is `"Add at least two buckets"`, and with issues it's `"Fix the problems in your buckets"`. |
| data | `blocked`, `"Define your buckets first"`, if define isn't done. `done`, `f"{total} examples"`, if total > 0 and short == 0. Otherwise `ready`: `"No examples yet"` when total == 0, else `"1 bucket needs more examples"` or `f"{short} buckets need more examples"`. |
| review | For the flagship: `done`, `"Labelled by exact rules"`. `blocked`, `"Add examples first"`, if total == 0. With q = len(review_queue): `done`, `"Nothing left to check"`, if q == 0. Otherwise `ready`, with `f"{q}+ to check"` if q == REVIEW_CARDS, else `f"{q} to check"`. |
| train | If `report.available`: when the sys1 row's accuracy isn't None, `done` with `f"Your model: {round(acc*100)}%"`; otherwise `done` with `"Preview run, no model yet"`. If the report isn't available: `blocked`, `"Needs 30 examples per bucket"`, when total == 0 or short > 0, and otherwise `ready`, `"Ready to train"`. |
| use | `blocked`, `"Define your buckets first"`, if define isn't done. `done`, `"Connected"`, if any key exists. Otherwise `ready`, `"Try it, then get a key"`. |
| improve | `blocked`, `"Needs a live model"`, if `project.live_model_id` is None. Otherwise `ready`, `"Check what your model wasn't sure about"`. |

- [ ] **Step 1: Write the failing tests** in `app/server/tests/test_progress.py`

Use the same helpers as `test_datasets.py` (`_project`, `NewExample` and `add_examples`, with `PRINCIPAL` for `org_a`), and `_train` and `wait_for_job` from the `test_report.py` pattern.

```python
def _progress(client, pid):
    return client.get(f"/api/projects/{pid}/progress").json()

def _stages(p):
    return {s["id"]: (s["status"], s["note"]) for s in p["stages"]}

def test_blank_project_progress(client_for):
    client = client_for("org_a")
    pid = client.post("/api/projects", json={"name": "Blank"}).json()["id"]
    p = _progress(client, pid)
    assert [s["id"] for s in p["stages"]] == ["define", "data", "review", "train", "use", "improve"]
    s = _stages(p)
    assert s["data"] == ("blocked", "Define your buckets first")
    assert s["improve"] == ("blocked", "Needs a live model")
    assert p["next"] == "define" and p["examples"] == 0 and p["accuracy"] is None

def test_enough_uploaded_examples_points_at_train(client_for):
    # three buckets, 30 uploaded rows each
    s = _stages(p)
    assert s["define"] == ("done", "3 buckets")
    assert s["data"] == ("done", "90 examples")
    assert s["review"] == ("done", "Nothing left to check")
    assert s["train"] == ("ready", "Ready to train")
    assert p["next"] == "train"

def test_short_bucket_blocks_training(client_for):
    # a: 30, b: 30, c: 29
    assert _stages(p)["data"] == ("ready", "1 bucket needs more examples")
    assert _stages(p)["train"] == ("blocked", "Needs 30 examples per bucket")

def test_generated_examples_wait_in_review(client_for):
    # 30 per bucket, 5 of them generated with how_sure=0.4
    assert _stages(p)["review"] == ("ready", "5 to check")

def test_preview_training_is_not_a_model(client_for):
    # 30 per bucket, then _train(client, pid) with the default FakeTrainer
    assert _stages(p)["train"] == ("done", "Preview run, no model yet")
    assert p["accuracy"] is None

def test_flagship_progress(client_for):
    pid = client.post("/api/projects", json={"name": "T", "template_id": "tallyfern-triage"}).json()["id"]
    s = _stages(p)
    assert s["review"] == ("done", "Labelled by exact rules")
    assert s["train"][0] == "done"

def test_key_marks_use_done(client_for):
    # _project, then POST /api/projects/{pid}/keys
    assert _stages(p)["use"] == ("done", "Connected")

def test_other_org_gets_404(client_for):
    pid = client_for("org_a").post("/api/projects", json={"name": "A"}).json()["id"]
    assert client_for("org_b").get(f"/api/projects/{pid}/progress").status_code == 404
```

**Check before writing `test_preview_training_is_not_a_model`:** read `test_report.py::test_preview_training_card_has_real_jev_rows_and_preview_sys1` to see whether the default `client_for` providers give a preview run. Copy its setup exactly; don't assume.

- [ ] **Step 2: Run the tests to make sure they fail**

Run: `cd app/server && uv run pytest tests/test_progress.py -q`
Expected: FAIL (404s, because there's no route yet).

- [ ] **Step 3: Implement the schemas, `progress()` and the router** to the rules table above, and register the router in `main.py`.

- [ ] **Step 4: Run the tests to make sure they pass**

Run: `cd app/server && uv run pytest tests/test_progress.py -q`
Expected: 8 passed.

- [ ] **Step 5: Regenerate the API docs and types**

Run `make docs`, then add the two type exports to `types.ts`.

Run: `make -C app check && make -C app test`
Expected: all clean and passing.

- [ ] **Step 6: Commit**

```bash
make format
git add app/server/src/system1/progress app/server/src/system1/main.py app/server/tests/test_progress.py app/client/src/lib/api
git commit -m "feat(server): report each stage's progress for a project"
```

---

### Task 3: Workspace shell (progress rail, next-step footer, assistant on the right)

**Files:**
- Create: `app/client/src/features/workspace/useProgress.ts`
- Modify: `app/client/src/features/workspace/stages.ts` (add `nextAfter`)
- Create: `app/client/src/features/workspace/stages.test.ts`
- Create: `app/client/src/features/workspace/NextStep.tsx`
- Rewrite: `app/client/src/features/workspace/StageRail.tsx`
- Modify: `app/client/src/features/workspace/WorkspacePage.tsx` (layout section only, from the return near the end of `Workspace`)
- Modify: `app/client/src/components/StepHeader.tsx` (drop the duplicate `Hint`)
- Modify: `app/client/src/components/layout/AppShell.tsx` (wide main on project routes)
- Modify: `app/client/src/features/improve/ImproveCanvas.tsx` (remove its own "Improve" `h2` block)
- Modify: these files, so each calls `useProgressReload()()` after its mutation succeeds:
  - `features/review/ReviewCanvas.tsx`, in `act` after `response.ok`
  - `features/train/TrainCanvas.tsx`, in `finished()`
  - `features/data/DataCanvas.tsx`, alongside each existing `reload()` in its job and upload `onDone` callbacks
  - `features/use/UseCanvas.tsx`, in `createKey` after `setCreated`

**Interfaces:**
- Consumes: `ProjectProgress` and `StageState` from Task 2, and `STAGES`, `StageId` and `stageHint` from `stages.ts`.
- Produces:
  - `nextAfter(stages: { id: StageId; status: "done" | "ready" | "blocked" }[], current: StageId): StageId | null`. It returns `null` unless `current` is `done`; otherwise it returns the first stage after `current`, in `STAGES` order, whose status isn't `blocked`, or `null` if there is none.
  - `useProgress(projectId: string): { progress: ProjectProgress | null; reload: () => void }`. A failed fetch leaves `progress` as it was.
  - `ProgressReloadContext` (a React context whose default is a no-op) and `useProgressReload(): () => void`.
  - `StageRail({ projectId, current, progress }: { projectId: string; current: StageId; progress: ProjectProgress | null })`
  - `NextStep({ projectId, current, progress }: same props)`

- [ ] **Step 1: Write the failing test** `stages.test.ts`

```ts
import { expect, test } from "bun:test"
import { nextAfter } from "./stages"

const s = (...statuses: ("done" | "ready" | "blocked")[]) =>
  (["define", "data", "review", "train", "use", "improve"] as const).map(
    (id, i) => ({ id, status: statuses[i] }),
  )

test("a done stage hands off to the next open one", () => {
  expect(nextAfter(s("done", "ready", "blocked", "blocked", "ready", "blocked"), "define")).toBe("data")
})
test("skips blocked stages", () => {
  expect(nextAfter(s("done", "done", "done", "blocked", "ready", "blocked"), "review")).toBe("use")
})
test("nothing while the current stage isn't done", () => {
  expect(nextAfter(s("ready", "blocked", "blocked", "blocked", "blocked", "blocked"), "define")).toBeNull()
})
test("nothing after the last stage", () => {
  expect(nextAfter(s("done", "done", "done", "done", "done", "ready"), "improve")).toBeNull()
})
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `cd app/client && bun test src/features/workspace/stages.test.ts`
Expected: FAIL (`nextAfter` is not exported).

- [ ] **Step 3: Implement `nextAfter`**, then run the test.
Expected: 4 pass.

- [ ] **Step 4: Build `useProgress` and its context**

`WorkspacePage` calls `reload` whenever `stage` or `policy.version` changes, and wraps its tree in `ProgressReloadContext.Provider value={reload}`.

- [ ] **Step 5: Rewrite `StageRail`**

**Layout:**
- `nav aria-label="Stages"` holding an `ol` that is `flex gap-1 overflow-x-auto` below `lg` and `lg:flex-col lg:gap-0.5` from `lg` up.
- Each item is a `Link` with `aria-current="step"` on the current stage.
- **Status glyph** (`size-5` circle):
  - done: `Check` (lucide), on `bg-model` with white text
  - ready: an empty circle with `border-2 border-model`
  - blocked: `Lock`, `size-3`, in muted ink on `bg-muted`
  - while progress is null: the number `i + 1`
- **Label:** `text-[15px] font-medium`. A blocked stage is `text-muted-foreground`. The current stage gets `bg-card ring-1 ring-border`.
- **Note:** below the label, `hidden lg:block text-[13px] text-muted-foreground`, from `stage.note`.
- **Accessible name:** `"{label}, {status word}"`, with the status word one of "done", "ready" or "blocked: {note}". Blocked stages stay links.

- [ ] **Step 6: Build `NextStep`**

- When `nextAfter(...)` returns a stage: a `border-t pt-4 mt-8 flex flex-wrap items-center justify-between gap-3` row.
- Text: `"Next: {label}. {stageHint(next)}"` in muted ink.
- Button: `Continue to {label}`, a `Link` to `/app/p/{projectId}/{next}`.
- Otherwise it renders nothing.

- [ ] **Step 7: Lay out the workspace**

- Keep the breadcrumb row ("All projects / ProjectName").
- **From `lg`:** the grid is `lg:grid-cols-[13rem_minmax(0,1fr)_22rem]` when the assistant is open, or `lg:grid-cols-[13rem_minmax(0,1fr)]` when it's closed.
  - The rail is the left column, `lg:sticky lg:top-4 lg:self-start`.
  - The centre holds `StepHeader`, the canvas and `NextStep`.
  - The assistant is the right column, `lg:sticky lg:top-4 lg:self-start`.
- **The assistant:**
  - Change `AgentPanel`'s card height class to `lg:h-[calc(100svh-6rem)]`.
  - Move "Hide assistant" into `AgentPanel`'s `CardHeader`, as an icon button (`PanelRightClose`, `aria-label="Hide assistant"`). This adds an optional `onHide?: () => void` prop.
  - When it's closed, render a fixed `bottom-6 right-6` button (`MessageCircle` icon plus "Assistant"), visible from `lg` up.
- **Below `lg`:** the rail sits above, and the existing Assistant/Workspace toggle stays as it is.
- **`StepHeader`:** an `h2` at `text-[28px] leading-tight font-semibold tracking-[-0.015em]` and one `p` hint. Drop the `Hint` import (`Hint` stays in use elsewhere).
- **`AppShell`:** `main` uses `max-w-[1600px]` when `useMatch("/app/p/*")` matches, and `max-w-6xl` otherwise. Apply the same width to the header's inner div.

- [ ] **Step 8: Wire the reload calls** into Review, Train, Data and Use, as listed under Files.

- [ ] **Step 9: Verify**

Run: `make -C app check && cd app/client && bun test && bun run build`
Expected: clean, with all tests passing and the build succeeding.

Then `make dev`, open a blank project, and check:
- the rail shows Define as ready and the rest as blocked
- after saving two buckets, Define shows done, "2 buckets", and "Continue to Data" appears
- below `lg` the rail scrolls horizontally

- [ ] **Step 10: Commit**

```bash
make format
git add -A app/client/src
git commit -m "feat(client): show progress through the journey and hand off between steps"
```

---

### Task 4: Head-to-head report on Train

Load the `dataviz` skill before writing the chart.

**Files:**
- Create: `app/client/src/features/train/reportBars.ts`
- Create: `app/client/src/features/train/reportBars.test.ts`
- Create: `app/client/src/features/train/HeadToHead.tsx`
- Modify: `app/client/src/features/train/ReportCard.tsx`

**Interfaces:**
- Consumes: `components["schemas"]["ReportRow"]` (`key`, `label`, `status`, `message`, `accuracy`, `ci_low`, `ci_high`, `n`, `errors`, `median_latency_ms`, `avg_p_gold`).
- Produces:

```ts
export type Tone = "model" | "jev" | "base"
export interface Bar {
  key: string
  label: string
  value: number | null   // percent, 0..100
  low: number | null     // percent
  high: number | null    // percent
  tone: Tone
  note: string | null    // shown in place of the bar when value is null
  latencyMs: number | null
}
export function reportBars(rows: ReportRow[]): Bar[]   // keeps the server's row order
```

`tone` is `model` for key `sys1`, `jev` for `jev` and `jev_labels`, and `base` for everything else. `note`, when `status !== "ok"` or `accuracy == null`, is `"Too many failed answers"` for status `errored`, and otherwise `message ?? "Not available"`.

- [ ] **Step 1: Write the failing test** `reportBars.test.ts`

```ts
test("scores become percents with their range", () => {
  const [b] = reportBars([row({ key: "sys1", accuracy: 0.913, ci_low: 0.86, ci_high: 0.95 })])
  expect(b).toMatchObject({ value: 91.3, low: 86, high: 95, tone: "model", note: null })
})
test("both Jev rows share Jev's tone, others are base", () => {
  expect(reportBars([row({ key: "jev" }), row({ key: "jev_labels" }), row({ key: "base" })]).map((b) => b.tone))
    .toEqual(["jev", "jev", "base"])
})
test("a preview row shows its message instead of a bar", () => {
  const [b] = reportBars([row({ key: "sys1", status: "preview", accuracy: null, message: "Real training connects soon." })])
  expect(b.value).toBeNull()
  expect(b.note).toBe("Real training connects soon.")
})
test("an errored row says so", () => {
  expect(reportBars([row({ status: "errored", accuracy: null })])[0].note).toBe("Too many failed answers")
})
```

(`row(partial)` is a local helper. It fills a full `ReportRow`: `status: "ok"`, `accuracy: 0.5`, `ci_low: 0.4`, `ci_high: 0.6`, `n: 100`, `errors: 0`, null latency, avg and message, and `label` set to the key.)

- [ ] **Step 2: Run it to make sure it fails**

Run: `bun test src/features/train/reportBars.test.ts`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `reportBars`**, then run the test.
Expected: 4 pass.

- [ ] **Step 4: Build `HeadToHead({ report })`**

**Headline:**
- `report.verdict?.sentence` as a `p` at `text-[32px] sm:text-[40px] leading-[1.1] font-semibold tracking-[-0.02em] max-w-[30ch] text-balance`.
- Fallback text: "How each model did on your test examples."

**Rows:**
- A `ul`, where each `li` is a grid `grid-cols-[minmax(8rem,12rem)_1fr_4.5rem] items-center gap-4 py-2`.
- **Left column:** the label (`font-medium`), with `"{Math.round(latencyMs)} ms typical"` underneath (`text-[13px] text-muted-foreground tabular-nums`) when present.
- **Middle column:** the bar track, `relative h-2.5 rounded-full bg-muted`.
  - The fill is `absolute inset-y-0 left-0`, with `rounded-r-[4px] rounded-l-full`, `width: value%`, and its background from the tone (`bg-model`, `bg-jev`, or `bg-muted-foreground/60`).
  - The whisker is an `absolute top-1/2 h-px bg-foreground/50` from `low%` to `high%`, with 6px vertical caps at each end.
  - The fill animates `width` from 0 on mount with `motion-safe:transition-[width] motion-safe:duration-700 motion-safe:ease-out`: set the width in a `useEffect` after the first paint.
  - Each `li` has a `title`: `"{value}% right, likely between {low}% and {high}%"`.
  - When `value` is null, the track is `border border-dashed` with no fill, and the right column shows `note` in muted ink.
- **Right column:** `Math.round(value)%`, at `text-lg font-semibold tabular-nums text-right`.
- **Axis:** below the list, a two-label row under the bar column, "0%" and "100%" (`text-[13px] text-muted-foreground`).

- [ ] **Step 5: Rework `ReportCard`**

1. Keep the fixture and preview badges at the top.
2. Render `<HeadToHead report={report} />` below them.
3. Move the existing `Table` into a `<details>` with the summary "Show as a table".
4. Rename the third column's heading to **"How sure of the right answer"**.
5. Drop the `CardDescription` verdict, since the headline now carries it.

- [ ] **Step 6: Verify**

Run: `make -C app check && cd app/client && bun test && bun run build`
Expected: clean and passing.

`make dev`, then open a Tallyfern project's Train step, and check:
- the verdict reads as the headline
- the bars match the table's numbers
- with motion reduced in the OS settings, the bars appear without animating

- [ ] **Step 7: Commit**

```bash
make format
git add app/client/src/features/train
git commit -m "feat(client): show the report card as your model against Jev"
```

---

### Task 5: Buckets wear their colour, and customer text wears the serif

**Files:**
- Modify: `app/client/src/features/review/SortCard.tsx`. Replace the label `Badge` with `BucketChip`. The input `p` gets `font-voice`.
- Modify: `app/client/src/features/data/HealthPanel.tsx`. Put a `BucketSwatch` before the name in the bucket cell (around line 117), with its index from `bucketIndex(policy.options, r.key)`.
- Modify: `app/client/src/features/define/BucketsPanel.tsx`. Put a `BucketSwatch` at the start of each bucket row, with the row's index.
- Modify: `app/client/src/features/playground/ResultRow.tsx`. Render the answer (around line 64, `{answer ?? "No answer"}`) as a `BucketChip` with the option's name and index when `options` includes it, and as plain text otherwise.
- Modify: `app/client/src/features/improve/InboxCard.tsx`. Put a `BucketSwatch` inside each guess button and each search-result button, and give the decision's input text `font-voice`.
- Modify: `app/client/src/features/playground/TryCanvas.tsx`. Give the input `Textarea` the class `font-voice`.
- Modify: `app/client/src/features/define/SamplesPanel.tsx`. Give the sample textareas `font-voice`.

**Interfaces:**
- Consumes: `BucketChip`, `BucketSwatch` and `bucketIndex` from Task 1.

- [ ] **Step 1: Apply the changes above.** This task adds no new logic: `bucketIndex` and `bucketVar` are already tested.

- [ ] **Step 2: Verify**

Run: `make -C app check && cd app/client && bun run build`
Expected: clean.

`make dev`, then check:
- a bucket has the same colour in Define, Data health, Review and Use
- buckets 9–13 on Tallyfern show the neutral swatch
- ticket text renders in Newsreader

- [ ] **Step 3: Commit**

```bash
make format
git add app/client/src
git commit -m "feat(client): carry each bucket's colour through the journey"
```

---

### Task 6: Dashboard project cards show where each project stands

**Files:**
- Create: `app/client/src/features/dashboard/ProgressStrip.tsx`
- Modify: `app/client/src/features/dashboard/DashboardPage.tsx` (`ProjectCard` and the page heading)

**Interfaces:**
- Consumes: `useProgress(projectId)` from Task 3, and `STAGES`.
- Produces: `ProgressStrip({ progress }: { progress: ProjectProgress | null })`. It's six `h-1.5 flex-1 rounded-full` segments in a `flex gap-1` row:
  - done is `bg-model`
  - ready is `bg-model/25`
  - blocked is `bg-muted`
  - null progress is all `bg-muted`

  It has `role="img"` with `aria-label="{done count} of 6 steps done"`.

- [ ] **Step 1: Rework `ProjectCard`**

**Contents, in order:**
1. The name: the stretched link, which goes to `progress?.next ?? stage`.
2. The `ProgressStrip`.
3. A status line in `text-[13px] text-muted-foreground`, the first of these that applies:
   - `"Live: {project.live_model_label}"` if `project.live_model_label`
   - `"Next: {label of progress.next}"` if `progress?.next`
   - `"All steps done"`
4. A score line, only when `progress?.accuracy != null`: `"Your model {pct}, Jev {pct}"` (omit the Jev part when `jev_accuracy` is null), `tabular-nums`.

**Actions:**
- Rename and Delete move into a `DropdownMenu`, triggered by a `size="icon-sm" variant="ghost"` button with `MoreHorizontal` and `aria-label="Project actions"`, placed top-right with `relative z-10` above the stretched link.
- The existing rename input and delete confirmation flow stay as they are.
- Drop the "Created …" line and the "Open to keep working" fallback description.

**Page:** the heading changes from "Your projects" to "Projects".

**Check first:** confirm that `size="icon-sm"` exists in `components/ui/button.tsx`. If it doesn't, use `size="icon"`.

- [ ] **Step 2: Verify**

Run: `make -C app check && cd app/client && bun run build`
Expected: clean.

`make dev`, then check:
- each card shows its strip and next step
- the actions menu opens with the keyboard (Tab, then Enter)
- a click on the card body opens the next stage

- [ ] **Step 3: Commit**

```bash
make format
git add app/client/src/features/dashboard
git commit -m "feat(client): show each project's progress on the dashboard"
```

---

### Task 7: Landing page

**Files:**
- Create: `app/client/src/features/landing/DecisionDemo.tsx`
- Rewrite: `LandingContent` in `app/client/src/features/landing/LandingPage.tsx`. `LandingPage`'s signed-in redirect stays as it is.

**Content, which is fixed:**
- **Headline:** "Decisions made the way your team makes them."
- **Lead:** "Your team makes the same call hundreds of times a week: which queue a ticket goes to, whether a refund gets approved. system1 turns that call into written guidelines and a small model trained on your own decisions, behind the same API as Jev."
- **Buttons:** "Sign up" (primary) and "Sign in" (outline), as now.
- **Header:** the "system1" wordmark (keep the `1` in `text-primary`; it's the product's name, not an accented word) and a ghost "Sign in" link.
- **Demo ticket:** Tallyfern sample `t0005` from `app/server/src/system1/templates/data/tallyfern/samples.jsonl`:
  - subject: "Someone logged into our account!!"
  - body: the first two sentences of the body, ending "…that NOBODY here created."
- **Demo answers:** the recorded `eval/*_predictions.jsonl` rows for `t0005`:
  - "Your model", Trust & Safety, how sure 85%
  - "Jev + your guidelines", Trust & Safety, how sure 70%
- **Caption:** "Sample numbers from the Tallyfern example project."
- **How it works:** heading "How it works", then the six stages from `STAGES`, as an `ol` of six items, each with its number, `label` and `hint`.
- **Footer:** "Built for Build North 2026 by Thomas Michalski and Nicholas Stranges."

**Layout:**
- **The hero:** `grid lg:grid-cols-[1.1fr_1fr] gap-12 items-center py-16 sm:py-24`. The headline is at `text-[32px] sm:text-[40px] leading-[1.1] font-semibold tracking-[-0.02em] max-w-[18ch]`, and the lead is at `text-lg text-muted-foreground max-w-[60ch]`.
- **`DecisionDemo`:**
  - A ticket card (`rounded-[10px] border bg-card p-5`), with the subject in `font-medium` and the body in `font-voice`.
  - Under the card, two answer rows, each a grid of: the lane name, a `BucketChip` for Trust & Safety (index 0, its slot in Tallyfern's options), a 6rem "how sure" bar in the lane's tone (`bg-model` or `bg-jev`), and the percent in `tabular-nums`.
  - The caption in `text-[13px] text-muted-foreground`.
- **How it works:** `ol` is `grid gap-6 sm:grid-cols-2 lg:grid-cols-6`. Each `li` has its number in a `size-6 rounded-full border-2 border-model text-[13px]` circle, the label in `font-medium`, and the hint in `text-sm text-muted-foreground`. No cards.
- **Load moment:** the ticket fades in and moves up 8px over 400ms, then each answer bar fills from 0 with 150ms between them. All of it goes under `motion-safe:`, using the `tw-animate-css` classes already imported (`animate-in fade-in slide-in-from-bottom-2`), with bar widths set after mount.

- [ ] **Step 1: Build `DecisionDemo` and rewrite `LandingContent`** to the content and layout above.

- [ ] **Step 2: Verify**

Run: `make -C app check && cd app/client && bun run build`
Expected: clean.

`make dev`, signed out, then check `/`:
- there's no horizontal scroll at 390px wide
- keyboard focus is visible on both buttons
- with motion reduced, the page renders already in its final state

- [ ] **Step 3: Commit**

```bash
make format
git add app/client/src/features/landing
git commit -m "feat(client): show a real decision on the landing page"
```

---

### Gate A: Thomas checks Tier 1

Run `make verify`. Expected: check, test and the client build all pass.

Then Thomas walks the demo path in `make dev`: landing, sign in, dashboard, a Tallyfern project (Define, Data, Review, Train, Use) and a blank project's Define, in light mode at desktop width and at phone width. He decides whether Tier 2 goes in before recording.

---

### Task 8: Keyboard-first Review

**Files:**
- Create: `app/client/src/features/review/keys.ts`
- Create: `app/client/src/features/review/keys.test.ts`
- Modify: `app/client/src/features/review/ReviewCanvas.tsx` (`Queue`)
- Modify: `app/client/src/features/review/SortCard.tsx`

**Interfaces:**
- Produces:

```ts
export type ReviewAction =
  | { kind: "agree" }
  | { kind: "move"; index: number }   // index into policy.options
  | { kind: "next" }
  | { kind: "prev" }
export function reviewKey(key: string, bucketCount: number): ReviewAction | null
export function isTypingTarget(el: { tagName?: string; isContentEditable?: boolean } | null): boolean
```

- **`reviewKey`:**
  - `"Enter"`, `"y"` and `"Y"` → agree.
  - `"1"`–`"9"` → move, with index `digit − 1`, only when the index is less than `bucketCount`; otherwise null.
  - `"j"` and `"ArrowDown"` → next. `"k"` and `"ArrowUp"` → prev.
  - Anything else → null.
- **`isTypingTarget`:** true for `INPUT`, `TEXTAREA` and `SELECT`, or when `isContentEditable` is set.
- **`SortCard`** gains these props: `active: boolean`, `index: number` (its position, for the `id`) and `options` (the full list, for slots). `onMove(to)` is unchanged.

- [ ] **Step 1: Write the failing test** `keys.test.ts`

```ts
test("digits pick a bucket by position", () => {
  expect(reviewKey("1", 4)).toEqual({ kind: "move", index: 0 })
  expect(reviewKey("4", 4)).toEqual({ kind: "move", index: 3 })
  expect(reviewKey("5", 4)).toBeNull()
  expect(reviewKey("0", 4)).toBeNull()
})
test("enter and y keep the label", () => {
  expect(reviewKey("Enter", 3)).toEqual({ kind: "agree" })
  expect(reviewKey("y", 3)).toEqual({ kind: "agree" })
})
test("j/k and arrows move between cards", () => {
  expect(reviewKey("j", 3)).toEqual({ kind: "next" })
  expect(reviewKey("ArrowUp", 3)).toEqual({ kind: "prev" })
})
test("typing in a field is never a shortcut", () => {
  expect(isTypingTarget({ tagName: "TEXTAREA" })).toBe(true)
  expect(isTypingTarget({ tagName: "DIV", isContentEditable: true })).toBe(true)
  expect(isTypingTarget({ tagName: "BUTTON" })).toBe(false)
  expect(isTypingTarget(null)).toBe(false)
})
```

- [ ] **Step 2: Run it to make sure it fails, implement, then run it to make sure it passes**

Run: `bun test src/features/review/keys.test.ts`
Expected: first FAIL, then 4 pass.

- [ ] **Step 3: Wire the keys into `Queue`**

- Keep `active` index state, starting at 0 and clamped when cards are removed.
- Add a `window` `keydown` listener that returns early if `isTypingTarget(e.target)`, if any of `e.metaKey`, `e.ctrlKey` or `e.altKey` is held, or if `busyId` is set.
- **move:** when the bucket at that index is the card's current label, treat it as agree. Otherwise call `act(card, "move", options[index].key)`.
- After a sort, `active` stays at the same index, so it lands on the next card.
- Scroll the active card into view with `scrollIntoView({ block: "nearest" })`.
- Above the list, add a help line in muted ink: "Keys: 1–9 sorts into a bucket, Enter keeps it, J and K move between cards."

- [ ] **Step 4: Update `SortCard`**

- Replace the "Move to…" dropdown with a wrapping row of `Button size="sm" variant="outline"` buttons, one per bucket. Each holds a `BucketSwatch`, the name, and, for the first nine, the digit in a `text-[13px] text-muted-foreground` span. The current bucket's button is `variant="secondary"` with `aria-pressed`.
- "Looks right" stays as the primary button.
- The active card gets `ring-2 ring-ring` and `aria-current="true"`.

- [ ] **Step 5: Verify**

Run: `make -C app check && cd app/client && bun test && bun run build`
Expected: clean and passing.

`make dev`, then check that a generated-data project's Review sorts with 1–9 and Enter, and that typing in the assistant composer doesn't sort.

- [ ] **Step 6: Commit**

```bash
make format
git add app/client/src/features/review
git commit -m "feat(client): sort review cards from the keyboard"
```

---

### Task 9: Define's sticky save bar

**Files:**
- Modify: `app/client/src/features/define/DefineCanvas.tsx`

- [ ] **Step 1: Move Save and Discard into a sticky bar**

1. Remove the top-right Save/Discard row.
2. Render the bar only when `dirty`: `sticky bottom-4 z-20 mt-8 flex items-center justify-between gap-3 rounded-[10px] border bg-card px-4 py-3`, with `role="region"` and `aria-label="Unsaved changes"`.
3. Its contents: the text "You have unsaved changes", then "Discard changes" (ghost) and "Save" (primary), with the same handlers and disabled states as now.
4. Move the "Draft my buckets" dropdown onto the same row as the "What are you deciding?" label, aligned right, and delete its separate `flex justify-end` wrapper.

- [ ] **Step 2: Verify**

Run: `make -C app check && cd app/client && bun run build`
Expected: clean.

`make dev`, then check that editing a bucket name shows the bar at the bottom of the viewport, that saving hides it, and that the assistant's rule edits (which discard the draft) also hide it.

- [ ] **Step 3: Commit**

```bash
make format
git add app/client/src/features/define/DefineCanvas.tsx
git commit -m "feat(client): keep save in reach while editing a definition"
```

---

### Task 10: Stage-aware assistant starters

**Files:**
- Modify: `app/client/src/features/agent/AgentPanel.tsx`

- [ ] **Step 1: Replace `STARTERS` with a per-stage map**

Use exactly this copy:

```ts
const STARTERS: Record<string, string[]> = {
  define: ["Draft my buckets", "Look over my guidelines", "What makes a good bucket?"],
  data: ["Generate practice examples", "How many examples do I need?"],
  review: ["Which buckets look weakest?"],
  train: ["Train my model", "Explain the report card"],
  use: ["How do I call the endpoint?"],
  improve: ["What should I fix first?"],
}
```

Show `STARTERS[stage] ?? []` whenever the empty-thread intro shows, for every project, not just template ones. Keep the two intro sentences as they are.

- [ ] **Step 2: Verify**

Run: `make -C app check`
Expected: clean.

`make dev`, then check that a blank project's empty thread shows the Define starters, and that clicking one sends it.

- [ ] **Step 3: Commit**

```bash
make format
git add app/client/src/features/agent/AgentPanel.tsx
git commit -m "feat(client): suggest assistant prompts that fit the current step"
```

---

### Gate B: Thomas checks Tier 2

Run `make verify`. Expected: everything passes. Thomas tries Review with the keyboard and the Define save bar.

---

### Task 11 (optional): Light/dark toggle

**Files:**
- Modify: `app/client/src/app/RootLayout.tsx`. Wrap the tree in `next-themes`' `ThemeProvider` with `attribute="class"`, `defaultTheme="system"` and `enableSystem`.
- Create: `app/client/src/components/layout/ThemeToggle.tsx`
- Modify: `app/client/src/components/layout/AppShell.tsx` and `features/landing/LandingPage.tsx`. Put the toggle before `UserButton`, and beside "Sign in" on the landing page.

**Check first:** read `node_modules/next-themes/dist/index.d.ts` for the `ThemeProvider` props and `useTheme()`'s return type in the installed version. Also confirm that `components/ui/sonner.tsx` already calls `useTheme`, so toasts follow the theme.

- [ ] **Step 1: Build `ThemeToggle`**

- A `Button size="icon" variant="ghost"`. It shows `Moon` when the resolved theme is light, and `Sun` when it's dark.
- `aria-label` is "Switch to dark mode" or "Switch to light mode".
- On click, call `setTheme(resolvedTheme === "dark" ? "light" : "dark")`.

- [ ] **Step 2: Verify**

Run: `make verify`
Expected: passes.

`make dev`, then toggle on the dashboard, Train and the landing page, and check:
- the bucket colours and model/Jev bars switch to their dark steps
- Clerk's widgets stay legible
- the choice persists across a reload

- [ ] **Step 3: Commit**

```bash
make format
git add app/client/src
git commit -m "feat(client): add a light and dark theme switch"
```

---

### Wrap-up

- [ ] **Parked ideas:** add these to `docs/backlog.md`, dated 2026-10-25:
  - a live decision feed on Use
  - cost per 1,000 decisions on the report (needs server-side pricing)
  - the flat-section restyle of the remaining canvases
  - a first-run tour

  Commit with `docs(backlog): park redesign follow-ups`.
- [ ] **Final check:** run `make verify` one last time, and report the output as it ran.

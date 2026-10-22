# system1 Product Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the system1 website end to end: a FastAPI server and React client where an organization signs in with Clerk, picks or describes a decision, builds rules with an agent, tries them live on Jev, generates labelled examples, sees a report card, gets an API key, and corrects decisions. Training stays outside `app/`, behind a contract.

**Architecture:** A modular FastAPI server (`app/server`) with a pure domain core (policy, rules engine, question builder) and ports and adapters for every outside service. Those services are Jev on TypeSafe, a sys1 HTTP endpoint, Anthropic, a trainer, dataset files and evaluation files, and each has a fake. A Vite React client (`app/client`) uses Clerk B2B organizations, types generated from the server's OpenAPI schema, and server-sent events for the agent. SQLite stores everything, scoped by Clerk organization. One Modal app serves both server and client.

**Tech Stack:**
- **Server:** Python 3.12, uv, FastAPI, Pydantic v2, pydantic-settings, SQLAlchemy 2, httpx, `clerk-backend-api`, `anthropic`, ruff, pytest.
- **Client:** bun, Vite, React, TypeScript, Tailwind CSS v4, shadcn/ui, `react-router` (declarative mode), `@clerk/react`, `@clerk/themes`, openapi-typescript and openapi-fetch.
- **Deploy:** Modal.

**Spec:** [docs/superpowers/specs/2026-10-21-system1-product-design.md](../specs/2026-10-21-system1-product-design.md). Read it with this plan. CLAUDE.md's "Engineering rules (product build)" apply to every task.

## Global Constraints

- **Where things live:**
  - All product code is under `app/server/` (package `system1`, src layout) and `app/client/`.
  - Say "client" and "server", never "frontend" and "backend".
  - Training code stays out of `app/`. Nothing in `app/` imports `train.py`, `eval_*.py`, `unsloth` or GPU code. Training is reached only through the `Trainer` contract.
- **Toolchain:**
  - Server: `uv add` / `uv sync` / `uv run`, with `ruff check` and `ruff format`.
  - Client: `bun add` / `bun run`, with Prettier.
  - Never use pip, npm, yarn or pnpm for `app/`.
  - Use the current stable versions at install time. Check the installed package's types and docs instead of memory.
- **Testing is light (hackathon).** Write the tests named in each task and nothing more. Default tests use fakes. Real calls to Jev or Anthropic exist only in tests marked `@pytest.mark.live`, which are skipped unless `LIVE=1`.
- **Jev:**
  - Pin the model to `jev-1.13.0` by default (setting `JEV_MODEL`) and store the `model` field from every response.
  - Calibration and thresholds use `probabilities`, never `confidence`.
  - Thomas has confirmed with TypeSafe that using Jev in the product and the demo is fine.
- **Training data rules:**
  - Never use Jev's answers as training labels, or to choose what gets labelled. Every decision answered by Jev is stored with `not_for_training = True`.
  - Feedback on test-set items is never training-eligible. The test set is frozen.
- **Policy limits:**
  - A decision has 2 to 15 options. Option keys are `snake_case` and unique.
  - Inputs larger than `MAX_INPUT_CHARS = 6000` are rejected with a clear message.
- **Agent:**
  - The model is `claude-sonnet-5-5` for now (switch back to `claude-opus-5-5` with AGENT_MODEL), with `output_config.effort` set to `medium`.
  - Load the `claude-api` skill before writing any Anthropic code, and enable server-side refusal fallbacks (`fallbacks: "default"` with its beta header, as the skill specifies).
- **Spending:** generating examples and training happen only after the user clicks a confirmation card. Per-organization daily token cap: `ORG_DAILY_TOKEN_CAP = 3_000_000`.
- **No model-written code runs on the server.** Rules are data, evaluated by the rules engine.
- **Clerk B2B:**
  - Use the current package `@clerk/react`, with `<Show when=…>` rather than SignedIn/SignedOut.
  - Organizations are on, with Membership required.
  - Every `/api` route requires an active organization, and every query filters by `org_id`. A request for another organization's object returns 404.
- **UI copy in plain words:** say "options", "examples", "your model" and "how often it's right". Probabilities, splits and calibration go in a "Details" drawer. Placeholder or fixture numbers always show the banner "Sample numbers. The real benchmark isn't in yet."
- **Commits:**
  - Use conventional messages, `type(scope): description`, with an imperative lowercase subject of 72 characters or less.
  - Commit only on `product-design`, never on `main`, and with no Claude attribution.
  - One commit per task, at minimum.

## Review Focus

1. **Cross-organization access by id.** A user in org B who requests org A's project, decision or API key by id gets a 404 and sees no data. An API key for project A can't decide for project B. Tests are in Tasks 4, 8 and 13.
2. **No active organization.** A signed-in user with a pending session, or no active org, sees the choose-organization screen rather than errors. The server answers 403 with code `no_active_org`. The client's cached data resets when the user switches orgs. Tests are in Task 4 (server) and in Gate G2's manual steps.
3. **Upstream failures and missing keys.** Jev or Anthropic return 429, 529 or 5xx, time out, or have no key configured. The user sees a readable message, transient errors retry with backoff, and the page stays usable. The tests are in Task 6, where the Jev adapter maps errors to a `ProviderError` with a user message.
4. **Invalid policy from the agent or the editor.** Examples are a rule whose label isn't an option, duplicate option keys, more than 15 or fewer than 2 options, or a rule condition on an unknown input. The change is rejected with a message, the stored policy doesn't change, and Try stays blocked until the policy is valid. Tests are in Task 5 (validation) and Task 11 (the agent tool returns an error result).
5. **Oversized input.** A huge pasted ticket gets a 422 with the limit stated, at both the gateway and Try. The test is in Task 8.

---

## Phase A: foundation, sign-in, projects, Jev playground (Block A, ending at Gate G2)

### Task 1: Server scaffold and make targets

**Files:**
- Create: `app/server/pyproject.toml`, `app/server/src/system1/__init__.py`, `app/server/src/system1/main.py`, `app/server/src/system1/config.py`, `app/server/src/system1/openapi_dump.py`, `app/server/tests/test_health.py`, `app/server/.python-version` (contains `3.12`)
- Create: `app/Makefile`
- Modify: `Makefile` (root), `CLAUDE.md` (section "Environment and commands"), `.gitignore` (add `app/server/.data/`, `app/client/dist/`, `app/client/node_modules/`)

**Interfaces:**
- Produces:
  - `create_app() -> FastAPI` in `main.py`, and a module-level `app = create_app()`.
  - `GET /api/health` returns `{"status": "ok"}`.
  - `Settings` (pydantic-settings) and `get_settings() -> Settings`, cached with `lru_cache`. Settings read the repo-root `.env`, located relative to `config.py` rather than the working directory, and a missing file is fine because deployed config comes from environment variables. Relative paths in settings resolve against the repo root. Fields and defaults:
    - Keys: `anthropic_api_key: str | None`, `typesafe_api_key: str | None`, `typesafe_base_url = "https://api.typesafe.ai"`, `jev_model = "jev-1.13.0"`.
    - Clerk and origins: `clerk_secret_key: str | None`, `client_origins: list[str] = ["http://localhost:5173"]`.
    - Storage: `database_url = "sqlite:///app/server/.data/system1.db"`.
    - Provider switches: `llm_provider: Literal["anthropic","fake"] = "anthropic"`, `jev_provider: Literal["typesafe","fake"] = "typesafe"`, `sys1_provider: Literal["none","http","fake"] = "none"`, `sys1_base_url: str | None`, `sys1_model = "sys1"`, `trainer: Literal["none","fake"] = "none"`.
    - Agent: `agent_model = "claude-sonnet-5-5"`, `agent_effort = "medium"`.
    - Limits: `org_daily_token_cap = 3_000_000`, `max_input_chars = 6000`, `auto_threshold = 0.8`, `est_cost_per_example_usd = 0.02`.
    - Paths: `playbook_path = ".claude/skills/system1-onboard/playbook.md"` and `static_dir: str | None` (the built client, used when deployed).
  - `python -m system1.openapi_dump <out.json>` writes `create_app().openapi()`.
- Make targets in `app/Makefile`:
  - `server` runs uvicorn on port 8000 with reload.
  - `client` runs `bun run dev`.
  - `dev` runs both, with `bunx concurrently -k`.
  - `format` runs `ruff format`, `ruff check --fix`, and Prettier on the client.
  - `check` runs `ruff check`, `ruff format --check`, and `bun run typecheck`.
  - `test` runs `uv run pytest -q` in the server.
  - `docs` runs openapi_dump into `app/client/src/lib/api/openapi.json`, then `bunx openapi-typescript` into `schema.d.ts`.
  - `verify` runs check, test and the client build.
- Root `Makefile` targets `dev`, `format`, `check`, `docs` and `verify` delegate with `$(MAKE) -C app <target>`. The root `test` keeps running the phase 1 tests, now explicitly with `$(PYTHON) -m pytest -q tests`, and then runs `$(MAKE) -C app test`.

- [ ] **Step 1:** Create the uv project in `app/server`, with `uv init --package` or by hand, using the src layout and Python 3.12. Add the runtime deps (`fastapi[standard]`, `pydantic-settings`, `sqlalchemy`, `httpx`, `clerk-backend-api`, `anthropic`) and the dev deps (`pytest`, `pytest-asyncio`, `ruff`). Configure ruff for line length 120 and pytest with `testpaths = ["tests"]` and a `live` marker.
- [ ] **Step 2: Write the failing test** `test_health_returns_ok`: `TestClient(create_app()).get("/api/health").json() == {"status": "ok"}`.
- [ ] **Step 3:** Run `cd app/server && uv run pytest -q`. Expected: FAIL, because `create_app` isn't defined yet.
- [ ] **Step 4:** Implement `config.py`, `main.py` (the app factory with a CORS middleware for `client_origins` and an `/api` router) and `openapi_dump.py`.
- [ ] **Step 5:** Run `uv run pytest -q`. Expected: PASS. Then write both Makefiles and the `.gitignore` lines, and add the new targets to CLAUDE.md's command list.
- [ ] **Step 6:** Run `make -C app check`. Expected: ruff passes. The client checks are skipped until Task 2, so guard the client steps with `if [ -d client/node_modules ]`.
- [ ] **Step 7: Commit** `chore(server): scaffold fastapi app, settings and make targets`.

### Task 2: Client scaffold, UI kit and typed API client

**Files:**
- Create: `app/client/` with Vite's React-TS template using bun, plus `vite.config.ts`, `src/index.css`, `src/lib/api/client.ts`, `src/lib/api/openapi.json` and `schema.d.ts` (both generated), `src/lib/sse.ts`, `src/components/ui/*` (shadcn), `.prettierrc`

**Interfaces:**
- Produces:
  - **`vite.config.ts`:**
    - Plugins `@vitejs/plugin-react` and `@tailwindcss/vite`.
    - A dev proxy that sends `/api` and `/v1` to `http://localhost:8000`.
    - It loads the repo-root `.env` with `loadEnv(mode, repoRoot, "")`, and defines **only** `import.meta.env.VITE_CLERK_PUBLISHABLE_KEY` from `CLERK_PUBLISHABLE_KEY`. Never expose other variables: `CLERK_SECRET_KEY` must never reach the client.
  - **Scripts:** `bun run dev`, `bun run build`, `bun run typecheck` (`tsc -b --noEmit`) and `bun run format`.
  - **`src/lib/api/client.ts`:** `useApi()` returns an `openapi-fetch` client typed with `paths` from `schema.d.ts`. A middleware adds `Authorization: Bearer ${await getToken()}` using Clerk's `useAuth().getToken`.
  - **`src/lib/sse.ts`:** `streamEvents(url: string, body: unknown, token: string, onEvent: (e: {event: string, data: any}) => void, signal?: AbortSignal): Promise<void>`. It uses a `fetch` POST and parses `event:` / `data:` lines from the response body stream. `EventSource` can't send an Authorization header, so it isn't used.
  - **shadcn/ui** is initialized for Tailwind v4, with these components: button, card, input, textarea, badge, dialog, sheet, tabs, dropdown-menu, select, separator, skeleton, sonner (toasts), tooltip, table.
  - **Visual direction:** clean, light, one accent color (teal) for "your model" and amber for Jev, matching the blueprint page.

- [ ] **Step 1:** Scaffold the client with bun, then add Tailwind v4, shadcn/ui, `react-router`, `openapi-fetch`, `openapi-typescript` (dev) and Prettier.
- [ ] **Step 2:** Implement `vite.config.ts`, `client.ts` and `sse.ts`.
- [ ] **Step 3:** Run `make docs`. Expected: `schema.d.ts` contains the `/api/health` path.
- [ ] **Step 4:** Run `make -C app check` and `cd app/client && bun run build`. Expected: both succeed.
- [ ] **Step 5: Commit** `chore(client): scaffold vite react client with ui kit and typed api`.

### Task 3: Clerk B2B on the client: landing, sign-in, organizations, app shell

**Files:**
- Create:
  - `src/main.tsx`, `src/app/RootLayout.tsx`, `src/app/routes.tsx`
  - `src/features/landing/LandingPage.tsx`
  - `src/features/auth/SignInPage.tsx`, `src/features/auth/SignUpPage.tsx`, `src/features/auth/ChooseOrganizationPage.tsx`
  - `src/components/layout/AppShell.tsx`, `src/components/layout/RequireOrg.tsx`
  - `src/features/team/TeamPage.tsx`

**Interfaces:**
- Consumes: `VITE_CLERK_PUBLISHABLE_KEY` (Task 2).
- Produces:
  - **Routes:**
    - `/` is the landing page. A signed-in user is redirected to `/app`.
    - `/sign-in/*` renders `<SignIn routing="path" path="/sign-in">` and `/sign-up/*` renders `<SignUp routing="path" path="/sign-up">`.
    - `/session-tasks/choose-organization` renders `<TaskChooseOrganization redirectUrlComplete="/app">`.
    - `/app/*` uses `AppShell`, wrapped in `RequireOrg`.
    - `/app/team/*` renders `<OrganizationProfile routing="path" path="/app/team">`.
  - **`RootLayout`** wraps `<ClerkProvider>` with:
    - `publishableKey`
    - `routerPush` and `routerReplace` wired to `useNavigate()` (declarative mode, per Clerk's React Router guide)
    - `afterSignOutUrl="/"`
    - `taskUrls={{ "choose-organization": "/session-tasks/choose-organization" }}`
    - `appearance={{ theme: shadcn }}` from `@clerk/themes`
  - **`AppShell`** has a top bar with the product name, `<OrganizationSwitcher hidePersonal afterSelectOrganizationUrl="/app" afterCreateOrganizationUrl="/app" />`, a "Team" link and `<UserButton />`, plus an `<Outlet />`.
  - **`RequireOrg`:**
    - Uses `<Show when="signed-in" fallback={<Navigate to="/sign-in" />}>`.
    - If `useAuth().orgId` is missing, it renders a friendly card with a `<CreateOrganization />` button.
    - It keys its children on `orgId`, so switching org remounts the pages and drops cached data.
  - **The landing page** speaks to the support-ops lead, using the spec's pitch line. It has a short "how it works" (rules, try, your model, improve) and Sign up / Sign in buttons.
- Before starting, the implementer checks the installed `@clerk/react` exports for `Show`, `TaskChooseOrganization`, the organization components and the `taskUrls` prop, and follows what's actually installed.

- [ ] **Step 1:** Add `@clerk/react` and `@clerk/themes`, then implement the files above.
- [ ] **Step 2:** Run `bun run typecheck` and `bun run build`. Expected: both pass.
- [ ] **Step 3:** Run `make dev` and open `http://localhost:5173`. Expected: the landing page renders and `/sign-in` shows Clerk's sign-in. Full manual checks happen at G2.
- [ ] **Step 4: Commit** `feat(client): add clerk organizations, landing page and app shell`.

### Task 4: Clerk on the server, database, and organization scoping

**Files:**
- Create: `src/system1/db.py`, `src/system1/auth/principal.py`, `src/system1/auth/verifier.py`, `src/system1/auth/deps.py`, `src/system1/usage.py`, `tests/conftest.py`, `tests/test_auth.py`

**Interfaces:**
- Produces:
  - **`db.py`:** `Base(DeclarativeBase)` and `make_engine(url)`. It turns on SQLite WAL mode and creates the parent folder. It also has `init_db(engine)` (`create_all`) and a `get_session()` FastAPI dependency that yields a `Session`. Table modules register with `Base`, and `init_db` runs in the app's lifespan.
  - **`principal.py`:**
    - `@dataclass(frozen=True) class Principal` with `user_id: str`, `org_id: str`, `org_role: str` and `org_slug: str | None`.
    - `principal_from_claims(claims: dict) -> Principal`, which reads `sub` and the `o` claim (`id`, `rol`, `slg`).
    - It raises `NoActiveOrganization` when `sts == "pending"` or `o` is missing.
  - **`verifier.py`:**
    - `class TokenVerifier(Protocol)` with `def claims(self, request: Request) -> dict | None`.
    - `ClerkVerifier(secret_key, authorized_parties)` uses `Clerk(bearer_auth=...).authenticate_request(httpx.Request(...), AuthenticateRequestOptions(authorized_parties=...))` and returns `request_state.payload` when `is_signed_in`.
    - `FakeVerifier(claims)` is for tests.
  - **`deps.py`:** `get_principal(request) -> Principal`. It returns 401 `{"code":"unauthenticated"}` with no valid token, and 403 `{"code":"no_active_org"}` with no active organization. The verifier comes from `app.state.verifier`.
  - **`usage.py`:** a `TokenUsage` table (`org_id`, `day`, `tokens`), plus `record_usage(session, org_id, tokens)` and `check_budget(session, org_id) -> None`. When the day's tokens are at or above the cap, it raises `BudgetExceeded`, which returns 429 with the message "Your team has used today's AI budget. It resets at midnight UTC."
  - **`tests/conftest.py`:** `client_for(org_id: str, user_id="user_1")` fixture builds a `TestClient` with a `FakeVerifier` and an in-memory SQLite database. Task 6 extends it to inject fake providers.

- [ ] **Step 1: Write the failing tests:**
  - `test_claims_with_org_give_principal`: claims `{"sub":"user_1","o":{"id":"org_a","rol":"admin","slg":"acme"}}` give `Principal("user_1","org_a","admin","acme")`.
  - `test_pending_session_has_no_org`: `{"sub":"user_1","sts":"pending"}` raises `NoActiveOrganization`.
  - `test_api_without_org_returns_403_no_active_org`: covers Review Focus 2.
  - `test_api_without_token_returns_401`.
- [ ] **Step 2:** Run `uv run pytest tests/test_auth.py -q`. Expected: FAIL (import errors).
- [ ] **Step 3:** Implement the files above. `create_app` installs `ClerkVerifier` from settings when `clerk_secret_key` is set, and otherwise rejects every `/api` request with 401 and a log warning.
- [ ] **Step 4:** Run `uv run pytest -q`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(server): verify clerk sessions and scope requests by organization`.

### Task 5: Domain core: policy model, validation, rules engine, question builder

**Files:**
- Create: `src/system1/domain/policy.py`, `src/system1/domain/rules_engine.py`, `src/system1/domain/questions.py`, `tests/test_rules_engine.py`, `tests/test_policy.py`
- Create: `src/system1/templates/data/tallyfern/rules.json` (Tallyfern's routing rules R01–R13 in the rules-as-data format, used by the acceptance test and the template)

**Interfaces:**
- Produces:
  - **`policy.py`:**
    - `InputField(key, label, type: Literal["enum","int","float","bool","text"], values: list[str] | None = None, nullable: bool = True, description: str = "")`
    - `Option(key, name, covers: list[str] = [], excludes: list[str] = [], example: str = "")`
    - `Condition`, a recursive Pydantic union of `Leaf(field: str, op: Literal["eq","ne","gt","gte","lt","lte","in","is_null"], value: Any = None)`, `AllOf(all: list[Condition])`, `AnyOf(any: list[Condition])` and `NotOf(not_: Condition, alias "not")`
    - `Rule(id, text, label, when: Condition | None = None)`
    - `Policy(decision_question, question_key = "decision", inputs: list[InputField], options: list[Option], rules: list[Rule])`
    - `PolicyIssue(path, message)` and `validate_policy(policy) -> list[PolicyIssue]`
    - Constants `MIN_OPTIONS = 2` and `MAX_OPTIONS = 15`
  - **`rules_engine.py`:**
    - `RuleMatch(label, rule_id)` and `evaluate(rules: list[Rule], facts: dict) -> RuleMatch | None`. The first match wins, a rule with `when=None` always matches, and comparisons with a missing or `None` fact are false ("unknown means no").
    - `is_fully_testable(rules) -> bool`, which is true when every rule except a final catch-all has a `when`.
    - `thresholds(rules) -> dict[str, list]`, the literal values compared per field, used by the example sampler.
  - **`questions.py`:** `build_questions(policy, variant: Literal["labels","policy"], order: list[str] | None = None) -> dict`. It returns Jev's question shape, `{policy.question_key: {"type": "choice", "instructions": ..., "criteria": {...}}}`.
    - The `labels` variant uses the option names only.
    - The `policy` variant uses an object per option (`{"covers": [...], "excludes": [...]}`) and instructions `{"question": decision_question, "precedence": [rule texts in order]}`.
    - It raises `ValueError` if `validate_policy` returns any issues.

- [ ] **Step 1: Write the failing tests:**
  - `test_tallyfern_rules_match_phase1_router`. This is the spec's acceptance check. For every record in the repo-root `data/raw/facts.jsonl`, `evaluate(tallyfern_rules, record["facts"])` returns the same `(label, rule_id)` as the record's stored `queue` and `rule_id`. The test skips if the file is missing.
  - `test_unknown_fact_never_meets_condition`: a refund with `amount_usd=None` gives `billing_refunds` / R05.
  - `test_validate_rejects_unknown_label_duplicates_and_option_count`. It returns one issue each for a rule label not in options, duplicate option keys, 16 options and a single option. It also flags a condition on an unknown input. This covers Review Focus 4.
  - `test_build_questions_policy_variant_shape`: the criteria keys equal the option keys in the given order, and the instructions precedence equals the rule texts.
- [ ] **Step 2:** Run `uv run pytest tests/test_rules_engine.py tests/test_policy.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement the three modules, and write `rules.json` by translating repo-root `policy.py`'s `_queue` rule for rule:
  - Mentions are `any` of `issue_type` / `secondary_issue` equal to a value.
  - R04 is `all` of `issue_type == "refund_request"` and `any(amount_usd > 500, days_since_charge > 30)`.
  - R13 has `when: null`.
- [ ] **Step 4:** Run the tests. Expected: PASS, with all 550 records matching.
- [ ] **Step 5: Commit** `feat(server): add policy model, rules engine and question builder`.

### Task 6: Contracts and adapters

**Files:**
- Create:
  - `src/system1/contracts/decisions.py`, `datasets.py`, `evaluation.py`, `training.py`, `llm.py`
  - `src/system1/adapters/jev_typesafe.py`, `sys1_http.py`, `fakes.py`, `jsonl_dataset.py`, `eval_files.py`, `anthropic_llm.py`
  - `src/system1/providers.py`
  - `tests/test_providers.py`

**Interfaces:**
- Produces:
  - **`decisions.py`:**
    - `DecisionRequest(model: str, state: str | dict | list, questions: dict[str, dict])`
    - `ChoiceAnswer(type: Literal["choice"], choice: str, confidence: float | None = None, probabilities: dict[str, float])`
    - `DecisionResponse(model: str, answers: dict[str, ChoiceAnswer], usage: dict | None = None, latency_ms: float)`
    - `class DecisionProvider(Protocol)` with `name: str` and `async def decide(self, req: DecisionRequest) -> DecisionResponse`
    - `ProviderError(Exception)` with `retryable: bool`, `user_message: str` and `status: int | None`
  - **`datasets.py`:** `DatasetRow(id, split: Literal["train","cal","test"], state, questions: dict, gold: dict[str, str], metadata: dict = {})` and `class DatasetSource(Protocol)` with `def rows(self, split: str | None = None) -> list[DatasetRow]`.
  - **`evaluation.py`:** `EvalRecord(id, question, pred, gold, confidence: float | None, p_gold: float | None, correct: bool)`, `EvalRun(model_key, label, summary: dict, records: list[EvalRecord], is_fixture: bool)` and `class EvalResultsSource(Protocol)` with `def runs(self) -> list[EvalRun]`.
  - **`training.py`:** `TrainingJob(id, status: Literal["queued","running","succeeded","failed","unavailable"], message: str, adapter_ref: str | None = None, metrics: dict = {})` and `class Trainer(Protocol)` with `start(dataset_ref: str, config: dict) -> TrainingJob` and `status(job_id: str) -> TrainingJob`.
  - **`llm.py`:**
    - `TextDelta(text)` and `TurnComplete(content: list[dict], stop_reason: str, input_tokens: int, output_tokens: int)`
    - `class LLM(Protocol)` with `def stream_turn(self, *, system: list[dict], messages: list[dict], tools: list[dict]) -> AsyncIterator[TextDelta | TurnComplete]` and `async def structured(self, *, system: str, prompt: str, schema: type[T], max_tokens: int = 4000) -> tuple[T, int]` (the result and the tokens used)
  - **`TypeSafeJevProvider(base_url, api_key, model)`:**
    - `POST {base_url}/v1/systemone` with a Bearer key, through `httpx.AsyncClient` with a 30 s timeout.
    - Retries 429, 529 and 5xx up to 3 times with exponential backoff.
    - Maps failures to `ProviderError`:
      - no key: "Jev isn't configured on this server"
      - 422: the response's `detail`
      - retries exhausted: "Jev is busy right now. Try again in a moment."
  - **`HttpSys1Provider(base_url, model, api_key: str | None)`:** the same request and response shape as Jev, so it works with any Jev-compatible server such as `laya-serve`.
  - **`fakes.py`:**
    - `FakeDecisionProvider(name, model_label)` deterministically picks the first option whose key appears in the state text, otherwise the first option. Probabilities are 0.9 for the chosen option and the rest split evenly.
    - `FakeLLM(script: list[...])` replays scripted turns and structured results.
    - `FakeTrainer` succeeds on the second `status` call. `UnavailableTrainer` always returns `status="unavailable"` with "Training isn't connected yet. The training pipeline runs separately for now."
  - **`JsonlDatasetSource(path)`** and **`EvalFilesSource(dir: Path, models: dict[str, str])`:** the second maps a model key to a file prefix, reads `<prefix>_predictions.jsonl` and `<prefix>_summary.json` in the format `eval_common.py` writes, and sets `is_fixture=True` when the summary has `"fixture": true`.
  - **`AnthropicLLM(api_key, model, effort)`** implements `LLM` with the Anthropic SDK, following the `claude-api` skill:
    - streaming
    - `output_config={"effort": effort}`
    - server-side fallbacks
    - structured output through `messages.parse`
  - **`providers.py`:** `@dataclass Providers(jev: DecisionProvider, sys1: DecisionProvider | None, llm: LLM, trainer: Trainer)`. `build_providers(settings) -> Providers` chooses from the settings switches, and the `get_providers(request)` dependency reads `app.state.providers`.

- [ ] **Step 1: Write the failing tests:**
  - `test_fake_and_jev_adapter_parse_the_same_response`: an `httpx.MockTransport` returns the Jev response JSON from `docs/reference/jev-api.md`. The adapter returns a `DecisionResponse` with `answers["queue"].choice == "billing_refunds"` and `model == "jev-1.13.0"`, matching the fake's response type.
  - `test_jev_429_then_success_retries`: the transport returns 429, then 200, and the result is a success.
  - `test_jev_without_key_raises_provider_error_with_message`: covers Review Focus 3.
  - `test_jev_live_smoke`, marked `@pytest.mark.live`: one real call with the Tallyfern policy question on a short ticket. It asserts the answer is one of the option keys.
- [ ] **Step 2:** Run `uv run pytest tests/test_providers.py -q`. Expected: FAIL.
- [ ] **Step 3:** Implement the contracts, adapters and `providers.py`. `create_app` builds providers in its lifespan and stores them on `app.state`.
- [ ] **Step 4:** Run `uv run pytest -q`. Expected: PASS, with the live test skipped.
- [ ] **Step 5: Commit** `feat(server): add decision, dataset, eval, trainer and llm contracts with adapters`.

### Task 7: Templates and the flagship project's assets

**Files:**
- Create: `src/system1/templates/catalog.py`, `src/system1/templates/data/gallery.json`, `src/system1/templates/data/tallyfern/{policy.json, jev_questions.json, samples.jsonl, eval/…}`, `app/server/scripts/build_flagship.py`, `tests/test_templates.py`

**Interfaces:**
- Consumes: `Policy` (Task 5), `DatasetRow` and `EvalRun` (Task 6).
- Produces:
  - **`Template`:**
    - `id`, `name`, `summary`, `fit: Literal["good","workable","poor"]`, `fit_reasons: list[str]`
    - `policy: Policy`, `sample_inputs: list[str]`
    - `flagship: FlagshipAssets | None`, where `FlagshipAssets` is `samples_path`, `eval_dir`, `eval_models: dict[str, str]`, `jev_questions_path` and `model_label`
  - `load_templates() -> list[Template]` and `get_template(template_id) -> Template` (raising `KeyError` if unknown).
  - **`gallery.json`** holds the 10 use cases from the spec's gallery table. Each has 3–6 options, 2–3 rules and 3 sample inputs, written by the implementer in plain business language. Refund approval and Tallyfern triage come first.
  - **`scripts/build_flagship.py`** runs with the repo-root `.venv` (`.venv/bin/python app/server/scripts/build_flagship.py`). It reads `data/policy/*`, `data/raw/*`, the dataset parquet and `results/triage/*`:
    - It prefers `data/build/triage.parquet` and falls back to `triage_provisional.parquet`. It writes 60 `test`-split rows to `samples.jsonl` as `DatasetRow`, with metadata `difficulty`, `rule_id` and `source` (`provisional` or `final`).
    - It writes `policy.json`: the Tallyfern inputs, the 13 options from `questions.json` (names plus covers and excludes), and `rules.json` from Task 5.
    - It writes `jev_questions.json` using phase 1's `load_questions("terse")` and `load_questions("policy")`, so the flagship's Jev lane asks the same question as the benchmark.
    - It copies triage eval results if they exist. Otherwise it writes fixture files with `"fixture": true` for the model keys `sys1`, `jev_policy`, `jev_labels` and `base`.

- [ ] **Step 1: Write the failing test** `test_templates_load_and_policies_are_valid`. There are 10 templates, `validate_policy` returns no issues for any of them, and Tallyfern has a `flagship` with an existing `samples_path`.
- [ ] **Step 2:** Run it. Expected: FAIL.
- [ ] **Step 3:** Implement `catalog.py` and the script, run the script, write `gallery.json`, and commit the generated data. The data is synthetic.
- [ ] **Step 4:** Run `uv run pytest -q`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(server): add use-case gallery and flagship template assets`.

### Task 8: Projects, policy versions, decision log, and the Try service

**Files:**
- Create:
  - `src/system1/projects/{models.py, schemas.py, service.py, router.py}`
  - `src/system1/decisions/{models.py, service.py}`
  - `src/system1/gateway/{service.py, router_app.py}`
  - `tests/test_projects_and_try.py`

**Interfaces:**
- Consumes: `get_principal` (Task 4), `Policy`, `validate_policy` and `build_questions` (Task 5), `Providers` (Task 6), and the templates (Task 7).
- Produces:
  - **Tables:**
    - `Project`: `id` (uuid str), `org_id`, `name`, `description`, `template_id`, `stage` (default `"usecase"`), `default_lane` (`jev|sys1|auto`, default `jev`), `live_model_label` (null), `created_by`, `created_at`
    - `PolicyVersion`: `id`, `project_id`, `version` (int), `policy_json`, `created_by`, `created_at`
    - `Decision`: `id`, `org_id`, `project_id`, `source` (`playground|api|agent`), `lane` (`jev|jev_labels|sys1`), `model_reported`, `state_json`, `answers_json`, `top_label`, `top_prob`, `latency_ms`, `input_tokens`, `policy_version`, `not_for_training`, `needs_review`, `dataset_row_id` (null), `created_at`
  - **Service** (every function takes `session` and `principal`, and filters by `principal.org_id`):
    - `create_project(name, template_id=None, description=None) -> Project`. A template's policy becomes version 1.
    - `list_projects()`
    - `get_project(project_id) -> Project`, which raises `NotFound` (404) when the project belongs to another org
    - `current_policy(project) -> tuple[Policy, int]`
    - `save_policy(project, policy) -> int`, which raises `PolicyInvalid(issues)` (422 with the issues) and leaves the stored policy unchanged
  - **Gateway service:**
    - `questions_for(project, policy, lane) -> dict` uses the flagship's `jev_questions.json` for the Tallyfern template, and `build_questions` otherwise. The `jev` lane uses the policy variant, `jev_labels` the labels variant, and `sys1` the labels variant.
    - `run_lane(session, providers, project, state, lane, source) -> LaneResult(lane, label, probabilities, model, latency_ms, decision_id, error: str | None)` raises `InputTooLong` (422, "This input is N characters. The limit is 6000.") and logs a `Decision` with `not_for_training = lane.startswith("jev")`.
    - `try_input(session, providers, project, text_or_state, sample_id=None) -> TryResult(results: list[LaneResult], gold: str | None, rule_id: str | None, recorded: dict[str, str])`. It runs `jev_labels` and `jev` concurrently, and `sys1` if it's configured. For a flagship sample it:
      - attaches the gold label and the rule
      - attaches recorded predictions from `EvalFilesSource`, which the UI labels "recorded"
      - sets `dataset_row_id = sample_id` on the logged decisions
  - **Routes:**
    - `GET/POST /api/projects` and `GET/PATCH/DELETE /api/projects/{id}`. DELETE needs `org_role == "admin"`.
    - `GET/PUT /api/projects/{id}/policy`. GET returns `PolicyOut(policy, version, issues: list[PolicyIssue])`.
    - `GET /api/templates`
    - `GET /api/projects/{id}/samples`, which returns flagship test rows without their gold labels; the labels are revealed after Try
    - `POST /api/projects/{id}/try`, with body `{text?: str, sample_id?: str}`

- [ ] **Step 1: Write the failing tests** (fake providers, `client_for`):
  - `test_project_from_template_gets_policy_v1`
  - `test_other_org_gets_404_for_project_and_policy`: covers Review Focus 1.
  - `test_invalid_policy_put_returns_422_and_keeps_old_version`: covers Review Focus 4.
  - `test_try_returns_both_jev_lanes_and_logs_not_for_training`
  - `test_try_rejects_oversized_input_with_limit_message`: covers Review Focus 5.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement. Register the routers in `create_app`.
- [ ] **Step 4:** Run `uv run pytest -q` and `make docs`. Expected: PASS, and the regenerated `schema.d.ts` includes the new paths.
- [ ] **Step 5: Commit** `feat(server): add projects, policy versions, decision log and try`.

### Task 9: Client: dashboard, workspace, Rules canvas, Try playground

**Files:**
- Create:
  - `src/features/dashboard/DashboardPage.tsx`, `TemplateCard.tsx`, `NewProjectDialog.tsx`
  - `src/features/workspace/WorkspacePage.tsx`, `StageRail.tsx`, `stages.ts`
  - `src/features/rules/RulesCanvas.tsx`, `InputsPanel.tsx`, `OptionsPanel.tsx`, `RulesPanel.tsx`
  - `src/features/usecase/UseCaseCanvas.tsx`
  - `src/features/playground/TryCanvas.tsx`, `ResultRow.tsx`
- Modify: `src/app/routes.tsx`

**Interfaces:**
- Consumes: `useApi()` (Task 2) and the API from Task 8.
- Produces:
  - **Routes:**
    - `/app` is the dashboard: the org's projects plus the template gallery, with fit badges and "Use this template". Its "Describe your own" and "Help me find one" buttons both create a blank project; the first message is sent in Task 12.
    - `/app/p/:projectId/:stage` is the workspace. `stage` is one of `usecase|rules|try|examples|train|use|improve`, defined once in `stages.ts` with plain labels.
  - **Use case canvas:** the project name and decision question (both editable through PATCH and PUT), the template summary, and the latest fit rating once the agent gives one (Task 12).
  - **Workspace layout:** a stage rail on top, the agent panel on the left (an empty placeholder until Task 12) and the canvas on the right. On narrow screens it shows one panel at a time with a toggle.
  - **Rules canvas:** edit inputs, options (name, covers, excludes) and rules (text, label select, up/down reorder, a "testable" or "needs judgment" badge from `when`). Save calls `PUT /policy`. A 422 shows the issues inline and keeps the user's edits.
  - **Try canvas:**
    - a text box and a "Sample from test set" select (flagship only)
    - one result row per lane, with the answer, a "how sure" bar from the top probability, and the time
    - "Correct by your rules: X (R04)" for samples
    - recorded rows badged "recorded"
    - errors shown in the row
    - Try disabled while the policy has issues
  - **Copy:** follows the Global Constraints' plain-words rule.

- [ ] **Step 1:** Implement the pages and components.
- [ ] **Step 2:** Run `make -C app check` and `bun run build`. Expected: both pass.
- [ ] **Step 3: Commit** `feat(client): add dashboard, workspace, rules canvas and try playground`.

### Gate G2: click-through (Thomas, about 15 minutes)

**Before testing**, in the Clerk dashboard:
- Organizations are enabled with **Membership required**, which is the B2B option you chose.
- Email and Google sign-in are on.

**Steps:**
1. Run `make dev`, then open http://localhost:5173.
2. Click **Sign up**, create an account, then create an organization called "Acme Support" in the choose-organization step. Expected: you land on `/app` with Acme Support in the org switcher.
3. Open the switcher, create a second org, and confirm its project list is empty. Switch back to Acme Support.
4. Open **Team**. Expected: Clerk's organization profile, where you can invite a teammate by email.
5. Click **Use this template** on **Tallyfern triage**. Expected: the workspace opens, and the Rules stage shows 13 options and 13 rules.
6. On **Try**, pick a sample ticket and press Try. Expected:
   - two Jev rows with real answers, each with a "how sure" bar
   - the correct answer and its rule
   - sys1 shown as "recorded", with the sample-numbers banner while fixtures are in use
7. Paste a 7,000-character text. Expected: a clear limit message.
8. On Rules, edit one rule's text and save, then reload. Expected: the edit persists. Then change a rule's label to something that isn't an option. Expected: an inline error, and nothing saved.

**Report back:** anything broken, plus wording you'd change.

**From you:** nothing else. Your keys are already in `.env`.

---

## Phase B: agent, API keys, feedback, skill (Block B, ending at Gate G3)

### Task 10: Agent server: events, tools, streaming loop, persistence

**Files:**
- Create: `src/system1/agent/{events.py, tools.py, loop.py, prompts.py, models.py, router.py}`, `tests/test_agent.py`

**Interfaces:**
- Consumes: `LLM` (Task 6), `save_policy`, `current_policy` and `try_input` (Task 8), `check_budget` and `record_usage` (Task 4).
- Produces:
  - **`events.py`:** `AgentEvent`, a Pydantic discriminated union on `type`:
    - `text{delta}`
    - `tool{name, status: started|done|error, summary}`
    - `choices{question, options: list[str]}`, with 2 to 4 options
    - `fit{rating, reasons}`
    - `canvas{policy: Policy, version: int, changed: list[str]}`
    - `try_result{input, result: TryResult}`
    - `confirm{action_id, kind: Literal["dataset","training"], title, detail, est_minutes, est_cost_usd}`
    - `stage{stage}`
    - `error{message}`
    - `done{}`
  - **Tables:**
    - `AgentTurn`: `id`, `project_id`, `org_id`, `seq`, `role`, `api_content_json` (content blocks stored exactly as returned, append-only, for replay), `ui_events_json`, `created_at`
    - `PendingAction`: `id`, `project_id`, `org_id`, `kind`, `params_json`, `status` (`pending|confirmed|cancelled`), `created_at`
  - **`AgentContext`:** a dataclass of `session`, `principal`, `providers`, `settings` and `project`, passed to the tools and the loop.
  - **Action handlers:** `register_action_handler(kind: str, handler: Callable[[AgentContext, PendingAction], Awaitable[dict]])`. The confirm route calls the handler for the action's kind. A kind with no handler gets 409 "Not available yet". Task 15 registers `training` and Task 16 registers `dataset`.
  - **`tools.py`:** tool definitions built from Pydantic input models, plus `execute_tool(name, args, ctx) -> tuple[str, list[AgentEvent]]`, which returns the tool result text for the model and the events for the UI. The tools are:
    - `show_choices(question, options)`
    - `show_fit(rating, reasons)`
    - `search_use_cases(query)`
    - `set_inputs(inputs)`, `set_options(options)` and `set_rules(rules)`, which validate the whole resulting policy and on issues return an error result listing them, with the policy unchanged
    - `try_decision(input)`
    - `request_dataset(count: int ≤ 50)` and `request_training()`, which only create a `PendingAction` and emit `confirm`
    - `go_to_stage(stage)`
  - **`prompts.py`:** `system_blocks(settings) -> list[dict]` loads `playbook_path` as a cached system block, and `canvas_message(policy, version, stage) -> dict` builds the current canvas as a mid-conversation system message.
  - **`loop.py`:** `run_agent_turn(ctx, user_text) -> AsyncIterator[AgentEvent]`. It:
    - calls `check_budget`
    - appends the user turn plus the canvas system message
    - loops `stream_turn` → stream text deltas → execute tools → append results, with at most 8 tool rounds per message
    - adds the canvas message again after tool results whenever the canvas changed
    - records usage, persists turns, and ends with `done`
    - emits a recoverable `error` event on a `ProviderError` or `BudgetExceeded`
  - **Routes:**
    - `POST /api/projects/{id}/agent/messages`, with body `{text}`, returns `text/event-stream` (each event is `event: <type>` plus `data: <json>`).
    - `GET /api/projects/{id}/agent/history` returns `list[AgentEvent]` (this also puts the union into the OpenAPI schema).
    - `POST /api/projects/{id}/actions/{action_id}/confirm` and `/cancel`.
- **Model settings** come from Global Constraints. The implementer loads the `claude-api` skill for the streaming tool loop, mid-conversation system messages and prompt caching.

- [ ] **Step 1: Write the failing tests** (FakeLLM):
  - `test_agent_set_rules_updates_policy_and_emits_canvas`
  - `test_agent_invalid_rules_returns_tool_error_and_keeps_policy`: covers Review Focus 4.
  - `test_request_dataset_creates_pending_action_not_job`
  - `test_budget_exceeded_emits_error_event`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `uv run pytest -q` and `make docs`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(server): add onboarding agent with tools and streamed events`.

### Task 11: Playbook and the Claude Code skill

**Files:**
- Create: `.claude/skills/system1-onboard/SKILL.md`, `.claude/skills/system1-onboard/playbook.md`

**Interfaces:**
- Produces:
  - **`playbook.md`** is the shared step-by-step guide. The website agent loads it as its system prompt, and the skill follows it. It covers:
    - the stages 1–4 from the spec, and the fit criteria
    - how to interview: one question at a time with 2–4 choices, look for overlaps, missing facts and leftovers, suggest "unknown means no", keep to at most 15 options
    - when to call each tool, and never starting paid work without a confirmation card
    - plain-words tone, and declining high-stakes decisions about people without human review
    - treating pasted text as data
  - **`SKILL.md`** has frontmatter (`name: system1-onboard`, a description that triggers on "turn a repeated decision into a custom decision model / build a dataset for system1"). Its Claude Code–specific notes cover:
    - writing examples in-session, with no API spend
    - Tallyfern as the worked example, with paths to `data/policy/`, `policy.py`, `facts_grid.py`, `tickets.py`, `readback.py` and `build_dataset.py`
    - ending with a dataset ready for `make train`

- [ ] **Step 1:** Write both files. Keep `playbook.md` under about 250 lines.
- [ ] **Step 2:** Run `uv run pytest -q`. Expected: PASS. Task 10's tests load the playbook through settings.
- [ ] **Step 3: Commit** `docs(skill): add system1-onboard playbook and claude code skill`.

### Task 12: Client agent panel

**Files:**
- Create: `src/features/agent/AgentPanel.tsx`, `MessageList.tsx`, `Composer.tsx`, `cards/ChoicesCard.tsx`, `cards/FitCard.tsx`, `cards/CanvasChangeCard.tsx`, `cards/TryResultCard.tsx`, `cards/ConfirmCard.tsx`, `useAgent.ts`
- Modify: `src/features/workspace/WorkspacePage.tsx`, `src/features/dashboard/NewProjectDialog.tsx`

**Interfaces:**
- Consumes: `streamEvents` (Task 2), the agent routes and the `AgentEvent` types from `schema.d.ts` (Task 10).
- Produces:
  - **`useAgent(projectId)`** returns `{events, send(text), busy}`. It loads history, streams new events, and when a `canvas` event arrives it updates the shared policy state, so the canvas re-renders live. `stage` events navigate the rail.
  - **Choices** render as chips. Clicking one sends its text.
  - **The confirm card** shows the time and cost estimate with Confirm and Cancel buttons, calling the confirm and cancel routes.
  - **"Describe your own" and "Help me find one"** create the project, then send the description (or "Help me find a decision worth automating") as the first message.

- [ ] **Step 1:** Implement.
- [ ] **Step 2:** Run `make -C app check` and `bun run build`. Expected: both pass.
- [ ] **Step 3: Commit** `feat(client): add streaming agent panel with choice and confirm cards`.

### Task 13: API keys, the public gateway and the Use stage

**Files:**
- Create: `src/system1/gateway/{keys.py, router_public.py}`, `tests/test_gateway_public.py`, `src/features/use/UseCanvas.tsx`, `src/features/use/snippets.ts`
- Modify: `src/system1/gateway/router_app.py`

**Interfaces:**
- Consumes: `run_lane` (Task 8).
- Produces:
  - **The `ApiKey` table:** `id`, `org_id`, `project_id`, `prefix` (the first 8 characters), `hash` (sha256), `created_by`, `created_at`, `revoked_at`.
  - **Key functions:** `create_key(session, principal, project) -> tuple[ApiKey, str]` returns the plaintext once, formatted `s1_` + 32 url-safe characters. `resolve_key(session, raw) -> ApiKey | None` ignores revoked keys.
  - **App routes:** `GET/POST /api/projects/{id}/keys` and `DELETE /api/projects/{id}/keys/{key_id}`.
  - **Public routes:**
    - `POST /v1/systemone`, with Bearer project key and a body in Jev's request shape where `questions` is optional and `model` is one of `jev-1.13.0|sys1|auto` or defaults to the project's `default_lane`.
    - It returns Jev's response shape plus `system1: {decision_id, routed_to, policy_version, latency_ms}`.
    - `auto` sends to sys1, and falls back to `jev` when the top probability is below `auto_threshold` or sys1 isn't configured. When sys1 was unsure, it sets `needs_review = True`.
    - `POST /v1/feedback` takes `{decision_id, correct: {question: label}}`.
  - **The Use canvas:**
    - The endpoint URL comes from `window.location.origin`.
    - Create, copy and revoke keys. The plaintext is shown once.
    - A model picker (Jev with your rules / Your model / Auto) saves `default_lane`. "Your model" and "Auto" are disabled, with a tooltip, when sys1 isn't connected.
    - curl, Python and JavaScript snippets.

- [ ] **Step 1: Write the failing tests:**
  - `test_public_decide_with_key_returns_system1_block`
  - `test_revoked_key_gets_401`
  - `test_key_for_project_a_cannot_decide_for_project_b`: covers Review Focus 1.
  - `test_auto_falls_back_to_jev_and_flags_review_when_sys1_unsure`: uses a fake sys1 with a top probability of 0.5.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement the server and the Use canvas, then run `make docs`.
- [ ] **Step 4:** Run `uv run pytest -q`, `make -C app check` and `bun run build`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: add project api keys, public gateway with auto routing and use page`.

### Task 14: Feedback and the Improve inbox

**Files:**
- Create: `src/system1/decisions/router.py`, `tests/test_feedback.py`, `src/features/improve/ImproveCanvas.tsx`
- Modify: `src/system1/decisions/{models.py, service.py}`, `src/features/playground/ResultRow.tsx`

**Interfaces:**
- Consumes: the `Decision` table and Task 8's service.
- Produces:
  - **The `Feedback` table:** `id`, `decision_id`, `org_id`, `kind` (`confirm|correction`), `correct_label`, `user_id`, `is_test_item`, `training_eligible`, `created_at`.
  - **`record_feedback(session, principal, decision_id, kind, correct_label) -> Feedback`:**
    - `is_test_item` is true when the decision's `dataset_row_id` is in the test split.
    - `training_eligible = not is_test_item and (decision.lane == "sys1" or kind == "correction")`, so a confirmed Jev answer never becomes a label.
  - **`inbox(session, principal, project) -> list[Decision]`** returns decisions with `needs_review`, or with a correction pending. **`training_pool_count(...) -> int`** counts eligible feedback.
  - **Routes:** `POST /api/decisions/{id}/feedback`, `GET /api/projects/{id}/inbox` and `GET /api/projects/{id}/training-pool`.
  - **Client:**
    - ✓ / ✗ on Try results. ✗ opens an option picker.
    - The Improve canvas lists the inbox with one-click correction, and shows "N new answers since your last training". Task 15 adds the Retrain button.

- [ ] **Step 1: Write the failing tests:**
  - `test_feedback_on_test_item_is_never_training_eligible`
  - `test_confirming_a_jev_answer_is_not_training_eligible`
  - `test_other_org_cannot_post_feedback`: covers Review Focus 1.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement, then run `make docs`.
- [ ] **Step 4:** Run `uv run pytest -q`, `make -C app check` and `bun run build`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: add feedback, improve inbox and training pool count`.

### Gate G3: agent and API check (Thomas, about 20 minutes)

1. On the dashboard, use **Refund approval**, or **Describe your own** with something like "we decide whether to approve refund requests". Expected:
   - The agent streams its replies.
   - Its questions come with clickable chips.
   - Answering updates the Rules canvas live.
   - A fit card appears.
   - It asks about at least one overlap or missing fact.
2. Ask the agent to "try it on a $700 refund from last week". Expected: a try-result card from Jev.
3. Ask it to "generate examples". Expected: a confirmation card with time and cost. Press **Cancel**: nothing should run.
4. On **Use**, create a key, copy the curl snippet and run it in a terminal. Expected: JSON that includes `system1.decision_id`. Revoke the key and run it again. Expected: 401.
5. On **Try**, mark an answer ✗ and pick the right option. Expected: it appears in **Improve**, and the counter goes up. A test-set sample shouldn't increase it.
6. In a fresh Claude Code session in this repo, ask "help me set up a decision model for refund approvals". Expected: the `system1-onboard` skill triggers.

**Report back:** the agent's tone, and any questions it should or shouldn't ask.

**From you:** a quick look at Anthropic usage in the console. A full onboarding conversation should cost well under $1.

---

## Phase C: report card, examples, training contract, deploy (Block C, ending at Gates G4 and G5)

### Task 15: Report card and the Train stage

**Files:**
- Create: `src/system1/report/{stats.py, service.py, router.py}`, `src/system1/training_router.py`, `tests/test_report.py`, `src/features/report/TrainCanvas.tsx`, `ReportCard.tsx`, `DetailsDrawer.tsx`
- Modify: `src/features/improve/ImproveCanvas.tsx` (add the Retrain button, which calls the training route and shows the trainer's message)

**Interfaces:**
- Consumes: `EvalResultsSource` and `Trainer` (Task 6), and the flagship assets (Task 7).
- Produces:
  - **`stats.py`:**
    - `accuracy_ci(correct: list[bool], n_boot=2000, seed=0) -> tuple[float, float, float]` returns the accuracy and its 95% bootstrap interval.
    - `paired_diff_ci(a: list[bool], b: list[bool], n_boot=2000, seed=0) -> tuple[float, float, float]`, where items are matched by id.
    - `per_option_accuracy(records) -> dict[str, float]` and `top_confusions(records, k=3) -> list[tuple[str, str, int]]`.
  - **`report(project) -> Report`:**
    - `rows`: one per model key, in the order sys1, jev_policy, jev_labels, base. Each row has its label, accuracy, CI, n, and median latency and cost per 1,000 decisions when the summary has them.
    - `per_option`, `confusions` and `is_fixture`.
    - `verdict: {winner: "sys1"|"jev_policy"|"inconclusive", diff, ci, sentence}` from `paired_diff_ci(sys1, jev_policy)`. sys1 wins when the interval's lower bound is above 0, and Jev wins when the upper bound is below 0.
  - **Routes:**
    - `GET /api/projects/{id}/report`. Projects without eval results get `{"available": false}`.
    - `POST /api/projects/{id}/training` and `GET /api/projects/{id}/training/{job_id}` go through `Trainer`. In production `UnavailableTrainer` returns its honest message.
    - This task registers the `training` action handler (Task 10), so a confirmed training card calls the same code.
  - **The Train canvas:**
    - The report card with plain labels and bars, and the sample-numbers banner when `is_fixture`.
    - The verdict sentence, then "Switch my endpoint to my model" (sets `default_lane="sys1"`, only when sys1 is connected) or "Use auto".
    - The Details drawer shows the CIs, n and the confusions.
    - For non-flagship projects, a "Train my model" button that goes through the trainer.

- [ ] **Step 1: Write the failing tests:**
  - `test_accuracy_ci_brackets_point_estimate`
  - `test_verdict_inconclusive_when_interval_spans_zero`
  - `test_report_flags_fixture_results`
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement, then run `make docs`.
- [ ] **Step 4:** Run `uv run pytest -q`, `make -C app check` and `bun run build`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: add report card with verdict and train stage behind trainer contract`.

### Task 16: Example generation pipeline and the Examples stage

**Files:**
- Create: `src/system1/examples/{models.py, sampler.py, writer.py, readback.py, pipeline.py, router.py}`, `tests/test_examples.py`, `src/features/examples/ExamplesCanvas.tsx`

**Interfaces:**
- Consumes: `evaluate`, `thresholds` and `is_fully_testable` (Task 5), `LLM.structured` (Task 6), and `PendingAction` (Task 10).
- Produces:
  - **Tables:**
    - `Job`: `id`, `org_id`, `project_id`, `kind`, `status` (`running|succeeded|failed`), `progress` (0–1), `message`, `result_json`, `created_at`
    - `ExampleRow`: `id`, `project_id`, `dataset_version`, `split`, `facts_json`, `text`, `label`, `rule_id`, `readback_ok`, `review` (`agree|disagree|null`)
  - **`sample_facts(policy, count, seed) -> list[dict]`** spreads examples across options, using rejection sampling over the input domains with values pulled toward `thresholds`. It caps attempts at `count * 200` and returns what it found.
  - **`write_texts(llm, policy, facts_batch) -> list[str]`** does batches of 10. The prompt forbids naming any option key or name. **`leak_check(text, policy) -> bool`** returns false if any option key or name appears.
  - **`read_back(llm, inputs, texts) -> list[dict]`** extracts facts from the text and the input schema only, never the policy or the label.
  - **`start_generation(session_factory, providers, settings, org_id, project_id, count) -> str`** returns the job id and runs the pipeline as an in-process asyncio task with its own session. The steps:
    1. sample
    2. write
    3. leak check
    4. read back
    5. keep an example only when `evaluate(extracted)` gives the same label
    6. split deterministically into 60/10/30
    7. store, updating `progress` along the way
  - **Labels** always come from `evaluate` on the sampled facts. If `is_fully_testable` is false, generation is refused with: "Some rules need judgment, so examples can't be labelled automatically yet."
  - **This task registers the `dataset` action handler** (Task 10), which calls `start_generation`.
  - **Routes:** `GET /api/projects/{id}/examples`, which returns the health summary (counts per option, read-back pass rate, split sizes) and 20 random rows for spot-checking. `POST /api/examples/{row_id}/review` records a review, and `GET /api/jobs/{id}` returns job status.
  - **The Examples canvas** shows the source picker with only "Generate from my rules" active (CSV upload is labelled "coming soon"), a count of up to 50, the job progress bar, the health panel with a lock icon on test, and agree/disagree buttons on the spot-check rows.

- [ ] **Step 1: Write the failing tests** (FakeLLM):
  - `test_sampled_facts_route_to_every_option`, using the Refund approval template.
  - `test_leaky_text_is_dropped`.
  - `test_readback_mismatch_is_dropped_and_labels_come_from_rules`.
  - `test_generation_refused_when_rules_need_judgment`.
- [ ] **Step 2:** Run them. Expected: FAIL.
- [ ] **Step 3:** Implement, then run `make docs`.
- [ ] **Step 4:** Run `uv run pytest -q`, `make -C app check` and `bun run build`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: add rule-labelled example generation with read-back check`.

### Gate G4: decision gate (Thomas, about 20 minutes)

1. Open **Train** on the Tallyfern project. Expected: the report card, with the sample-numbers banner until the real triage results exist.
   - When the real results land in `results/triage/` (written by `eval_common.py`, with prefixes `sys1`, `jev_policy`, `jev_labels` and `base`), rerun `.venv/bin/python app/server/scripts/build_flagship.py`, then reload. Expected: real numbers and no banner.
   - If the prefixes Nicholas uses differ, tell Claude. It's a one-line mapping in `eval_models`.
2. In the Refund project, go to **Examples**, generate 20 and confirm. Expected: a progress bar, then the health panel and 20 spot-check rows. Agree with or disagree with a few.
3. Press **Train my model** on a non-flagship project. Expected: an honest "training isn't connected yet" message.
4. If a real sys1 endpoint exists by now, add `SYS1_PROVIDER=http`, `SYS1_BASE_URL=…` and `SYS1_MODEL=…` to `.env` and restart. Expected:
   - **Try** shows a live "Your model" row.
   - **Use** lets you pick Your model or Auto.
   - Without a real endpoint, `SYS1_PROVIDER=fake` shows the flow for testing only, and must stay off for the demo.

**Decide:** which demo story to tell, based on the real results.

### Task 17: Deploy to Modal

**Files:**
- Create: `app/server/modal_app.py`
- Modify: `app/Makefile` (targets `build-client`, `deploy`, `serve-modal`), `src/system1/main.py` (serve `static_dir` with an SPA fallback to `index.html` for any non-`/api` or `/v1` path)

**Interfaces:**
- Produces:
  - **`modal_app.py`:**
    - `app = modal.App("system1")`.
    - The image is `debian_slim(python_version="3.12")` plus `uv_pip_install(<server deps>)`, plus `add_local_python_source("system1")` (or `add_local_dir` of the package), plus `add_local_dir("app/client/dist", "/assets/client")` and `add_local_file(<playbook>, "/assets/playbook.md")`.
    - `volumes={"/data": modal.Volume.from_name("system1-data", create_if_missing=True)}`, `secrets=[modal.Secret.from_name("system1-env")]`, `max_containers=1` (one writer for SQLite) and `min_containers=1` (warm for judging).
    - It's decorated with `@modal.concurrent(max_inputs=50)` and `@modal.asgi_app()`, returning `create_app()`.
    - Environment overrides: `DATABASE_URL=sqlite:////data/system1.db`, `STATIC_DIR=/assets/client` and `PLAYBOOK_PATH=/assets/playbook.md`.
  - **Make targets:** `build-client` runs `bun run build`. `deploy` runs build-client, then `modal deploy app/server/modal_app.py`. `serve-modal` runs `modal serve`, a temporary URL for checking.
  - The implementer checks the current Modal API (`min_containers`, `max_containers`, the image methods and `Secret.from_dotenv`) against the installed `modal` package.

- [ ] **Step 1:** Implement the static serving, `modal_app.py` and the make targets.
- [ ] **Step 2:** Run `make -C app build-client` and `uv run pytest -q`. Expected: both pass.
- [ ] **Step 3: Commit** `feat(deploy): serve client and server from one modal app`.
- [ ] **Step 4: Stop.** Deploying is an external side effect, so Thomas runs Gate G5.

### Gate G5: deploy and rehearse (Thomas, 1–2 hours including the video)

1. Create the Modal secret from your `.env`, for example `modal secret create system1-env --from-dotenv .env`. Claude confirms the exact flag first. Add `CLIENT_ORIGINS` with the deployed URL (`["https://<your-workspace>--system1-….modal.run"]`) to that secret after the first deploy, then redeploy.
2. Run `make deploy`, then open the printed URL.
3. Sign in on the deployed URL. Clerk's development instance works for the hackathon; if sign-in fails there, tell Claude, since you may need to add the URL in Clerk's dashboard.
4. Run the whole demo once: sign up → organization → Refund approval with the agent → Try → Use (curl against the live URL) → Tallyfern Try and Train → Improve.
5. Record the video, following the spec's storyboard.

**From you:**
- approval to deploy
- the Modal secret
- the Clerk dashboard tweak if sign-in fails on the Modal URL
- the recording

### Task 18: Polish pass

**Files:**
- Modify: client copy and empty states across features, `app/README.md` (create: how to run, the folder map, the contracts, configuration)

**Interfaces:**
- Produces:
  - **Empty states** for no projects, no inbox items, no results and no keys.
  - **Loading skeletons**, plus toasts for errors that use the server's messages.
  - **Every number** checked against the Global Constraints' copy rule: no unlabelled placeholder numbers.
  - **The landing page** gets a final copy pass.
  - **`app/README.md`** covers how to run the app, the folder map, the four contracts and the configuration.

- [ ] **Step 1:** Do the pass.
- [ ] **Step 2:** Run `make verify`. Expected: all checks pass.
- [ ] **Step 3: Commit** `chore: polish empty states, copy and add app readme`.

---

## Out of scope for this plan (tracked in docs/backlog.md)

- **Training and sys1 serving.** The real trainer adapter, the registry check before going live, retraining from corrections, and serving sys1 with `laya-serve`. These come later through the `Trainer` and `DecisionProvider` contracts.
- **Drift signals** (the share of traffic falling back to Jev, and the average top probability over time).
- **Docker.** It isn't needed: SQLite runs locally, and Modal builds the deployed container.
- **The rule-ID question (S5).** It needs a training change.
- **Roadmap items:** bring-your-history CSV, one-off CSV batch, Era by Eon (V2), SurrealDB Agent Memory (V3), and the Claude connector and MCP server (Future).

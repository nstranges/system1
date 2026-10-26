# system1 UI redesign

Oct 25, 2026 · Thomas Michalski · Status: draft for approval · Branch: `ui-redesign` (off `main`)

The journey ([journey v2](2026-10-22-system1-journey-v2-design.md)) stays as it is: Define → Data → Review → Train → Use ⇄ Improve. This redesign changes how the app looks, how it shows progress through that journey, and how the pitch's key moment (your model against Jev) reads. It adds no model-side behaviour.

## Why

An evaluation of the client on Oct 25 found:

- **The journey has no sense of progress.** The stage rail is six numbered links with no done, current or blocked state. Nothing says Train is blocked until every bucket has 30 examples, and you can land on an empty Improve on day one.
- **No stage hands off to the next one.** Each step's hint is shown twice (tooltip and text). Improve shows its own "Improve" heading under the shared one.
- **The dashboard doesn't say where a project stands.** Cards show a description and created date, with Rename and Delete always visible.
- **The money moment is a plain table.** The report card, which carries the whole bet, is rows of percentages, and one column says "Avg. probability on the right answer", which breaks the "how sure" vocabulary rule.
- **Review isn't fast.** Each card has a "Move to…" dropdown and there are no keyboard shortcuts, for a user who triages all day.
- **It looks like stock shadcn.** Geist, white, neutral greys, one teal accent, and cards inside cards. Nothing about it says decisions or system1.
- **The landing page describes the old journey** ("Write your rules, Try it, …"), uses a split-colour headline and four identical numbered cards, and shows no product.

Submission is due **tonight, Oct 25, at 23:59 ET**, and the demo video comes from this UI, so the work is tiered: Tier 1 is the demo path and has to land; Tiers 2 and 3 are cut first.

## Who and what

The reader is the support-ops lead at a 20–200 person SaaS company, plus two judges scoring UI and design and watching a four-minute video. The primary job of every screen is to answer "where am I, and what do I do next", and on Train, "is my model better than Jev".

## Design direction

**The idea: buckets are coloured bins, and every input that passes through the app wears the colour of the bin it lands in.** A bucket's colour is fixed the moment it's defined and follows it into Data health, Review, Use answers and the Improve inbox. That is the one bold thing; everything around it stays quiet.

A second, quieter distinction: **the customer's words are set in a serif, and the product's words in a sans.** A ticket, an email or a form row reads as someone else's voice, which is exactly what it is.

### Colour

| Token | Light | Dark | Role |
|---|---|---|---|
| `--paper` (background) | `#F2F4F3` | `#14181D` | Cool ledger grey, the page |
| `--card` | `#FFFFFF` | `#1C2228` | Surfaces that hold objects |
| `--ink` (foreground) | `#18212B` | `#EEF1F0` | Text |
| `--muted-ink` | `#5B6670` | `#A3ADB5` | Secondary text |
| `--rule` (border, input) | `#D8DEDB` | `rgb(255 255 255 / 10%)` | Hairlines |
| `--primary` | `#1C5CAB` | `#5598E7` | Actions; the same blue family as the model |
| `--model` | `#2A78D6` | `#3987E5` | Your model in every chart |
| `--jev` | `#EB6834` | `#D95926` | Jev in every chart |

`--model` and `--jev` are slots 1 and 2 of the dataviz skill's validated categorical palette (they're the existing `--series-1/2`). The brand blue is the model's own colour, so the product and its model read as one thing.

**Bucket colours** use that palette's fixed order, light and dark steps as published:

| Slot | Light | Dark |
|---|---|---|
| 1 | `#2a78d6` | `#3987e5` |
| 2 | `#eb6834` | `#d95926` |
| 3 | `#1baf7a` | `#199e70` |
| 4 | `#eda100` | `#c98500` |
| 5 | `#e87ba4` | `#d55181` |
| 6 | `#008300` | `#008300` |
| 7 | `#6250d6` | `#9085e9` |
| 8 | `#e34948` | `#e66767` |

- A bucket's slot is its position in the policy's options.
- Buckets 9 to 15 get no hue: they show a neutral swatch. No ninth colour is ever generated.
- Bucket identity is never carried by colour alone: the colour is a swatch next to the bucket's name, and text stays in ink.
- Deleting a bucket shifts the slots of those after it. Deletes are rare, and the trade is accepted to avoid hash collisions.

### Type

- **Instrument Sans** (variable) for everything the product says: UI, headings, numbers. Use `tabular-nums` wherever numbers sit in columns or change.
- **Newsreader** (variable) for customer input only: sample tickets, sort cards, inbox items, the Try box. Exposed as the `font-voice` utility, at 15px with a 1.6 line height.
- **Scale:** 13 / 15 / 18 / 22 / 28 / 40. The 40 is used only for the Train verdict and the landing headline.
  - Body text is 15px.
  - Stage titles are 28px, weight 600, tracking −0.015em.
  - The verdict and landing headline are 40px (32 on phones), weight 600, tracking −0.02em, max 30ch.
- **Not used:** all-caps labels, eyebrow labels above headings, monospace for small data labels, middle-dot meta strings, "→" on buttons, and one accented word inside a headline.

### Shape

- Radius by hierarchy: chips and swatches 3–4px, controls 6px, panels 10px.
- No shadows on cards. A card is used only for a discrete object (a project, a sort card, a ticket). Sections of a canvas sit on the paper, separated by space and a hairline.

### Layout: the workspace

```
┌──────────────────────────────────────────────────────────────────────────┐
│ system1   Acme ▾                                   Projects  Team   (◐) ●│
├───────────────┬───────────────────────────────────────────┬──────────────┤
│ All projects  │ Define                                    │ Assistant  ⇥ │
│ Refund appr.  │ Say what you're deciding and what the     │              │
│               │ possible outcomes (buckets) are.          │  messages    │
│ ✓ Define      │                                           │              │
│   4 buckets   │  [canvas]                                 │              │
│ ○ Data        │                                           │              │
│   No examples │                                           │  starters    │
│ ⊘ Review      │                                           │  composer    │
│ ⊘ Train       │ ───────────────────────────────────────── │              │
│ ○ Use         │ Next: Data. Add examples of past…         │              │
│ ⊘ Improve     │                       [Continue to Data]  │              │
└───────────────┴───────────────────────────────────────────┴──────────────┘
```

- **Left:** the project name and a vertical stage rail. Each stage shows a status (done, ready or blocked) and a one-line note from the server ("4 buckets", "2 buckets need more examples", "12 to check", "Your model: 91%"). Blocked stages stay clickable but muted.
- **Centre:** the stage title, a single hint line, the canvas, and a "next step" footer once the current stage is done.
- **Right:** the assistant, sticky and full height. It closes to a floating "Assistant" button.
- **Below `lg`:** the rail scrolls horizontally at the top, and the existing Assistant/Workspace toggle stays.
- Everything is left-aligned. The workspace uses the full width (up to 1600px); the dashboard and team pages keep the 6xl column.

### Layout: Train's head-to-head

```
Your model got 91% of your test examples right,
ahead of Jev + your guidelines at 84%.

Your model            ██████████████████████████▌──┤   91%
  120 ms typical
Jev + your guidelines ███████████████████████▏─┤      84%
  880 ms typical
Jev, buckets only     █████████████████──┤            66%
Base model            ███████────┤                    29%
                      0%                         100%
[Show as a table]
```

- The verdict sentence the server already writes becomes the headline.
- One bar per row on a fixed 0–100% axis, with the server's confidence interval drawn as a thin whisker. Your model is in `--model`, both Jev rows in `--jev`, and the base model in muted ink.
- Each row is labelled with its name and value, so no legend is needed. A row with no score shows its message ("Real training connects soon.") in place of a bar.
- The bars grow in once on first render (only when motion is allowed). This is the app's single orchestrated motion.
- The table stays behind "Show as a table", with its third column renamed to **"How sure of the right answer"**.

### Layout: the landing page

```
system1                                                     Sign in
──────────────────────────────────────────────────────────────────
Decisions made the way              ┌ Someone logged into our ─────┐
your team makes them.               │ account!!                    │
                                    │ We just got an alert that…   │
A small model trained on your       └──────────────────────────────┘
team's own calls, behind the same    Your model  ▪ Trust & Safety 85%
API as Jev.                          Jev + rules ▪ Trust & Safety 70%
                                     Sample numbers from the Tallyfern
[Sign up]  [Sign in]                 example project.

Define → Data → Review → Train → Use → Improve   (the six real steps)
```

- **The hero is a real Tallyfern test ticket** (`t0005`) and its recorded answers, captioned as sample numbers, because the flagship's results are still fixtures.
- **The how-it-works row is the actual six-step journey,** numbered because it really is a sequence, using the copy in `stages.ts`.
- **One load moment:** the ticket settles and the two answer rows fill their "how sure" bars, once, only when motion is allowed.

## New behaviour

1. **`GET /api/projects/{project_id}/progress`** returns each stage's status and note, the stage to do next, the example count, and the latest accuracy for your model and Jev. The rail, the next-step footer and the dashboard cards all read it. The rules are in the plan, Task 2.
2. **The next-step footer** appears when the current stage is done: "Next: Data. {hint}" with a **Continue to Data** button.
3. **Dashboard cards** show a six-segment progress strip, the next step or the live model's name, and the latest scores ("Your model 91%, Jev 84%"). Rename and Delete move into a "Project actions" menu.
4. **Keyboard-first Review:**
   - **1–9** sort the focused card into that bucket.
   - **Enter** or **Y** keeps its label.
   - **J/K** or the arrow keys move between cards.
   - The dropdown becomes a row of bucket buttons, each with its digit.
5. **Define's save bar** sticks to the bottom of the screen, and appears only when there are unsaved changes.
6. **Stage-aware starters** on the assistant for every project, not just templates.
7. **A light/dark toggle** in the header.

## Goals, non-goals, anti-goals

- **Goals:** a judge can tell where a project stands and what to do next from any screen. The Train verdict reads in two seconds. The app looks like itself.
- **Non-goals:**
  - a live decision feed
  - cost per 1,000 decisions on the report (the server computes no cost)
  - an onboarding tour
  - restructuring every canvas into the flat section style. Card styling changes globally through tokens, and only the canvases this plan touches are restructured.
- **Anti-goals:**
  - a progress indicator that marks a preview training run as a trained model
  - colour as the only carrier of bucket identity
  - any copy that says "confidence" or "probability"

## Constraints

- Client: React 19, Tailwind 4, the shadcn components in `components/ui/`, and bun. Server: FastAPI and uv.
- The journey's "Words on screen" table still governs copy.
- No real Anthropic, TypeSafe or Modal calls in tests.
- `make docs` after the API change. Generated files aren't hand-edited.

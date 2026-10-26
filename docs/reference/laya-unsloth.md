# Laya and Unsloth decision training: reference notes

Researched 2026-10-20 from the Laya model card and Unsloth's docs. Laya is the base model for sys1.

## Laya

- **Model:** `convaiinnovations/laya`, a ModernBERT-large backbone with a decision head trained from scratch. About 421M parameters, Apache 2.0. It's non-autoregressive, so each decision takes one forward pass. A multilingual variant is built on mmBERT-base (322M).
- **Context:** 512 tokens for the English root checkpoint. The multilingual and typed-decisions checkpoints default to 1,024 and can read up to 8,192 with `max_len`.
  - ⚠ `train.py` loads the root checkpoint with `max_seq_length = 2048`. Verify what length it actually trains and predicts at.
- **Jev compatibility:** `laya-serve` speaks Jev's request and response shape (`POST /v1/systemone`), so existing Jev clients only need a new base URL. Unknown fields are ignored.
- **Benchmarks against Jev** (from the model card; the Jev numbers are third-party):

  | Metric | Laya | Jev |
  |---|---|---|
  | typed-decisions accuracy | 0.766 | 0.727 |
  | AG News | 0.950 | 0.910 |
  | DAIR Emotion | 0.595 | 0.480 |
  | **Banking77 (77 classes)** | **0.425** | **0.870** |
  | ECE after temperature scaling | 0.081 | 0.246 |
  | p50 latency, one question | 33 ms | ~250 ms |

- **Limitations that shape our task design:**
  - **Weak zero-shot.** Base checkpoints are near chance on typed-decisions (0.36), so a weak "base Laya" baseline is expected.
  - **Many options favour Jev.** Choice options share one prompt budget, so above about 20 options Jev wins. Unsloth's server trims labels past about 20 described options.
  - **Weak question types.** `score` questions are the weakest type, and `noul` answers can be pulled by the wording of the true/false labels.
  - **Over-confidence.** The model ships over-confident, so refit the temperature on our calibration split.
  - **Long documents.** Accuracy varies past about 4k tokens.

## Unsloth decision training

- **Dataset row:** `state`, `questions` (a dict or JSON string) and `gold`, which holds the answer for each question.
  - For a choice question, gold is an option key. For noul it's a boolean, and for score it's a 0-based level index.
  - **This is Jev's request shape plus `gold`.** One parquet file can drive training, base-model evaluation and the Jev calls.
- **`FastDecisionModel` API:**

  | Call | Returns or does |
  |---|---|
  | `from_pretrained(model_name, max_seq_length, load_in_4bit)` | Loads the base model |
  | `get_peft_model(model, r, lora_alpha, lora_dropout, use_gradient_checkpointing, random_state)` | Attaches LoRA adapters |
  | `build_dataset(dataset, tokenizer, model)` | `(items, report)`, with `report['skipped']` and `report['total']` |
  | `split_holdout(items, seed)` | `(train_items, eval_items)` |
  | `calibrate(model, tokenizer, items)` | Metrics including held-out accuracy, `ece` and loss |
  | `predict(model, tokenizer, state, questions)` | `{question: {answer, probabilities, ...}}` |
  | `evaluate(model, tokenizer, test_items)` | Accuracy only |
  | `for_inference(model)` | Switches to inference mode; call it before `predict` |

- **Trainer:** `DecisionTrainer(model, processing_class, train_dataset, eval_dataset, args=TrainingArguments(...))`. The head's learning rate defaults to 1e-4 and can be changed with `head_learning_rate`.
- **Truncation:** long inputs keep the questions and options, and cut the end of `state`. With a 512-token window, long option descriptions eat into the ticket text.
- **Recommended settings:** LoRA rank 16, 2 epochs, or 3–4 with less data. Unsloth's Laya run reached 77% test accuracy using 2.5 GB of VRAM in about 10 minutes.
- **Other supported bases:** Qwen3.5 0.8B, 2B and 4B, Llama 3.2 3B and Gemma 4 E4B. Qwen3.5-2B scored 81% on Unsloth's test in about 40 minutes. It's the backup if Laya's context or option budget becomes the bottleneck.
- **Saving:** `save_pretrained` writes the LoRA adapters and the head. `save_pretrained_merged` writes a full 16-bit model.
- **Serving options:**
  - The Unsloth Studio Decision API (`POST /v1/systemone`, model `laya`, `default` or `jev-latest`). To serve a custom model, set the `UNSLOTH_SYSTEMONE_MODEL` env var.
  - `laya-serve`.
  - Studio's `confidence` uses a different formula from Jev's, so threshold on `probabilities` instead.

## Training and eval code today (as of commit b11a3ae)

All of it currently runs on `LocalLLaMA/typed-decisions` (subset `all`). Commands are in the `Makefile` (`make help`).

- **`train.py`** (`make train`):
  - Runs as the Modal app `laya-training` on an L4 GPU, with the volume `laya-outputs`.
  - Fine-tunes a LoRA on Laya, splitting the data into separate train, per-epoch eval and calibration sets.
  - Saves the adapter and downloads it to `./lora`, which is gitignored. When `save_pretrained` isn't available, it falls back to raw trainable weights in `lora/trainable.pt`.
  - Settings: lr 5e-5, batch 16, 2 epochs, LoRA rank 16. (Superseded: with `EPOCHS=0`, the default, `adaptive.py` picks the epoch ceiling and lr from the row count, and training stops early on eval loss with schedule-free AdamW. A positive `EPOCHS` fixes the pass count.)
- **`eval_laya.py` and `eval_lora.py`** (`make eval-laya`, `make eval-lora`): run on Modal and predict the test split with `FastDecisionModel.predict`. `eval_lora.py` rebuilds the `train.py` model and loads `lora/trainable.pt`.
- **`eval_jev.py`** (`make eval-jev`): runs locally and calls `https://api.typesafe.ai/v1/systemone` with `TYPESAFE_API_KEY`, using 8 threads with retries on 429 and 5xx errors.
- **`eval_common.py`:** shared scoring. Every answer is reduced to `{id, question, type, pred, gold, confidence, p_gold, correct}`. It reports accuracy, ECE (10 bins) and NLL, using the top *probability* as confidence, which follows our "use probabilities, not `confidence`" rule. Output goes to `results/<name>_{predictions.jsonl,summary.json}`.
- **Verified by these runs:**
  - `predict` returns per-option probabilities.
  - The TypeSafe-direct route works, and `jev-latest` resolved to `jev-1.13.0`.
- **First results** (typed-decisions test split, 400 rows and 2,000 decisions):

  | Model | Accuracy | ECE |
  |---|---|---|
  | Jev | 0.752 | 0.036 |
  | Laya + our LoRA | 0.658 | 0.166 |
  | Untrained Laya | 0.360 | 0.176 |

  - ⚠ Our LoRA is about 10 points below the published fine-tuned Laya numbers (0.766 on the model card, about 77% in Unsloth's table). That's worth explaining before phase 1 training relies on the same pipeline.
  - Unconfirmed suspects: the learning rate (5e-5, against Unsloth's recommended 2e-4), too few epochs, or something lost in the `trainable.pt` save and load path.
  - On this data Jev's calibration error is low (0.036), unlike the model card's 0.246.
- **Gaps for phase 1:** the dataset is hardcoded, there are no terse and policy question variants, and the Jev model isn't pinned by default. The Makefile passes `--model $JEV_MODEL`.

## Sources

- [Unsloth: train your own decision model](https://unsloth.ai/docs/basics/train-your-own-decision-model-with-unsloth)
- [Unsloth: Laya Decisions API](https://unsloth.ai/docs/models/decision-laya)
- [Laya model card](https://huggingface.co/convaiinnovations/laya)

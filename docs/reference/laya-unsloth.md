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

## train.py today (commit f8ca43c)

- **What it does:** a Modal app named `laya-training`, running on an L4 GPU with the volume `laya-outputs`. It fine-tunes a LoRA on Laya using `LocalLLaMA/typed-decisions` (subset `all`), calibrates, saves the adapter, and downloads it to `./lora`, which is gitignored. Run it with `modal run train.py`.
- **Status:** a smoke test of the training stack. Gaps for phase 1:
  - **Hardcoded dataset.** It trains on a public dataset that we can't use for evaluation, because it's in Unsloth's training mix.
  - **One holdout for two jobs.** `split_holdout` produces a single set used for both evaluation and calibration. Phase 1 needs separate train, calibration and test splits.
  - **No per-case predictions** with probabilities, and **no baselines.**

## Sources

- [Unsloth: train your own decision model](https://unsloth.ai/docs/basics/train-your-own-decision-model-with-unsloth)
- [Unsloth: Laya Decisions API](https://unsloth.ai/docs/models/decision-laya)
- [Laya model card](https://huggingface.co/convaiinnovations/laya)

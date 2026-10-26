"""Generate new labelled rows with NVIDIA NeMo Data Designer, in the upload format (text,decision).

The label is fixed first (seeded from the existing rows' decisions) and the LLM only writes the text for it, the same
label-before-text rule as the ticket pipeline. Nothing here uses Jev's answers.

    python generate_data.py --source data/banking/banking_upload.csv --per-label 20 --preview 5
    python generate_data.py --source data/banking/banking_upload.csv --per-label 20 --out data/banking/banking_new.csv

Real calls go to Anthropic with ANTHROPIC_API_KEY (read from the environment, never printed). Use --dry-run to
build and validate the config and see the call count without spending anything.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

DEFAULT_MODEL = "claude-haiku-5-5"
TONES = ["calm", "frustrated", "terse", "rambling", "polite"]
LENGTHS = ["one short sentence", "one sentence", "two sentences"]

PROMPT = """Write one new message a real customer might send, whose correct category is "{{ decision }}".

Existing messages in this category, for the range of topics and wording only:
{{ examples }}

Style: {{ tone }}, {{ length }}. Typos: {{ typos }}.
Do not copy or lightly reword the examples. Do not mention the category name. Make it clearly belong to this
category and not to a similar one. Reply with the message text only."""


def load_source(path):
    """Read a text,decision CSV."""
    df = pd.read_csv(path)
    missing = {"text", "decision"} - set(df.columns)
    if missing:
        sys.exit(f"{path} is missing columns: {sorted(missing)}")
    return df.dropna(subset=["text", "decision"]).astype(str)


def build_seed(source, per_label, shots, rng_seed):
    """One row per requested record: the label plus a few of its existing messages as wording examples."""
    rows = []
    for i, (decision, group) in enumerate(source.groupby("decision")):
        for j in range(per_label):
            sample = group["text"].sample(n=min(shots, len(group)), random_state=rng_seed + i * 10_000 + j)
            rows.append({"decision": decision, "examples": "\n".join(f"- {t}" for t in sample)})
    return pd.DataFrame(rows)


def build_config(seed, model, temperature):
    from data_designer.config import (
        CategorySamplerParams,
        ChatCompletionInferenceParams,
        DataDesignerConfigBuilder,
        DataFrameSeedSource,
        LLMTextColumnConfig,
        ModelConfig,
        SamplerColumnConfig,
        SamplerType,
        SamplingStrategy,
    )

    model_config = ModelConfig(
        alias="writer",
        model=model,
        provider="anthropic",
        inference_parameters=ChatCompletionInferenceParams(temperature=temperature, max_tokens=300),
    )
    builder = DataDesignerConfigBuilder(model_configs=[model_config])
    builder.with_seed_dataset(DataFrameSeedSource(df=seed), sampling_strategy=SamplingStrategy.ORDERED)
    for name, values in (("tone", TONES), ("length", LENGTHS), ("typos", ["none", "none", "a couple of typos"])):
        builder.add_column(
            SamplerColumnConfig(name=name, sampler_type=SamplerType.CATEGORY, params=CategorySamplerParams(values=values))
        )
    builder.add_column(LLMTextColumnConfig(name="text", model_alias="writer", prompt=PROMPT))
    return builder


def clean(df, source):
    """Keep text,decision, drop blanks and anything already in the source or repeated."""
    out = df[["text", "decision"]].copy()
    out["text"] = out["text"].astype(str).str.strip().str.strip('"').str.replace(r"\s+", " ", regex=True)
    out = out[out["text"].str.len() > 3]
    seen = set(source["text"].str.lower().str.strip())
    out = out[~out["text"].str.lower().isin(seen)].drop_duplicates(subset="text", keep="first")
    return out.reset_index(drop=True)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", required=True, help="text,decision CSV to take the labels and wording examples from")
    p.add_argument("--per-label", type=int, default=10, help="new rows to request per label")
    p.add_argument("--shots", type=int, default=5, help="existing messages shown per row as examples")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--temperature", type=float, default=1.0)
    p.add_argument("--seed", type=int, default=20261025)
    p.add_argument("--out", help="write the cleaned new rows here (text,decision)")
    p.add_argument("--preview", type=int, metavar="N", help="generate only N rows in memory and print them")
    p.add_argument("--dry-run", action="store_true", help="build the config and print the call count, no API calls")
    args = p.parse_args()

    source = load_source(args.source)
    seed = build_seed(source, args.per_label, args.shots, args.seed)
    n = args.preview or len(seed)
    print(f"{source['decision'].nunique()} labels, {len(seed)} rows requested, {n} LLM calls, model {args.model}")

    builder = build_config(seed, args.model, args.temperature)
    if args.dry_run:
        print("config OK; no calls made")
        return

    from data_designer.interface import DataDesigner
    from data_designer.config import ModelProvider

    # The api_key value is the name of the env var, resolved by Data Designer at call time.
    provider = ModelProvider(name="anthropic", endpoint="https://api.anthropic.com", provider_type="anthropic",
                             api_key="ANTHROPIC_API_KEY")
    dd = DataDesigner(artifact_path=Path("data/generated"), model_providers=[provider])

    if args.preview:
        result = dd.preview(builder, num_records=args.preview)
        print(clean(result.dataset, source).to_string(max_colwidth=100))
        return

    result = dd.create(builder, num_records=len(seed), dataset_name=Path(args.source).stem)
    new = clean(result.load_dataset(), source)
    if not args.out:
        sys.exit("pass --out to save the generated rows")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    new.to_csv(args.out, index=False)
    print(f"wrote {len(new)} rows to {args.out} ({len(seed) - len(new)} dropped as blank or duplicate)")


if __name__ == "__main__":
    main()

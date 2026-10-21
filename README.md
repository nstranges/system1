# Setting Up uv Environment
uv venv unsloth_env --python 3.13                                      
source unsloth_env/bin/activate
uv pip install modal

# Setting Up Modal Account
modal setup

# Running Training
modal run train.py

# Evaluating the untrained Laya baseline on the test split
modal run eval_laya.py            # add --limit 50 for a smoke test

# Evaluating the trained LoRA in lora/ on the test split
modal run eval_lora.py            # add --limit 50 for a smoke test

# Evaluating Jev (hosted API) on the test split; both evals write to results/
uv pip install requests datasets
export TYPESAFE_API_KEY=...
python eval_jev.py --limit 50   # smoke test, drop --limit for the full run

# Setting Up uv Environment
uv venv unsloth_env --python 3.13                                      
source unsloth_env/bin/activate
uv pip install modal

# Setting Up Modal Account
modal setup

# Running Training
modal run train.py

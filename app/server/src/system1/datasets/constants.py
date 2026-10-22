"""Limits and thresholds for the dataset journey, in one place so the server, tests and docs agree."""

SPLIT = {"train": 0.7, "cal": 0.1, "test": 0.2}

MIN_PER_BUCKET = 30
DEFAULT_TARGET = 30
GENERATION_CAP = 300
MIN_TEST_PER_BUCKET = 6
VERDICT_MIN_TEST_PER_BUCKET = 10
REVIEW_CARDS = 30

CONTEXT_MAX_FILE_BYTES = 2_000_000
CONTEXT_MAX_FILES = 10
CONTEXT_PROMPT_CHARS = 50_000

UPLOAD_MAX_BYTES = 5_000_000
UPLOAD_MAX_ROWS = 5_000

MAX_GUIDELINES = 20
MAX_GUIDELINE_CHARS = 300
MAX_SAMPLE_INPUTS = 3
# Matches Settings.max_input_chars: validate_policy sees only the policy, not settings.
MAX_SAMPLE_INPUT_CHARS = 6000

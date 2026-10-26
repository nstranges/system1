"""The base model behind each training size the product offers. The server sends only the size name."""

SIZES = {
    "small": "convaiinnovations/laya",
    "medium": "unsloth/Qwen3.5-0.8B",
    "large": "unsloth/Qwen3.5-2B",
}


def base_for(size):
    """The Hugging Face id to fine-tune for a size."""
    if size not in SIZES:
        raise ValueError(f"unknown model size {size!r}; use one of {', '.join(SIZES)}")
    return SIZES[size]

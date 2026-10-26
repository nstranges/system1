import pytest

from model_sizes import SIZES, base_for


def test_each_size_maps_to_its_base():
    assert base_for("small") == "convaiinnovations/laya"
    assert base_for("medium") == "unsloth/Qwen3.5-0.8B"
    assert base_for("large") == "unsloth/Qwen3.5-2B"
    assert list(SIZES) == ["small", "medium", "large"]


def test_unknown_size_is_refused():
    with pytest.raises(ValueError):
        base_for("huge")

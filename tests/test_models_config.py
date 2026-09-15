"""The model registry is the single source of truth for model names and
prices (see CLAUDE.md). This guards its shape so later phases can rely on it.
"""

from __future__ import annotations

from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "models.yaml"

EXPECTED_KEYS = {"frontier_large", "frontier_small", "local"}
REQUIRED_FIELDS = {
    "provider",
    "name",
    "input_price_per_mtok",
    "output_price_per_mtok",
}


def test_models_yaml_has_expected_shape() -> None:
    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    assert set(data["models"]) == EXPECTED_KEYS
    for spec in data["models"].values():
        assert set(spec) >= REQUIRED_FIELDS


def test_local_model_is_free() -> None:
    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    local = data["models"]["local"]
    assert local["input_price_per_mtok"] == 0
    assert local["output_price_per_mtok"] == 0

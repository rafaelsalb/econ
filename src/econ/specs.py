from __future__ import annotations

from pathlib import Path

import yaml

from . import config
from .utils import sha256_file

REQUIRED = [
    "school",
    "model_id",
    "version",
    "equations",
    "observables",
    "identification",
    "calibration",
    "estimation",
    "forecast_recipe",
    "refutation_conditions",
    "discriminating_predictions",
    "known_limitations",
    "revision_policy",
    "pass_criteria",
]


def card_path(model_id: str) -> Path:
    return config.SPECS / f"{model_id}.yaml"


def load_card(model_id: str) -> dict:
    path = card_path(model_id)
    if not path.exists():
        raise FileNotFoundError(f"no model card at {path}")
    return yaml.safe_load(path.read_text())


def validate_card(card: dict) -> list[str]:
    problems = []
    for key in REQUIRED:
        if key not in card or card[key] in (None, "", {}, []):
            problems.append(f"missing field: {key}")
    eq = card.get("equations", {})
    if not isinstance(eq, dict) or not eq:
        problems.append("equations must be a non-empty mapping")
    for name in ["pi", "activity", "policy_rate", "expectations"]:
        if name not in card.get("observables", {}):
            problems.append(f"missing observable mapping: {name}")
    return problems


def hash_card(model_id: str) -> str:
    return sha256_file(card_path(model_id))

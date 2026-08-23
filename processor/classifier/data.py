"""Canonical classifier tables loaded from the checked-in JSON/YAML snapshots."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal


_TABLE_DIR = Path(__file__).with_name("tables")


def _load(name: str):
    # The snapshots use JSON, which is a strict subset of YAML.  Keeping the
    # loader in the standard library avoids adding a runtime dependency.
    return json.loads((_TABLE_DIR / name).read_text(encoding="utf-8"))


@dataclass(frozen=True, slots=True)
class Rule:
    """One labelled classifier rule and the evidence that exercises it."""

    pattern: str
    exemplar: str
    view: Literal["unfiltered", "filtered"]
    tier: Literal["immediate", "high"]


def _rules(name: str) -> list[Rule]:
    rows = _load(name)
    if not isinstance(rows, list):
        raise TypeError(f"classifier table {name!r} must be a list")
    rules: list[Rule] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise TypeError(f"classifier table {name!r} row {index} must be an object")
        try:
            pattern = str(row["pattern"]).strip()
            exemplar = str(row["exemplar"]).strip()
            view = str(row["view"]).strip()
            tier = str(row["tier"]).strip()
        except KeyError as exc:
            raise ValueError(
                f"classifier table {name!r} row {index} is missing {exc.args[0]!r}"
            ) from exc
        if not pattern or not exemplar:
            raise ValueError(
                f"classifier table {name!r} row {index} needs pattern and exemplar"
            )
        if view not in {"unfiltered", "filtered"}:
            raise ValueError(f"classifier table {name!r} row {index} has invalid view")
        if tier not in {"immediate", "high"}:
            raise ValueError(f"classifier table {name!r} row {index} has invalid tier")
        rules.append(Rule(pattern, exemplar, view, tier))
    return rules


def _patterns(rules: list[Rule]) -> list[str]:
    """Build one stable, mutable regex-list compatibility surface."""

    return [rule.pattern for rule in rules]


_MAIN_IMMEDIATE_RULES = _rules("immediate.main.yaml")
_PORT_IMMEDIATE_RULES = _rules("immediate.port.yaml")
_WEAK_DAMAGE_RULES = _rules("weak_damage.yaml")
_WEAK_OMISSION_RULES = _rules("weak_omission.yaml")
_MAIN_HIGH_RULES = _rules("high.main.yaml")
_PORT_HIGH_RULES = _rules("high.port.yaml")
_MANAGER_RULES = _rules("manager.yaml")
_ANGRY_RULES = _rules("angry.yaml")

RULE_TABLES: dict[str, list[Rule]] = {
    "immediate.main": _MAIN_IMMEDIATE_RULES,
    "immediate.port": _PORT_IMMEDIATE_RULES,
    "weak.damage": _WEAK_DAMAGE_RULES,
    "weak.omission": _WEAK_OMISSION_RULES,
    "high.main": _MAIN_HIGH_RULES,
    "high.port": _PORT_HIGH_RULES,
    "manager": _MANAGER_RULES,
    "angry": _ANGRY_RULES,
}

RULE_PATTERN_TABLES: dict[str, list[str]] = {
    name: _patterns(rules) for name, rules in RULE_TABLES.items()
}


# These flattened lists preserve the legacy classifier's mutable identities.
# Rule metadata is canonical in RULE_TABLES; these are deliberately the
# compatibility view consumed by the unchanged engine.
_MAIN_IMMEDIATE_KEYWORDS = RULE_PATTERN_TABLES["immediate.main"]
_PORT_IMMEDIATE_KEYWORDS = RULE_PATTERN_TABLES["immediate.port"]
_IMMEDIATE_KEYWORDS = _MAIN_IMMEDIATE_KEYWORDS + _PORT_IMMEDIATE_KEYWORDS

_WEAK_UNGUARDED: list[str] = []
_WEAK_DAMAGE = RULE_PATTERN_TABLES["weak.damage"]
_WEAK_OMISSION = RULE_PATTERN_TABLES["weak.omission"]
_WEAK_IMMEDIATE = _WEAK_UNGUARDED + _WEAK_DAMAGE + _WEAK_OMISSION

_MAIN_HIGH_KEYWORDS = RULE_PATTERN_TABLES["high.main"]
_PORT_HIGH_KEYWORDS = RULE_PATTERN_TABLES["high.port"]
_HIGH_KEYWORDS = _MAIN_HIGH_KEYWORDS + _PORT_HIGH_KEYWORDS
_PORTED_HIGH_PATTERNS = tuple(_PORT_HIGH_KEYWORDS)

_MANAGER_DEMAND_KEYWORDS = RULE_PATTERN_TABLES["manager"]
_ANGRY_KEYWORDS = RULE_PATTERN_TABLES["angry"]

_INTENTS = _load("intents.yaml")
_SENSITIVE_INTENTS = set(_INTENTS["sensitive"])
_HIGH_INTENTS = set(_INTENTS["high"])
_HIGH_SENSITIVE_INTENTS = set(_INTENTS["high_sensitive"])

_CAPS = _load("caps.yaml")
_CAPS_STOPWORDS = frozenset(_CAPS["stopwords"])
_SHOUT_ANCHORS = frozenset(_CAPS["anchors"])
_SHOUT_GRAMMAR = frozenset(_CAPS["grammar"])
_SHOUT_COMPLAINT_VERBS = frozenset(_CAPS["complaint_verbs"])
_SHOUT_HARD_ANCHORS = frozenset(_CAPS["hard_anchors"])


__all__ = [
    "Rule", "RULE_TABLES", "RULE_PATTERN_TABLES",
    "_MAIN_IMMEDIATE_RULES", "_PORT_IMMEDIATE_RULES",
    "_WEAK_DAMAGE_RULES", "_WEAK_OMISSION_RULES", "_MAIN_HIGH_RULES",
    "_PORT_HIGH_RULES", "_MANAGER_RULES", "_ANGRY_RULES",
    "_MAIN_IMMEDIATE_KEYWORDS", "_PORT_IMMEDIATE_KEYWORDS",
    "_IMMEDIATE_KEYWORDS", "_WEAK_UNGUARDED", "_WEAK_DAMAGE",
    "_WEAK_OMISSION", "_WEAK_IMMEDIATE", "_MAIN_HIGH_KEYWORDS",
    "_PORT_HIGH_KEYWORDS", "_HIGH_KEYWORDS", "_PORTED_HIGH_PATTERNS",
    "_MANAGER_DEMAND_KEYWORDS", "_ANGRY_KEYWORDS", "_SENSITIVE_INTENTS",
    "_HIGH_INTENTS", "_HIGH_SENSITIVE_INTENTS", "_CAPS_STOPWORDS",
    "_SHOUT_ANCHORS", "_SHOUT_GRAMMAR", "_SHOUT_COMPLAINT_VERBS",
    "_SHOUT_HARD_ANCHORS",
]

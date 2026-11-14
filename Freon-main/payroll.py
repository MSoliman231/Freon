import json
import os

import paths

RULES_FILE = paths.data_dir() / "rules.json"

# Only the late rules are fixed amounts. An absent day is not here: it costs
# one day of that person's own salary (salary / days in the month).
RULE_STATES = ("Late-1", "Late-2")

# Placeholder values for now, change them from Settings
DEFAULT_DEDUCTIONS = {"Late-1": 10.0, "Late-2": 20.0}


def format_amount(value):
    value = float(value)
    if value == int(value):
        return str(int(value))
    return f"{value:.2f}"


def load_rules():
    rules = {"deductions": dict(DEFAULT_DEDUCTIONS), "salaries": {}}
    try:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for state, value in data.get("deductions", {}).items():
            if state in rules["deductions"]:
                rules["deductions"][state] = float(value)
        for name, salary in data.get("salaries", {}).items():
            rules["salaries"][name] = float(salary)
    except (OSError, ValueError, AttributeError):
        pass
    return rules


def save_rules(rules):
    tmp = RULES_FILE.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        os.replace(tmp, RULES_FILE)
    except OSError as e:
        print(f"Could not save rules: {e}")


def remove_name(name):
    """Called when a name is deleted from the attendance page."""
    rules = load_rules()
    if name in rules["salaries"]:
        del rules["salaries"][name]
        save_rules(rules)


def rename_name(old, new):
    """Moves a name's salary to the new name."""
    rules = load_rules()
    if old in rules["salaries"]:
        rules["salaries"][new] = rules["salaries"].pop(old)
        save_rules(rules)
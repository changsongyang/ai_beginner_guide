"""Lab 02: deterministic validation of a small structured-output contract."""

from __future__ import annotations

import json


REQUIRED_FIELDS = ("person", "location", "time")


def verify_json(text: str) -> bool:
    """Accept an object only when it has exactly the required string fields."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return False
    if not isinstance(data, dict) or set(data) != set(REQUIRED_FIELDS):
        return False
    return all(isinstance(data[field], str) and data[field].strip() for field in REQUIRED_FIELDS)


def run_experiment() -> dict[str, object]:
    """Validate one conforming and two non-conforming fixed outputs."""
    inputs = {
        "valid": '{"person":"Ada","location":"London","time":"1843"}',
        "extra_field": (
            '{"person":"Ada","location":"London","time":"1843","confidence":0.9}'
        ),
        "invalid_json": '{"person":"Ada","location":"London","time":1843',
    }
    return {
        "required_fields": list(REQUIRED_FIELDS),
        "cases": {name: verify_json(value) for name, value in inputs.items()},
    }


def evaluate(result: dict[str, object]) -> dict[str, object]:
    """Check that valid output passes and both failure modes are rejected."""
    expected = {"valid": True, "extra_field": False, "invalid_json": False}
    checks = {
        "required_fields_are_exact": result.get("required_fields") == list(REQUIRED_FIELDS),
        "case_outcomes_match": result.get("cases") == expected,
    }
    return {"passed": all(checks.values()), "checks": checks}


if __name__ == "__main__":
    experiment = run_experiment()
    print(json.dumps({"result": experiment, "evaluation": evaluate(experiment)}, ensure_ascii=False, indent=2))

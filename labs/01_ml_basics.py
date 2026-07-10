"""Lab 01: a deterministic linear-regression train/test/evaluate loop."""

from __future__ import annotations

import json
import math
import random


def _fit_line(features: list[float], targets: list[float]) -> tuple[float, float]:
    feature_mean = sum(features) / len(features)
    target_mean = sum(targets) / len(targets)
    covariance = sum(
        (feature - feature_mean) * (target - target_mean)
        for feature, target in zip(features, targets)
    )
    variance = sum((feature - feature_mean) ** 2 for feature in features)
    coefficient = covariance / variance
    intercept = target_mean - coefficient * feature_mean
    return coefficient, intercept


def run_experiment() -> dict[str, float | int]:
    """Fit a line to fixed synthetic housing data and return observable metrics."""
    generator = random.Random(42)
    areas = [50.0 + generator.random() * 200.0 for _ in range(100)]
    prices = [5.0 * area + 20.0 + generator.gauss(0.0, 50.0) for area in areas]

    indices = list(range(100))
    generator.shuffle(indices)
    train_indices, test_indices = indices[:80], indices[80:]
    train_x = [areas[index] for index in train_indices]
    train_y = [prices[index] for index in train_indices]
    coefficient, intercept = _fit_line(train_x, train_y)

    test_y = [prices[index] for index in test_indices]
    predictions = [coefficient * areas[index] + intercept for index in test_indices]
    mean_squared_error = sum(
        (actual - predicted) ** 2 for actual, predicted in zip(test_y, predictions)
    ) / len(test_y)
    target_mean = sum(test_y) / len(test_y)
    total_variance = sum((actual - target_mean) ** 2 for actual in test_y)
    residual_variance = sum(
        (actual - predicted) ** 2 for actual, predicted in zip(test_y, predictions)
    )

    return {
        "samples": 100,
        "train_samples": len(train_indices),
        "test_samples": len(test_indices),
        "coefficient": round(coefficient, 6),
        "intercept": round(intercept, 6),
        "rmse": round(math.sqrt(mean_squared_error), 6),
        "r2": round(1.0 - residual_variance / total_variance, 6),
    }


def evaluate(result: dict[str, float | int]) -> dict[str, object]:
    """Apply the lab's published acceptance thresholds."""
    checks = {
        "split_is_80_20": (result["train_samples"], result["test_samples"]) == (80, 20),
        "coefficient_is_near_five": 4.5 < float(result["coefficient"]) < 5.5,
        "rmse_is_in_expected_range": 20.0 < float(result["rmse"]) < 70.0,
        "r2_exceeds_threshold": float(result["r2"]) > 0.9,
    }
    return {"passed": all(checks.values()), "checks": checks}


if __name__ == "__main__":
    experiment = run_experiment()
    print(json.dumps({"result": experiment, "evaluation": evaluate(experiment)}, ensure_ascii=False, indent=2))

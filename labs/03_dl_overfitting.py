"""Lab 03: deterministic overfitting and early-stopping evidence on CPU.

A high-capacity polynomial is used as a compact proxy for a neural network so
the learning-curve behavior is visible without installing a training framework.
The same train-loss-down/validation-loss-up signal motivates early stopping in
deep learning.
"""

from __future__ import annotations

import json
import math
import random


def _mse(weights: list[float], data: list[tuple[float, float]]) -> float:
    total = 0.0
    for feature, target in data:
        prediction = sum(weight * feature**power for power, weight in enumerate(weights))
        total += (prediction - target) ** 2
    return total / len(data)


def run_experiment() -> dict[str, object]:
    """Train a noisy high-capacity model and return its fixed learning curve."""
    generator = random.Random(42)
    training = []
    for index in range(12):
        feature = -1.0 + 2.0 * index / 11.0
        target = math.sin(math.pi * feature) + generator.gauss(0.0, 0.8)
        training.append((feature, target))
    validation = [
        (feature := -1.0 + 2.0 * index / 80.0, math.sin(math.pi * feature))
        for index in range(81)
    ]

    weights = [0.0] * 19
    epochs = 4000
    learning_rate = 0.15
    curve: list[dict[str, float | int]] = []
    for epoch in range(1, epochs + 1):
        gradients = [0.0] * len(weights)
        for feature, target in training:
            powers = [feature**power for power in range(len(weights))]
            error = sum(weight * value for weight, value in zip(weights, powers)) - target
            for index, value in enumerate(powers):
                gradients[index] += 2.0 * error * value / len(training)
        for index, gradient in enumerate(gradients):
            weights[index] -= learning_rate * gradient

        if epoch == 1 or epoch % 100 == 0:
            curve.append(
                {
                    "epoch": epoch,
                    "train_loss": round(_mse(weights, training), 8),
                    "validation_loss": round(_mse(weights, validation), 8),
                }
            )

    best = min(curve, key=lambda point: float(point["validation_loss"]))
    return {
        "epochs": epochs,
        "best_epoch": best["epoch"],
        "initial_train_loss": curve[0]["train_loss"],
        "final_train_loss": curve[-1]["train_loss"],
        "best_validation_loss": best["validation_loss"],
        "final_validation_loss": curve[-1]["validation_loss"],
        "curve": curve,
    }


def evaluate(result: dict[str, object]) -> dict[str, object]:
    """Confirm that continued fitting after the best epoch harms validation."""
    checks = {
        "training_loss_decreases": result["final_train_loss"] < result["initial_train_loss"],
        "early_stop_precedes_end": result["best_epoch"] < result["epochs"],
        "validation_rebounds": result["final_validation_loss"] > result["best_validation_loss"],
    }
    return {"passed": all(checks.values()), "checks": checks}


if __name__ == "__main__":
    experiment = run_experiment()
    print(json.dumps({"result": experiment, "evaluation": evaluate(experiment)}, ensure_ascii=False, indent=2))

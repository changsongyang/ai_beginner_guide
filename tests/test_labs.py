from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAB_DIR = ROOT / "labs"
LAB_FILES = (
    "01_ml_basics.py",
    "02_structured_output.py",
    "03_dl_overfitting.py",
    "04_rag_minimal.py",
    "05_agent_evals.py",
)


def load_lab(filename: str):
    path = LAB_DIR / filename
    source = path.read_text(encoding="utf-8")
    if "def run_experiment(" not in source or "def evaluate(" not in source:
        raise AssertionError(f"{filename} must expose run_experiment() and evaluate()")
    spec = importlib.util.spec_from_file_location("lab_" + filename[:2], path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot import {filename}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LabContractTests(unittest.TestCase):
    def test_every_lab_has_callable_experiment_and_evaluation(self) -> None:
        for filename in LAB_FILES:
            with self.subTest(filename=filename):
                module = load_lab(filename)
                self.assertTrue(callable(module.run_experiment))
                self.assertTrue(callable(module.evaluate))

    def test_every_lab_is_deterministic_serializable_and_self_passing(self) -> None:
        for filename in LAB_FILES:
            with self.subTest(filename=filename):
                module = load_lab(filename)
                first = module.run_experiment()
                second = module.run_experiment()
                self.assertEqual(first, second)
                json.dumps(first, ensure_ascii=False)
                evaluation = module.evaluate(first)
                json.dumps(evaluation, ensure_ascii=False)
                self.assertIs(evaluation["passed"], True, evaluation)

    def test_labs_do_not_require_network_or_live_keys(self) -> None:
        for filename in LAB_FILES:
            source = (LAB_DIR / filename).read_text(encoding="utf-8")
            with self.subTest(filename=filename):
                for forbidden in (
                    "OPENAI_API_KEY",
                    "ANTHROPIC_API_KEY",
                    "os.environ",
                    "import requests",
                    "from requests",
                ):
                    self.assertNotIn(forbidden, source)
        dependencies = [
            line
            for line in (LAB_DIR / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(dependencies, [])

    def test_lab_01_stable_metric_ranges(self) -> None:
        result = load_lab("01_ml_basics.py").run_experiment()
        self.assertEqual((result["samples"], result["train_samples"], result["test_samples"]), (100, 80, 20))
        self.assertGreater(result["coefficient"], 4.5)
        self.assertLess(result["coefficient"], 5.5)
        self.assertGreater(result["rmse"], 20.0)
        self.assertLess(result["rmse"], 70.0)
        self.assertGreater(result["r2"], 0.9)

    def test_lab_02_stable_schema_cases(self) -> None:
        result = load_lab("02_structured_output.py").run_experiment()
        self.assertEqual(
            result["cases"],
            {"valid": True, "extra_field": False, "invalid_json": False},
        )

    def test_lab_03_exposes_overfitting_and_early_stop(self) -> None:
        result = load_lab("03_dl_overfitting.py").run_experiment()
        self.assertLess(result["best_epoch"], result["epochs"])
        self.assertLess(result["final_train_loss"], result["initial_train_loss"])
        self.assertGreater(result["final_validation_loss"], result["best_validation_loss"])

    def test_lab_04_returns_grounded_rag_trace(self) -> None:
        result = load_lab("04_rag_minimal.py").run_experiment()
        self.assertIn("RAG", result["hits"][0]["text"])
        self.assertIn("检索上下文", result["context"])
        self.assertIn("基于检索结果", result["answer"])

    def test_lab_05_returns_two_case_eval_report(self) -> None:
        result = load_lab("05_agent_evals.py").run_experiment()
        self.assertEqual(result["test_cases_evaluated"], 2)
        self.assertEqual(len(result["details"]), 2)
        self.assertGreaterEqual(result["average_relevance"], 0.8)


if __name__ == "__main__":
    unittest.main()

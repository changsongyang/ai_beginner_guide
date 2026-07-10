"""
Agent Output Evaluation (Evals) - Basic Framework

Corresponds to: Chapter 14 - AI 智能体 (AI Agents)

This file is a runnable local eval harness. It uses simple lexical metrics so
beginners can understand the evaluation loop without API keys or model calls.
Replace the scoring functions with embeddings, LLM judges, or task-specific
graders when moving beyond this teaching example.
"""

from __future__ import annotations

import json
import re
from statistics import mean
from typing import Callable


TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")


def tokenize(text: str) -> set[str]:
    """Return normalized tokens for lightweight overlap metrics."""
    return {token.lower() for token in TOKEN_RE.findall(text)}


def jaccard_similarity(left: str, right: str) -> float:
    """Compute token-set Jaccard similarity."""
    left_tokens = tokenize(left)
    right_tokens = tokenize(right)
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


class AgentEvaluator:
    """Small local evaluator for agent output consistency and grounding."""

    def __init__(self):
        self.results: list[dict] = []

    def consistency_eval(self, agent_func: Callable[[str], str], query: str, runs: int = 3) -> dict:
        """Evaluate output consistency across repeated runs."""
        outputs = [agent_func(query) for _ in range(runs)]
        result = {
            "query": query,
            "outputs": outputs,
            "consistency_score": self._compute_consistency(outputs),
        }
        self.results.append(result)
        return result

    def relevance_eval(self, agent_output: str, reference_answer: str) -> float:
        """Score how much the output overlaps with the expected answer."""
        return jaccard_similarity(agent_output, reference_answer)

    def faithfulness_eval(self, agent_output: str, context: str) -> dict:
        """
        Estimate whether answer tokens are supported by the provided context.

        This is a teaching metric, not a hallucination detector. It is useful
        for showing why production evals need explicit context grounding.
        """
        output_tokens = tokenize(agent_output)
        context_tokens = tokenize(context)
        unsupported = sorted(output_tokens - context_tokens)
        score = 1.0 if not output_tokens else 1 - (len(unsupported) / len(output_tokens))
        return {
            "faithfulness_score": max(0.0, score),
            "unsupported_tokens": unsupported[:20],
        }

    def _compute_consistency(self, outputs: list[str]) -> float:
        """Average pairwise similarity across outputs."""
        if len(outputs) <= 1:
            return 1.0

        scores = []
        for i, left in enumerate(outputs):
            for right in outputs[i + 1:]:
                scores.append(jaccard_similarity(left, right))
        return mean(scores) if scores else 1.0


def run_eval_suite(agent_func: Callable[[str], str], test_cases: list[dict]) -> dict:
    """Run consistency, relevance, and faithfulness checks over test cases."""
    evaluator = AgentEvaluator()
    details = []

    for test in test_cases:
        output = agent_func(test["query"])
        detail = {
            "query": test["query"],
            "output": output,
            "consistency": evaluator.consistency_eval(agent_func, test["query"], runs=2),
        }

        if "expected_answer" in test:
            detail["relevance_score"] = evaluator.relevance_eval(
                output,
                test["expected_answer"],
            )

        if "context" in test:
            detail["faithfulness"] = evaluator.faithfulness_eval(
                output,
                test["context"],
            )

        details.append(detail)

    relevance_scores = [
        item["relevance_score"]
        for item in details
        if "relevance_score" in item
    ]
    return {
        "test_cases_evaluated": len(details),
        "average_relevance": mean(relevance_scores) if relevance_scores else None,
        "details": details,
    }


def simple_agent(query: str) -> str:
    """Deterministic toy agent for the local evaluation loop."""
    knowledge = {
        "What is machine learning?": "Machine learning learns patterns from data.",
        "Explain neural networks": "Neural networks are layered models that learn representations.",
    }
    return knowledge.get(query, "I do not have enough context to answer.")


def run_experiment() -> dict:
    """Evaluate two fixed agent tasks and return a serializable report."""
    test_cases = [
        {
            "query": "What is machine learning?",
            "expected_answer": "Machine learning learns patterns from data.",
            "context": "Machine learning learns patterns from data.",
        },
        {
            "query": "Explain neural networks",
            "expected_answer": "Neural networks are layered models.",
            "context": "Neural networks are layered models that learn representations.",
        },
    ]
    return run_eval_suite(simple_agent, test_cases)


def evaluate(result: dict) -> dict[str, object]:
    """Apply stable minimum thresholds to the fixed evaluation report."""
    details = result.get("details", [])
    checks = {
        "two_cases_ran": result.get("test_cases_evaluated") == 2 and len(details) == 2,
        "relevance_is_acceptable": float(result.get("average_relevance") or 0.0) >= 0.8,
        "outputs_are_consistent": all(
            detail["consistency"]["consistency_score"] == 1.0 for detail in details
        ),
        "answers_are_grounded": all(
            detail["faithfulness"]["faithfulness_score"] == 1.0 for detail in details
        ),
    }
    return {"passed": all(checks.values()), "checks": checks}


if __name__ == "__main__":
    experiment = run_experiment()
    print(json.dumps({"result": experiment, "evaluation": evaluate(experiment)}, ensure_ascii=False, indent=2))

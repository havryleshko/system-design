from __future__ import annotations
import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List
from uuid import uuid4
from app.eval.judge import LLMJudge
from app.eval.scenarios import Scenario, ScenarioResult, load_scenarios
from app.agent.blueprint.generate import generate_blueprint


def run_scenario(scenario: Scenario, judge: LLMJudge) -> ScenarioResult:
    _ = uuid4()  
    blueprint = generate_blueprint(goal=scenario.prompt)
    output = json.dumps(blueprint.model_dump(), ensure_ascii=False, indent=2)
    judgement = judge.judge(scenario.prompt, output, scenario.success_criteria)
    return ScenarioResult(
        scenario=scenario,
        output=output,
        score=judgement.score,
        passed=judgement.passed,
        feedback=judgement.feedback,
    )


def run_batch(scenarios: Iterable[Scenario], judge: LLMJudge) -> List[ScenarioResult]:
    results: List[ScenarioResult] = []
    for scenario in scenarios:
        try:
            result = run_scenario(scenario, judge)
        except Exception as exc:  # pragma: no cover - evaluation failure path
            results.append(
                ScenarioResult(
                    scenario=scenario,
                    output="",
                    score=0.0,
                    passed=False,
                    feedback=f"Execution failed: {exc}",
                )
            )
            continue
        results.append(result)
    return results


def summarise_and_log(results: List[ScenarioResult], output_path: Path | None = None) -> int:
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    avg_score = sum(r.score for r in results) / total if total else 0.0

    print(f"Passed {passed}/{total} scenarios | avg score {avg_score:.2f}", file=sys.stderr)
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.scenario.name}: {result.score:.2f} — {result.feedback}", file=sys.stderr)

    if output_path:
        payload = [
            {
                "scenario": asdict(result.scenario),
                "output": result.output,
                "score": result.score,
                "passed": result.passed,
                "feedback": result.feedback,
            }
            for result in results
        ]
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0 if passed == total else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run evaluation scenarios against the agent.")
    parser.add_argument("--extra-scenarios", type=str, help="Optional path to additional scenarios file", default=None)
    parser.add_argument("--model", type=str, help="LLM judge model id", default=None)
    parser.add_argument("--threshold", type=float, help="Passing threshold", default=0.6)
    parser.add_argument("--output", type=str, help="Write JSON results to this path", default=None)
    args = parser.parse_args(argv)

    judge = LLMJudge(model=args.model, threshold=args.threshold)
    results = run_batch(load_scenarios(args.extra_scenarios), judge)
    output_path = Path(args.output) if args.output else None
    return summarise_and_log(results, output_path)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())



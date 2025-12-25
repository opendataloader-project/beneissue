"""LangSmith Evals demo script.

Upload existing test cases to LangSmith Dataset and run evaluation.

Usage:
    export LANGCHAIN_API_KEY="ls_..."
    export ANTHROPIC_API_KEY="sk-..."

    # Upload only
    uv run python scripts/langsmith_eval.py --upload-only

    # Eval only
    uv run python scripts/langsmith_eval.py --eval-only

    # Both
    uv run python scripts/langsmith_eval.py
"""

import argparse
import json
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langsmith import Client
from langsmith.evaluation import evaluate

DATASET_NAME = "beneissue-triage-test"


def load_triage_cases() -> list[dict]:
    """Load existing test cases."""
    cases_dir = Path("examples/calculator/.claude/skills/beneissue/tests/cases")
    triage_cases = []

    for f in cases_dir.glob("triage-*.json"):
        data = json.loads(f.read_text())
        inputs = {
            "title": data["input"]["title"],
            "body": data["input"]["body"],
        }
        # Include existing_issues if present (for duplicate detection)
        if "existing_issues" in data["input"]:
            inputs["existing_issues"] = data["input"]["existing_issues"]

        triage_cases.append({
            "inputs": inputs,
            "outputs": {"decision": data["expected"]["decision"]},
        })

    return triage_cases


def upload_dataset(client: Client, cases: list[dict]) -> None:
    """Create LangSmith dataset."""
    # Delete existing dataset
    try:
        existing = client.read_dataset(dataset_name=DATASET_NAME)
        client.delete_dataset(dataset_id=existing.id)
        print(f"Deleted existing dataset: {DATASET_NAME}")
    except Exception:
        pass

    # Create new dataset
    dataset = client.create_dataset(DATASET_NAME)
    for case in cases:
        client.create_example(
            inputs=case["inputs"],
            outputs=case["outputs"],
            dataset_id=dataset.id,
        )

    print(f"Created dataset: {dataset.url}")


def run_eval(client: Client) -> None:
    """Run evaluation."""
    # Check dataset exists
    try:
        client.read_dataset(dataset_name=DATASET_NAME)
    except Exception:
        print(f"Dataset '{DATASET_NAME}' not found. Run with --upload-only first.")
        return

    print("Running evaluation...")
    results = evaluate(
        triage,
        data=DATASET_NAME,
        evaluators=[check_decision],
        experiment_prefix="triage-v1",
    )

    print(f"\nExperiment: {results.experiment_name}")
    print("View results at: https://smith.langchain.com")


def triage(inputs: dict) -> dict:
    """Simple triage function."""
    llm = ChatAnthropic(model="claude-haiku-4-5")

    # Build prompt with existing issues if present
    content = f"Title: {inputs['title']}\n\nBody: {inputs['body']}"
    if "existing_issues" in inputs:
        issues_text = "\n".join(
            f"- #{issue['number']}: {issue['title']} ({issue['state']})"
            for issue in inputs["existing_issues"]
        )
        content += f"\n\nExisting Issues:\n{issues_text}"

    response = llm.invoke([
        SystemMessage(
            content="You are a GitHub issue triage bot. "
            "Respond with ONLY one word: valid, invalid, duplicate, or needs_info"
        ),
        HumanMessage(content=content),
    ])
    decision = response.content.strip().lower().replace('"', "")
    return {"decision": decision}


def check_decision(run, example) -> dict:
    """Evaluator: check if decision matches expected."""
    expected = example.outputs["decision"]
    actual = run.outputs.get("decision", "")
    return {"key": "correct", "score": 1 if expected in actual else 0}


def main():
    parser = argparse.ArgumentParser(description="LangSmith Evals demo")
    parser.add_argument("--upload-only", action="store_true", help="Upload dataset only")
    parser.add_argument("--eval-only", action="store_true", help="Run eval only")
    args = parser.parse_args()

    client = Client()

    # If neither specified, run both
    do_upload = args.upload_only or (not args.upload_only and not args.eval_only)
    do_eval = args.eval_only or (not args.upload_only and not args.eval_only)

    if do_upload:
        cases = load_triage_cases()
        print(f"Loaded {len(cases)} triage cases")
        upload_dataset(client, cases)

    if do_eval:
        run_eval(client)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""LangSmith cost debugging script.

Analyzes cost duplication in LangSmith traces by fetching runs
and comparing LLM costs vs parent-reported costs.

Usage:
    source .env && python scripts/langsmith_cost_debug.py
    source .env && python scripts/langsmith_cost_debug.py --project beneissue --limit 10
    source .env && python scripts/langsmith_cost_debug.py --run-id <uuid>
"""

import argparse
import os
import sys
from datetime import datetime, timezone

from langsmith import Client


def analyze_trace(client: Client, project_name: str, trace_id: str, root_run_id: str):
    """Analyze a single trace for cost duplication."""
    all_runs = list(client.list_runs(
        project_name=project_name,
        filter=f'eq(trace_id, "{trace_id}")',
    ))

    print(f"\n{'='*60}")
    print(f"Trace: {str(trace_id)[:8]}... ({len(all_runs)} runs)")
    print('='*60)

    # Build parent-child relationships
    runs_by_id = {str(run.id): run for run in all_runs}
    children = {}
    for run in all_runs:
        parent_id = str(run.parent_run_id) if run.parent_run_id else None
        if parent_id not in children:
            children[parent_id] = []
        children[parent_id].append(run)

    total_llm_cost = 0
    root_cost = 0

    def print_tree(run, depth=0):
        nonlocal total_llm_cost, root_cost

        indent = "  " * depth
        cost = getattr(run, 'total_cost', None) or 0
        tokens = getattr(run, 'total_tokens', None) or 0

        # Extract input/output costs if available
        prompt_tokens = getattr(run, 'prompt_tokens', None) or 0
        completion_tokens = getattr(run, 'completion_tokens', None) or 0

        cost_str = f"${cost:.6f}" if cost > 0 else "$0"
        tokens_str = f"{tokens:,}" if tokens > 0 else "0"

        run_type_icon = {
            "llm": "🤖",
            "chain": "⛓️",
            "tool": "🔧",
        }.get(run.run_type, "❓")

        print(f"{indent}{run_type_icon} {run.name} ({run.run_type})")
        print(f"{indent}   Tokens: {tokens_str} | Cost: {cost_str}")

        if run.run_type == "llm":
            total_llm_cost += cost
            if prompt_tokens or completion_tokens:
                print(f"{indent}   Details: prompt={prompt_tokens}, completion={completion_tokens}")

        if str(run.id) == root_run_id:
            root_cost = cost

        # Print children
        run_children = children.get(str(run.id), [])
        for child in sorted(run_children, key=lambda r: r.start_time or datetime.min.replace(tzinfo=timezone.utc)):
            print_tree(child, depth + 1)

    # Find and print root
    root_runs = children.get(None, [])
    for root in root_runs:
        print_tree(root)

    print(f"\n--- Summary ---")
    print(f"Sum of LLM costs: ${total_llm_cost:.6f}")
    print(f"Root reported cost: ${root_cost:.6f}")
    if total_llm_cost > 0:
        ratio = root_cost / total_llm_cost
        status = "✅ OK" if 0.99 < ratio < 1.01 else "⚠️ DUPLICATED"
        print(f"Ratio: {ratio:.2f}x {status}")

    return total_llm_cost, root_cost


def main():
    parser = argparse.ArgumentParser(description="Analyze LangSmith cost duplication")
    parser.add_argument("--project", default="beneissue", help="LangSmith project name")
    parser.add_argument("--limit", type=int, default=5, help="Number of traces to analyze")
    parser.add_argument("--run-id", help="Specific run ID to analyze")
    parser.add_argument("--filter", default='eq(name, "LangGraph")', help="Filter for root runs")
    args = parser.parse_args()

    if not os.environ.get("LANGCHAIN_API_KEY"):
        print("Error: LANGCHAIN_API_KEY not set")
        sys.exit(1)

    client = Client()
    project_name = args.project

    if args.run_id:
        # Analyze specific run
        run = client.read_run(args.run_id)
        analyze_trace(client, project_name, str(run.trace_id), args.run_id)
    else:
        # Find recent root runs
        print(f"Fetching recent '{args.filter}' runs from '{project_name}'...")

        runs = list(client.list_runs(
            project_name=project_name,
            filter=args.filter,
            limit=args.limit,
        ))

        if not runs:
            print(f"No runs found matching filter: {args.filter}")
            return

        print(f"Found {len(runs)} runs")

        total_duplication = 0
        total_expected = 0

        for run in runs:
            llm_cost, root_cost = analyze_trace(
                client, project_name, str(run.trace_id), str(run.id)
            )
            total_expected += llm_cost
            total_duplication += (root_cost - llm_cost)

        print(f"\n{'='*60}")
        print("OVERALL SUMMARY")
        print('='*60)
        print(f"Total expected cost (LLM only): ${total_expected:.6f}")
        print(f"Total duplicated cost: ${total_duplication:.6f}")
        if total_expected > 0:
            waste_pct = (total_duplication / total_expected) * 100
            print(f"Waste percentage: {waste_pct:.1f}%")


if __name__ == "__main__":
    main()

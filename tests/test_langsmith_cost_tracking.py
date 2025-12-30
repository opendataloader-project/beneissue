"""Tests for LangSmith cost tracking and duplication issues.

This test reproduces and investigates the cost duplication issue where:
- claude_code_analyze: 32448 tokens, $0.038283
- analyze (parent): 32448 tokens, $0.076566 (2x)
- LangGraph (root): 32448 tokens, $0.114849 (3x)

The issue is that LangSmith accumulates costs from child spans into parent spans,
showing them as "Other" costs in the dashboard.
"""

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from langsmith import Client, get_current_run_tree, traceable

# Check if LangSmith is configured
def _is_langsmith_configured() -> bool:
    """Check if LangSmith env vars are available."""
    return bool(os.environ.get("LANGCHAIN_API_KEY"))


@pytest.mark.skipif(
    not _is_langsmith_configured(),
    reason="Requires LANGCHAIN_API_KEY for LangSmith",
)
class TestLangSmithCostTracking:
    """Tests to investigate LangSmith cost tracking behavior."""

    def test_cost_accumulation_in_nested_traces(self):
        """Test that demonstrates cost accumulation in nested traces.

        This test creates a nested trace structure similar to:
        - LangGraph (chain)
          - analyze (chain)
            - claude_code_analyze (llm)

        And sets usage metadata at the innermost level to see how costs propagate.
        """
        from langsmith import traceable

        # Simulate usage data similar to what Claude Code SDK returns
        mock_usage = {
            "input_tokens": 30000,
            "output_tokens": 2448,
            "total_tokens": 32448,
            "input_cost": 0.009,  # Approximate based on ratio
            "output_cost": 0.029283,  # Approximate based on ratio
        }

        @traceable(name="inner_claude_code", run_type="llm")
        def inner_llm_call():
            """Simulates the innermost LLM call (claude_code_analyze)."""
            run_tree = get_current_run_tree()
            if run_tree:
                # This is how we currently set usage
                run_tree.set(usage_metadata=mock_usage)
            return {"result": "analysis complete"}

        @traceable(name="analyze_node", run_type="chain")
        def analyze_wrapper():
            """Simulates the analyze node wrapper."""
            result = inner_llm_call()
            return result

        @traceable(name="langgraph_root", run_type="chain")
        def langgraph_wrapper():
            """Simulates the LangGraph root trace."""
            result = analyze_wrapper()
            return result

        # Run the nested trace
        result = langgraph_wrapper()

        # The test passes if no exception - actual verification needs LangSmith dashboard
        assert result == {"result": "analysis complete"}
        print("\n=== Cost Tracking Test Completed ===")
        print("Check LangSmith dashboard for trace: 'langgraph_root'")
        print(f"Expected behavior: Cost ${mock_usage['input_cost'] + mock_usage['output_cost']:.6f} should appear ONLY in 'inner_claude_code'")
        print("Bug behavior: Cost may be accumulated and appear 2x in 'analyze_node', 3x in 'langgraph_root'")

    def test_usage_metadata_propagation(self):
        """Test different methods of setting usage metadata."""
        from langsmith import traceable

        usage = {
            "input_tokens": 1000,
            "output_tokens": 500,
            "total_tokens": 1500,
            "input_cost": 0.003,
            "output_cost": 0.025,
        }

        # Method 1: Using run_tree.set()
        @traceable(name="method1_run_tree_set", run_type="llm")
        def method1():
            run_tree = get_current_run_tree()
            if run_tree:
                run_tree.set(usage_metadata=usage)
            return "done"

        # Method 2: Return usage in outputs (documented approach)
        @traceable(name="method2_return_usage", run_type="llm")
        def method2():
            return {"output": "done", "usage_metadata": usage}

        # Method 3: Using add_outputs
        @traceable(name="method3_add_outputs", run_type="llm")
        def method3():
            run_tree = get_current_run_tree()
            if run_tree:
                run_tree.add_outputs({"usage_metadata": usage})
            return "done"

        # Run all methods
        method1()
        method2()
        method3()

        print("\n=== Usage Metadata Methods Test Completed ===")
        print("Check LangSmith for traces: method1_run_tree_set, method2_return_usage, method3_add_outputs")
        print("Compare how costs appear in each method")

    def test_verify_no_double_counting_with_exclude_child_runs(self):
        """Test using exclude_child_runs to prevent cost aggregation."""
        from langsmith import traceable

        usage = {
            "input_tokens": 32448,
            "output_tokens": 2448,
            "total_tokens": 34896,
            "input_cost": 0.009,
            "output_cost": 0.029283,
        }

        @traceable(name="llm_with_usage", run_type="llm")
        def llm_call():
            run_tree = get_current_run_tree()
            if run_tree:
                run_tree.set(usage_metadata=usage)
            return "done"

        # Parent with metadata set to not aggregate child costs
        @traceable(name="parent_no_aggregate", run_type="chain", metadata={"exclude_child_runs": True})
        def parent_call():
            return llm_call()

        result = parent_call()

        print("\n=== Exclude Child Runs Test Completed ===")
        print("Check if 'exclude_child_runs' metadata prevents cost aggregation")


class TestLangSmithAPIAccess:
    """Tests for accessing LangSmith API directly."""

    @pytest.mark.skipif(
        not _is_langsmith_configured(),
        reason="Requires LANGCHAIN_API_KEY for LangSmith",
    )
    def test_fetch_recent_runs(self):
        """Test fetching recent runs from LangSmith API."""
        client = Client()

        # List recent runs from beneissue project
        project_name = os.environ.get("LANGCHAIN_PROJECT", "beneissue")

        runs = list(client.list_runs(
            project_name=project_name,
            limit=5,
        ))

        print(f"\n=== Recent Runs from '{project_name}' ===")
        for run in runs:
            print(f"\nRun: {run.name} (id={run.id[:8]}...)")
            print(f"  Type: {run.run_type}")
            print(f"  Status: {run.status}")
            if hasattr(run, 'total_tokens') and run.total_tokens:
                print(f"  Tokens: {run.total_tokens}")
            if hasattr(run, 'total_cost') and run.total_cost:
                print(f"  Cost: ${run.total_cost:.6f}")

            # Check for feedback/metrics
            feedback = client.list_run_feedback(run_id=run.id)
            feedback_list = list(feedback)
            if feedback_list:
                print(f"  Feedback: {len(feedback_list)} items")

    @pytest.mark.skipif(
        not _is_langsmith_configured(),
        reason="Requires LANGCHAIN_API_KEY for LangSmith",
    )
    def test_analyze_cost_breakdown(self):
        """Analyze cost breakdown for a specific trace to understand duplication."""
        client = Client()
        project_name = os.environ.get("LANGCHAIN_PROJECT", "beneissue")

        # Find recent analyze runs
        runs = list(client.list_runs(
            project_name=project_name,
            filter='eq(name, "LangGraph")',
            limit=3,
        ))

        if not runs:
            print("No LangGraph runs found")
            return

        for root_run in runs[:1]:  # Analyze first run
            print(f"\n=== Cost Analysis for Run {str(root_run.id)[:8]}... ===")

            # Get all child runs
            all_runs = list(client.list_runs(
                project_name=project_name,
                filter=f'eq(trace_id, "{root_run.trace_id}")',
            ))

            print(f"Total runs in trace: {len(all_runs)}")

            total_llm_cost = 0
            total_reported_cost = 0

            for run in sorted(all_runs, key=lambda r: r.start_time or datetime.min.replace(tzinfo=timezone.utc)):
                cost = getattr(run, 'total_cost', None) or 0
                tokens = getattr(run, 'total_tokens', None) or 0

                indent = "  "
                if run.parent_run_id:
                    indent = "    " if run.run_type == "llm" else "  "

                print(f"{indent}{run.name} ({run.run_type})")
                print(f"{indent}  Tokens: {tokens}, Cost: ${cost:.6f}")

                if run.run_type == "llm":
                    total_llm_cost += cost

                if run.id == root_run.id:
                    total_reported_cost = cost

            print(f"\n--- Summary ---")
            print(f"Sum of LLM costs: ${total_llm_cost:.6f}")
            print(f"Root reported cost: ${total_reported_cost:.6f}")
            if total_reported_cost > 0 and total_llm_cost > 0:
                ratio = total_reported_cost / total_llm_cost
                print(f"Ratio: {ratio:.2f}x (should be ~1.0 if no duplication)")


class TestCostDuplicationReproduction:
    """Reproduce exact cost duplication scenario."""

    @pytest.mark.skipif(
        not _is_langsmith_configured(),
        reason="Requires LANGCHAIN_API_KEY for LangSmith",
    )
    def test_reproduce_cost_duplication_exact(self):
        """Reproduce the exact cost duplication scenario from analyze workflow.

        Expected structure:
        - LangGraph (chain): Should NOT have its own cost
        - analyze (chain): Should NOT have its own cost
        - claude_code_analyze (llm): $0.038283 - ONLY here

        Bug behavior:
        - LangGraph shows $0.114849 (3x)
        - analyze shows $0.076566 (2x)
        - claude_code_analyze shows $0.038283 (1x)
        """
        from langsmith import traceable
        from beneissue.integrations.claude_code import UsageInfo

        # Exact values from the reported issue
        usage = UsageInfo(
            input_tokens=30000,
            output_tokens=2448,
            input_cost_usd=0.009,
            output_cost_usd=0.029283,
            model="claude-sonnet-4-20250514",
        )

        @traceable(name="claude_code_analyze_repro", run_type="llm")
        def claude_code_analyze():
            """Simulates claude_code_analyze node."""
            # Use the same method as production code
            usage.set_on_run_tree()
            return {"analysis": "completed", "usage": usage.to_langsmith_metadata()}

        @traceable(name="analyze_repro", run_type="chain")
        def analyze():
            """Simulates analyze node (wrapper)."""
            result = claude_code_analyze()
            # In production, we also return usage in state
            return {**result, "usage_metadata": usage.to_langsmith_metadata()}

        @traceable(name="LangGraph_repro", run_type="chain")
        def langgraph():
            """Simulates LangGraph root."""
            return analyze()

        result = langgraph()

        print("\n=== Cost Duplication Reproduction ===")
        print(f"Expected total cost: ${usage.total_cost_usd:.6f}")
        print("Check LangSmith dashboard for trace 'LangGraph_repro'")
        print("\nIf cost is duplicated, you'll see:")
        print(f"  - LangGraph_repro: ${usage.total_cost_usd * 3:.6f} (3x)")
        print(f"  - analyze_repro: ${usage.total_cost_usd * 2:.6f} (2x)")
        print(f"  - claude_code_analyze_repro: ${usage.total_cost_usd:.6f} (1x)")

        return result

    @pytest.mark.skipif(
        not _is_langsmith_configured(),
        reason="Requires LANGCHAIN_API_KEY for LangSmith",
    )
    def test_fix_attempt_outputs_only(self):
        """Attempt to fix by only returning usage in outputs, not setting on run_tree."""
        from langsmith import traceable

        usage = {
            "input_tokens": 30000,
            "output_tokens": 2448,
            "total_tokens": 32448,
            "input_cost": 0.009,
            "output_cost": 0.029283,
        }

        @traceable(name="llm_outputs_only", run_type="llm")
        def llm_with_outputs_only():
            """Only return usage in outputs, don't use set_on_run_tree."""
            # Return as part of the function output
            return {"result": "done", "usage_metadata": usage}

        @traceable(name="chain_outputs_only", run_type="chain")
        def chain_with_outputs_only():
            """Parent chain - should NOT get child's cost accumulated."""
            return llm_with_outputs_only()

        result = chain_with_outputs_only()
        print("\n=== Fix Attempt: Outputs Only ===")
        print("Check if returning usage_metadata only in outputs prevents duplication")

    @pytest.mark.skipif(
        not _is_langsmith_configured(),
        reason="Requires LANGCHAIN_API_KEY for LangSmith",
    )
    def test_fix_attempt_explicit_zero_parent_cost(self):
        """Attempt to fix by explicitly setting zero cost on parent chains."""
        from langsmith import traceable

        usage = {
            "input_tokens": 30000,
            "output_tokens": 2448,
            "total_tokens": 32448,
            "input_cost": 0.009,
            "output_cost": 0.029283,
        }

        zero_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "input_cost": 0.0,
            "output_cost": 0.0,
        }

        @traceable(name="llm_with_cost", run_type="llm")
        def llm_call():
            run_tree = get_current_run_tree()
            if run_tree:
                run_tree.set(usage_metadata=usage)
            return "done"

        @traceable(name="chain_zero_cost", run_type="chain")
        def chain_call():
            result = llm_call()
            # Explicitly set zero cost on parent to prevent aggregation
            run_tree = get_current_run_tree()
            if run_tree:
                run_tree.set(usage_metadata=zero_usage)
            return result

        result = chain_call()
        print("\n=== Fix Attempt: Explicit Zero Parent Cost ===")
        print("Check if setting zero usage on parent overrides accumulated cost")

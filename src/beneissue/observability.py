"""Observability utilities for workflow nodes.

Provides logging, timing, and tracing for LangGraph nodes.
"""

import functools
import sys
import time
from typing import Any, Callable, TypeVar

from langsmith import traceable

F = TypeVar("F", bound=Callable[..., Any])


def _log(message: str, level: str = "info", node: str = "node") -> None:
    """Log message to stderr for GitHub Actions visibility."""
    prefix = {
        "info": "ℹ️",
        "success": "✅",
        "error": "❌",
        "warning": "⚠️",
        "start": "🚀",
        "end": "🏁",
    }.get(level, "")
    print(f"{prefix} [{node}] {message}", file=sys.stderr, flush=True)


def traced_node(
    name: str,
    *,
    run_type: str = "chain",
    log_input: bool = False,
    log_output: bool = True,
) -> Callable[[F], F]:
    """Decorator to add tracing and logging to a LangGraph node.

    Combines LangSmith tracing with timing and logging for observability.

    Args:
        name: Name for the trace (e.g., "triage", "analyze").
        run_type: LangSmith run type ("chain", "llm", "tool").
        log_input: Whether to log input state keys.
        log_output: Whether to log output keys.

    Example:
        @traced_node("triage", log_output=True)
        def triage_node(state: IssueState) -> dict:
            ...
    """

    def decorator(func: F) -> F:
        # Apply LangSmith traceable decorator
        traced_func = traceable(name=name, run_type=run_type)(func)

        @functools.wraps(func)
        def wrapper(state: dict, *args: Any, **kwargs: Any) -> dict:
            # Pre-execution logging
            _log(f"Starting...", "start", name)
            if log_input:
                input_keys = [k for k in state.keys() if state.get(k) is not None]
                _log(f"Input keys: {input_keys}", "info", name)

            start_time = time.perf_counter()

            try:
                # Execute the node
                result = traced_func(state, *args, **kwargs)

                # Post-execution logging
                elapsed = time.perf_counter() - start_time
                elapsed_str = (
                    f"{elapsed:.2f}s" if elapsed >= 1 else f"{elapsed * 1000:.0f}ms"
                )

                if log_output and isinstance(result, dict):
                    output_keys = list(result.keys())
                    _log(f"Completed in {elapsed_str}, output: {output_keys}", "success", name)
                else:
                    _log(f"Completed in {elapsed_str}", "success", name)

                return result

            except Exception as e:
                elapsed = time.perf_counter() - start_time
                _log(f"Failed after {elapsed:.2f}s: {e}", "error", name)
                raise

        return wrapper  # type: ignore

    return decorator


def log_node_event(node: str, event: str, level: str = "info", **data: Any) -> None:
    """Log a custom event from within a node.

    Args:
        node: Node name.
        event: Event description.
        level: Log level (info, success, error, warning).
        **data: Additional data to log.

    Example:
        log_node_event("triage", "duplicate detected", duplicate_of=42)
    """
    if data:
        data_str = ", ".join(f"{k}={v}" for k, v in data.items())
        _log(f"{event} ({data_str})", level, node)
    else:
        _log(event, level, node)

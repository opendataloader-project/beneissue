"""Observability utilities for workflow nodes.

Provides logging, timing, and tracing for LangGraph nodes.
"""

import functools
import logging
import time
from typing import Any, Callable, TypeVar

from langsmith import traceable

F = TypeVar("F", bound=Callable[..., Any])

# Configure module logger
logger = logging.getLogger("beneissue")


def get_node_logger(node: str) -> logging.Logger:
    """Get a logger for a specific node."""
    return logging.getLogger(f"beneissue.{node}")


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
        node_logger = get_node_logger(name)

        @functools.wraps(func)
        def wrapper(state: dict, *args: Any, **kwargs: Any) -> dict:
            # Pre-execution logging
            node_logger.info("Starting...")
            if log_input:
                input_keys = [k for k in state.keys() if state.get(k) is not None]
                node_logger.info("Input keys: %s", input_keys)

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
                    node_logger.info("Completed in %s, output: %s", elapsed_str, output_keys)
                else:
                    node_logger.info("Completed in %s", elapsed_str)

                return result

            except Exception as e:
                elapsed = time.perf_counter() - start_time
                node_logger.error("Failed after %.2fs: %s", elapsed, e)
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
    node_logger = get_node_logger(node)
    log_func = getattr(node_logger, level if level in ("info", "warning", "error") else "info")

    if data:
        data_str = ", ".join(f"{k}={v}" for k, v in data.items())
        log_func("%s (%s)", event, data_str)
    else:
        log_func("%s", event)

# LangSmith Integration

beneissue uses LangSmith to trace LLM calls and workflow execution.

## Configuration

### Environment Variables

```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=your-api-key
export LANGCHAIN_PROJECT=beneissue  # optional
```

### Automatic Setup

LangSmith is automatically configured when running `beneissue` CLI commands.

```python
# src/beneissue/config.py
def setup_langsmith():
    if os.environ.get("LANGCHAIN_API_KEY"):
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGCHAIN_PROJECT", "beneissue")
```

## Applied Features

### 1. @traceable Decorator

Traces node execution using LangSmith's `@traceable`.

```python
from langsmith import traceable

@traceable(name="claude_code_analyze", run_type="chain")
def analyze_node(state: IssueState) -> dict:
    ...
```

### 2. @traced_node Custom Decorator

A custom decorator that combines `@traceable` with timing and logging.

```python
from beneissue.observability import traced_node, log_node_event

@traced_node("triage", run_type="chain", log_output=True)
def triage_node(state: IssueState) -> dict:
    ...
    log_node_event("triage", f"decision={response.decision}", "success")
    ...
```

**Provides:**
- Automatic LangSmith trace creation
- Execution time measurement and logging
- Input/output key logging
- Automatic error logging

### 3. Structured Logging

Stderr logging visible in GitHub Actions.

```
🚀 [intake] Starting...
ℹ️ [intake] Fetching issue #42 from owner/repo
✅ [intake] Completed in 523ms, output: [issue_title, issue_body, ...]
🚀 [triage] Starting...
✅ [triage] decision=valid
✅ [triage] Completed in 1.23s, output: [triage_decision, ...]
```

## Traced Nodes

| Node | Decorator | run_type |
|------|-----------|----------|
| `intake_node` | `@traced_node` | tool |
| `triage_node` | `@traced_node` | chain |
| `analyze_node` | `@traceable` | chain |

## Viewing in LangSmith Dashboard

1. Go to [LangSmith](https://smith.langchain.com)
2. Select project `beneissue`
3. View execution history in the Traces tab

**Available information:**
- Execution time per node
- LLM input/output (prompts, responses)
- Token usage
- Error locations

## Related Files

| File | Description |
|------|-------------|
| `src/beneissue/observability.py` | `@traced_node`, `log_node_event` |
| `src/beneissue/config.py` | `setup_langsmith()` |
| `src/beneissue/nodes/triage.py` | triage node (traced) |
| `src/beneissue/nodes/intake.py` | intake node (traced) |
| `src/beneissue/nodes/analyze.py` | analyze node (traceable) |

## Cost Tracking

You can view per-project token usage and costs in the LangSmith dashboard. Using `enable_cache=True` during development reduces duplicate LLM calls and saves costs.

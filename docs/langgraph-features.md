# LangGraph v1 Features

beneissue uses LangGraph v1.0.5 to implement its workflow orchestration.

## Applied Features

### 1. StateGraph-based Workflow

State-based graph workflow with conditional routing.

```
intake → triage → analyze → fix → apply_labels
              ↓         ↓       ↓
        apply_labels  post_comment
```

**File:** `src/beneissue/graph/workflow.py`

### 2. Node-level Caching

Caching is applied to expensive nodes that include LLM calls.

```python
from beneissue.graph.workflow import create_full_workflow

# Enable caching (reduces API costs during development/testing)
graph = create_full_workflow(enable_cache=True)
```

**Cached nodes:**
- `triage`: Issue classification (TTL: 1 hour)
- `analyze`: Issue analysis (TTL: 1 hour)

**How it works:**
- Returns cached results for identical inputs
- Uses `InMemoryCache` (persists for process lifetime)
- Useful for iterative testing during development

### 3. Checkpointing

Save workflow state to resume from interruption points.

```python
from langgraph.checkpoint.memory import MemorySaver
from beneissue.graph.workflow import create_full_workflow, get_thread_id

checkpointer = MemorySaver()
graph = create_full_workflow(checkpointer=checkpointer)

thread_id = get_thread_id("owner/repo", 123)
config = {"configurable": {"thread_id": thread_id}}

result = graph.invoke(state, config)
```

**Use cases:**
- State debugging during local development
- State recovery in long-running servers

**Note:** In GitHub Actions' one-shot execution, `MemorySaver` is lost when the process terminates. For persistent storage, use `SqliteSaver` or external storage.

### 4. Convenience Functions

```python
from beneissue.graph.workflow import create_checkpointed_workflow

# Create workflow with checkpointer
graph, checkpointer = create_checkpointed_workflow(
    "full",           # "triage", "analyze", "fix", "full"
    enable_cache=True,
)
```

## Not Applied

### Human-in-the-loop (interrupt)

The `interrupt_before` feature is not applied as it's incompatible with GitHub Actions environment.

**Reasons:**
- GitHub Actions runs one-shot executions
- State is lost when workflow terminates
- Cannot wait for user input

**Suitable environments:**
- LangGraph Cloud / LangServe
- Slack/Discord bots
- Interactive CLI

## Related Files

| File | Description |
|------|-------------|
| `src/beneissue/graph/workflow.py` | Workflow definition and factory functions |
| `src/beneissue/graph/state.py` | `IssueState` schema |
| `src/beneissue/graph/routing.py` | Conditional routing functions |

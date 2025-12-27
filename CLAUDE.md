# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

beneissue is an AI-powered GitHub issue automation tool that automatically triages, analyzes, and fixes issues. It uses LangGraph for workflow orchestration, LangChain/Anthropic for triage decisions, and Claude Code CLI for analysis and fixes.

## Commands

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run single test file
uv run pytest tests/test_routing.py

# Run tests with specific marker
uv run pytest -m triage
uv run pytest -m ai  # Tests requiring API calls

# Run policy tests (uses test cases in .claude/skills/beneissue/tests/cases/)
uv run beneissue test
uv run beneissue test --path examples/calculator  # Test specific project
uv run beneissue test --case duplicate            # Run specific test case
uv run beneissue test --dry-run                   # Validate without running AI

# CLI commands (for local testing)
uv run beneissue triage owner/repo --issue 123   # triage only
uv run beneissue analyze owner/repo --issue 123  # analyze only
uv run beneissue fix owner/repo --issue 123      # fix only
uv run beneissue run owner/repo --issue 123      # full workflow
```

## Architecture

### LangGraph Workflows

Four independent workflows defined in `src/beneissue/graph/workflow.py`:

- **triage_graph**: `intake → triage → apply_labels`
- **analyze_graph**: `intake → analyze → apply_labels`
- **fix_graph**: `intake → fix → apply_labels`
- **full_graph**: `intake → triage → analyze → fix → apply_labels` (with conditional routing)

Each can be invoked independently via CLI or `@beneissue` comments. State flows through `IssueState` (defined in `graph/state.py`).

### Node Implementations

- **intake** (`nodes/intake.py`): Fetches issue data and existing issues from GitHub
- **triage** (`nodes/triage.py`): Uses LangChain with Claude Haiku to classify issues (valid/invalid/duplicate/needs_info)
- **analyze** (`nodes/analyze.py`): Runs Claude Code CLI with Read/Glob/Grep tools to analyze codebase
- **fix** (`nodes/fix.py`): Runs Claude Code CLI with full edit permissions to implement fixes
- **actions** (`nodes/actions.py`): Applies labels and posts comments to GitHub

### Prompts

Prompts are stored as markdown files in `src/beneissue/prompts/`:
- `triage.md` - Classification decision prompt
- `analyze.md` - Issue analysis prompt (outputs structured JSON)
- `fix.md` - Fix implementation prompt

### Configuration

Config loaded from `.claude/skills/beneissue/beneissue-config.yml` with fallback to defaults in `config.py`. Key settings:
- `models.triage`: Model for triage (default: claude-haiku-4-5)
- `team`: List of assignees with specialties
- `limits.daily`: Rate limits for triage/analyze/fix operations

### Structured Output Schemas

All AI responses use Pydantic models in `nodes/schemas.py`:
- `TriageResult`: decision, reason, duplicate_of, questions
- `AnalyzeResult`: summary, affected_files, fix_decision, priority, story_points, assignee
- `FixResult`: success, title, description, error

### Label System

Labels are defined in `labels.py` and synced via `beneissue labels` command:
- `triage/valid`, `triage/invalid`, `triage/duplicate`, `triage/needs-info`
- `fix/auto-eligible`, `fix/manual-required`, `fix/completed`

### Metrics Collection

Metrics are stored in Supabase PostgreSQL. Code in `src/beneissue/metrics/`:

- **schemas.py**: `WorkflowRunRecord` Pydantic model with all workflow fields
- **storage.py**: `MetricsStorage` class with Supabase client, `save_run()` method
- **collector.py**: `MetricsCollector` class and `record_metrics_node` LangGraph node

**Workflow integration**: All graphs end with `→ record_metrics → END`. The node:
1. Skips if `dry_run` or `no_action` mode
2. Skips if `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` not configured
3. Converts `IssueState` to `WorkflowRunRecord` and saves to Supabase

**Environment variables** (optional):
- `SUPABASE_URL`: Project URL
- `SUPABASE_SERVICE_KEY`: Service role key for write access

**Database setup**: Run `scripts/sql/001_create_tables.sql` in Supabase SQL Editor.

**Testing**: Integration tests auto-load `.env` file via `tests/conftest.py`:
```bash
uv run pytest tests/test_metrics.py -v                    # All metrics tests
uv run pytest tests/test_metrics.py::TestMetricsIntegration -v  # Supabase integration only
```

---
name: beneissue
description: AI-powered GitHub issue automation. Automatically triages, analyzes, and fixes issues.
---

# beneissue

Automatically process GitHub issues with AI.

## What it does

When an issue is opened:
1. **Triage** → classifies as valid/invalid/duplicate/needs-info
2. **Analyze** → identifies affected files, fix approach, scores fixability
3. **Fix** → if score ≥ 80, Claude Code creates a PR

## Issue comment commands

```
@beneissue triage    # Re-classify this issue
@beneissue analyze   # Run full analysis
@beneissue fix       # Attempt auto-fix
```

## Configuration

Edit `beneissue-config.yml` in this directory to customize:
- Models (triage, analyze)
- Auto-fix policy (enabled, min_score)
- Project description for AI context

## Labels applied

| Label | Meaning |
|-------|---------|
| `triage/valid` | Ready for analysis |
| `triage/needs-info` | Waiting for details |
| `fix/auto-eligible` | Will be auto-fixed |
| `fix/completed` | PR created |

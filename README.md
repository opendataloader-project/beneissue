# beneissue

Drowning in GitHub issues? beneissue automatically triages them and creates PRs for simple fixes.

## Who is this for?

- **Open source maintainers** with 100+ issues piling up
- **Small teams** who can't afford to manually label every issue
- **Solo developers** who want typo fixes handled automatically

## What changes after you install it?

| Before | After |
|--------|-------|
| Issue opened → check it days later | Issue opened → instantly classified + labeled |
| Manually comment "need more info" | Auto-asks specific follow-up questions |
| Fix simple bugs yourself | Score 80+ issues get auto-PR via Claude Code |

## Get started in 5 minutes

```bash
pip install beneissue
cd your-repo
beneissue init
```

Done. New issues will be processed automatically.

### Verify it works

When an issue gets these labels, you're set:
- `triage/valid` — Valid issue, ready for work
- `fix/auto-eligible` — Will be auto-fixed

## How it works

```
Issue opened
    ↓
[Triage] → valid / invalid / duplicate / needs-info
    ↓
[Analyze] → affected files, fix approach, score (0-100)
    ↓
[Fix] → score ≥ 80? → Claude Code creates PR
```

## CLI Commands

```bash
# Process a specific issue
beneissue triage owner/repo --issue 123
beneissue analyze owner/repo --issue 123
beneissue fix owner/repo --issue 123

# Dry run (no GitHub changes)
beneissue analyze owner/repo --issue 123 --dry-run

# Setup commands
beneissue init      # Initialize in current repo
beneissue labels    # Sync labels to GitHub
beneissue test      # Run policy tests
```

## Configuration

Edit `.claude/skills/beneissue/beneissue.yml`:

```yaml
version: "1.0"

project:
  name: "my-project"
  description: |
    Brief description of your project.
    Include any special triage rules here.

models:
  triage: claude-haiku-4-5    # Fast, cheap
  analyze: claude-sonnet-4    # Balanced
  fix: claude-sonnet-4

policy:
  auto_fix:
    enabled: true
    min_score: 80  # Minimum score for auto-fix
```

## GitHub Action

The workflow triggers on:
- New issues (`issues: opened`)
- Comments with `@beneissue` commands

```yaml
# Manual commands in issue comments:
@beneissue triage   # Classify the issue
@beneissue analyze  # Full analysis
@beneissue fix      # Attempt auto-fix
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `BENEISSUE_TOKEN` | Yes | GitHub token with repo access |
| `LANGCHAIN_API_KEY` | No | LangSmith for tracing |

## Labels

| Label | Meaning |
|-------|---------|
| `triage/valid` | Valid issue, ready for analysis |
| `triage/invalid` | Out of scope or spam |
| `triage/duplicate` | Already reported |
| `triage/needs-info` | Waiting for more details |
| `fix/auto-eligible` | Score ≥ 80, will be auto-fixed |
| `fix/manual-required` | Score 50-79, needs human |
| `fix/completed` | Auto-fix PR created |

## License

Apache 2.0

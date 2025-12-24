# beneissue

Drowning in GitHub issues? Install beneissue once, and it handles the rest automatically.

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

## Install once, runs forever

```bash
pip install beneissue
cd your-repo
beneissue init
```

That's it. From now on:

1. **New issue opened** → automatically triaged and labeled
2. **High-score issues** → Claude Code creates a PR
3. **Need manual control?** → just comment on the issue

### Control via issue comments

```
@beneissue triage    # Re-classify this issue
@beneissue analyze   # Run full analysis
@beneissue fix       # Attempt auto-fix now
```

No CLI needed. Just talk to the bot in the issue thread.

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

## Verify it's working

When issues get these labels automatically, you're set:
- `triage/valid` — Valid issue, ready for work
- `fix/auto-eligible` — Will be auto-fixed

## Configuration

Edit `.claude/skills/beneissue/beneissue-config.yml`:

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

policy:
  auto_fix:
    enabled: true
    min_score: 80  # Minimum score for auto-fix
```

## Environment Variables

Set these in your GitHub repository secrets:

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

## CLI (optional)

For manual runs or debugging:

```bash
beneissue triage owner/repo --issue 123
beneissue analyze owner/repo --issue 123 --dry-run
beneissue fix owner/repo --issue 123
```

## License

Apache 2.0

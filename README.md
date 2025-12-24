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

### 1. Install the package

```bash
pip install beneissue
```

### 2. Set up GitHub repository secrets

Go to your repo → Settings → Secrets and variables → Actions, and add:

| Secret | Required | Description |
|--------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Your Claude API key |
| `LANGCHAIN_API_KEY` | No | LangSmith for tracing |

### 3. Initialize in your repo

```bash
cd your-repo
beneissue init
git add .github/ .claude/
git commit -m "Add beneissue automation"
git push
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

| Command | Description |
|---------|-------------|
| `beneissue init` | Initialize beneissue in current repo |
| `beneissue triage <repo> --issue <n>` | Classify issue (no GitHub actions) |
| `beneissue analyze <repo> --issue <n>` | Full analysis + apply labels |
| `beneissue analyze <repo> --issue <n> --dry-run` | Analysis without GitHub changes |
| `beneissue fix <repo> --issue <n>` | Attempt auto-fix |
| `beneissue labels` | Sync labels to repository |
| `beneissue test` | Run policy tests |
| `beneissue test --dry-run` | Validate test cases only |

## License

Apache 2.0

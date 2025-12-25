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
| Fix simple bugs yourself | Auto-eligible issues get auto-PR via Claude Code |

## Install once, runs forever

### 1. Install the package

```bash
pip install beneissue
```

### 2. Set up GitHub repository

**Secrets:** Go to Settings → Secrets and variables → Actions:

| Secret | Required | Description |
|--------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Your Claude API key |
| `LANGCHAIN_API_KEY` | No | LangSmith for tracing |

**Permissions:** Go to Settings → Actions → General → Workflow permissions:
- Enable "Allow GitHub Actions to create and approve pull requests"

### 3. Initialize in your repo

```bash
cd your-repo
beneissue init
git push
```

That's it. From now on:

1. **New issue opened** → automatically triaged and labeled
2. **Auto-eligible issues** → Claude Code creates a PR
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
[Analyze] → affected files, fix approach, checklist
    ↓
[Fix] → auto-eligible? → Claude Code creates PR
```

## Verify it's working

When issues get these labels automatically, you're set:
- `triage/valid` — Valid issue, ready for work
- `fix/auto-eligible` — Will be auto-fixed

## Configuration

Edit `.claude/skills/beneissue/beneissue-config.yml`:

```yaml
version: "1.0"

models:
  triage: claude-haiku-4-5    # Fast, cheap (~$0.02/call)

limits:
  daily:
    triage: 50   # ~$1/day
    analyze: 20  # ~$2-10/day
    fix: 5       # ~$5-25/day

team:
  - github_id: "your-github-id"
    available: true
    specialties: ["backend", "python"]

observability:
  langsmith:
    enabled: true
    project: "beneissue"
```

## Labels

| Label | Meaning |
|-------|---------|
| `triage/valid` | Valid issue, ready for analysis |
| `triage/invalid` | Out of scope or spam |
| `triage/duplicate` | Already reported |
| `triage/needs-info` | Waiting for more details |
| `fix/auto-eligible` | Passes checklist, will be auto-fixed |
| `fix/manual-required` | Needs human review |
| `fix/completed` | Auto-fix PR created |

## CLI (optional)

For manual runs or debugging:

| Command | Description |
|---------|-------------|
| `beneissue triage <repo> --issue <n>` | Classify issue only |
| `beneissue analyze <repo> --issue <n>` | Analyze issue only (no triage, no fix) |
| `beneissue fix <repo> --issue <n>` | Fix issue only (no triage, no analysis) |
| `beneissue run <repo> --issue <n>` | Full workflow: triage → analyze → fix |
| `beneissue init` | Initialize beneissue in current repo |
| `beneissue labels` | Sync labels to repository |
| `beneissue test` | Run policy tests |

Add `--dry-run` to triage/analyze to skip GitHub actions.

## License

Apache 2.0

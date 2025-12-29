# BeneIssue

AI-Agentic issue automation for GitHub.

Drowning in GitHub issues? Install `beneissue` once, and it handles the rest automatically.

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

## How it works

![BeneIssue Workflow](https://raw.githubusercontent.com/opendataloader-project/beneissue/main/docs/images/workflow.png)

**Three stages:**

| Stage | What it does | Model |
|-------|--------------|-------|
| **Triage** | Classify issue → valid / invalid / duplicate / needs-info | Haiku (fast, ~$0.02) |
| **Analyze** | Find affected files, plan fix approach, check eligibility | Claude Code |
| **Fix** | Create branch, apply fix, open PR | Claude Code |

## Install once, runs forever

### 1. Install the package

```bash
pip install beneissue
```

### 2. Set up GitHub repository

**Secrets:** Go to Settings → Secrets and variables → Actions → Secrets tab:

| Secret | Required | Description |
|--------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Your Claude API key |
| `LANGCHAIN_API_KEY` | No | LangSmith for tracing |

**Variables:** Go to Settings → Secrets and variables → Actions → Variables tab:

| Variable | Required | Description |
|----------|----------|-------------|
| `LANGCHAIN_PROJECT` | No | LangSmith project name (default: `beneissue`) |

**Permissions:** Go to Settings → Actions → General → Workflow permissions:
- Enable "Allow GitHub Actions to create and approve pull requests"

### 3. Initialize in your repo

```bash
cd your-repo
beneissue init
git push
```

This creates:

```
your-repo/
├── .github/workflows/
│   └── beneissue-workflow.yml   # Triggers on issue events
└── .claude/skills/beneissue/
    ├── SKILL.md                 # Claude Code instructions
    └── beneissue-config.yml     # Your settings
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

## GitHub Actions triggers

| Event | Trigger | Action |
|-------|---------|--------|
| Issue opened/reopened | Automatic | Runs `analyze` (triage → analyze) |
| `@beneissue triage` | Comment | Re-classify the issue |
| `@beneissue analyze` | Comment | Run full analysis |
| `@beneissue fix` | Comment | Attempt auto-fix now |
| `@beneissue run` | Comment | Full pipeline: triage → analyze → fix |

## Verify it's working

When issues get these labels automatically, you're set:
- `triage/valid` — Valid issue, ready for work
- `fix/auto-eligible` — Will be auto-fixed

## Configuration

Edit `.claude/skills/beneissue/beneissue-config.yml`:

```yaml
version: "1.0"

limits:
  daily:
    triage: 50   # ~$1/day
    analyze: 20  # ~$2-10/day
    fix: 5       # ~$5-25/day

team:
  - github_id: "your-github-id"
    available: true
    specialties: ["backend", "python"]
```

### LangSmith (optional)

Enable LangSmith tracing to monitor and debug your workflows.

**For GitHub Actions:** Add to repository secrets/variables:

| Type | Name | Description |
|------|------|-------------|
| Secret | `LANGCHAIN_API_KEY` | Your LangSmith API key |
| Variable | `LANGCHAIN_PROJECT` | Project name (default: `beneissue`) |

**For local development:**

```bash
export LANGCHAIN_API_KEY=your-langsmith-api-key
export LANGCHAIN_PROJECT=your-project-name  # default: beneissue
```

When `LANGCHAIN_API_KEY` is set, LangSmith tracing is automatically enabled. Traces will appear in the specified project (or `beneissue` if not set).

### Metrics Storage (optional)

Store workflow metrics in Supabase for dashboards and analytics:

**1. Create a Supabase project** at [supabase.com](https://supabase.com)

**2. Run the SQL setup script:**

```sql
-- Copy contents from scripts/sql/001_create_tables.sql
-- Run in Supabase SQL Editor
```

**3. Set environment variables:**

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Your Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Service role key (for write access) |

> **Note:** `SUPABASE_SERVICE_ROLE_KEY` is also supported (Vercel integration naming).

```bash
export SUPABASE_URL=https://your-project.supabase.co
export SUPABASE_SERVICE_KEY=your-service-role-key
```

When both variables are set, metrics are automatically recorded after each workflow run. Without these variables, beneissue works normally but skips metrics storage.

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

## Policy Testing

Validate your triage/analyze rules before deploying:

```
your-repo/.claude/skills/beneissue/tests/cases/
├── triage-valid-bug.json
├── triage-invalid-spam.json
└── analyze-auto-eligible-typo.json
```

```bash
beneissue test                    # Run all test cases
beneissue test --case spam        # Run specific case
beneissue test --dry-run          # Validate without AI calls
```

See [examples/calculator](examples/calculator/.claude/skills/beneissue/tests/cases/) for sample test cases.

## License

Apache 2.0

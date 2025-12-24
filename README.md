# beneissue

AI-powered GitHub issue automation framework using LangGraph and Claude.

## Features

- **Triage**: Classify issues as valid, invalid, duplicate, or needs-info
- **Analyze**: Deep analysis with affected files, fix approach, and scoring
- **Fix**: Auto-fix eligible issues using Claude Code
- **Auto-labeling**: Automatically apply labels based on analysis
- **LangSmith Integration**: Full observability with tracing

## Installation

```bash
pip install beneissue
```

## Quick Start

```bash
# Initialize beneissue in your repository
cd your-repo
beneissue init

# This creates:
# - .github/workflows/beneissue.yml (GitHub Action)
# - .claude/skills/beneissue/ (skill config + test cases)
# - GitHub labels for triage/fix status
```

## CLI Commands

```bash
# Triage only (no GitHub actions)
beneissue triage owner/repo --issue 123

# Full analysis with labels and comments
beneissue analyze owner/repo --issue 123

# Dry run (no GitHub actions)
beneissue analyze owner/repo --issue 123 --dry-run

# Attempt auto-fix
beneissue fix owner/repo --issue 123

# Sync labels to repository
beneissue labels

# Run policy tests
beneissue test
beneissue test --dry-run  # Validate test cases only
```

## Repository Setup

After running `beneissue init`, your repository will have:

```
your-repo/
├── .github/workflows/
│   └── beneissue.yml          # GitHub Action workflow
└── .claude/skills/beneissue/
    ├── SKILL.md               # Skill definition
    ├── beneissue.yml          # Configuration
    ├── prompts/               # Custom prompts (optional)
    └── tests/cases/           # Policy test cases
        ├── triage-valid-bug.json
        ├── triage-needs-info.json
        └── triage-invalid-spam.json
```

## Configuration

Edit `.claude/skills/beneissue/beneissue.yml`:

```yaml
version: "1.0"

project:
  name: "my-project"
  description: "Project description for AI context"

# Override default models
models:
  triage: claude-haiku-4-5
  analyze: claude-sonnet-4
  fix: claude-sonnet-4

# Auto-fix policy
policy:
  auto_fix:
    enabled: true
    min_score: 80  # Minimum score for auto-fix eligibility
```

## GitHub Action

The generated workflow triggers on:
- New issues (`issues: opened`)
- Issue comments with `@beneissue` commands

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
| `LANGCHAIN_API_KEY` | No | LangSmith API key for tracing |
| `BENEISSUE_MODEL_TRIAGE` | No | Override triage model |
| `BENEISSUE_MODEL_ANALYZE` | No | Override analyze model |

## Policy Tests

Create test cases to validate your triage/analyze behavior:

```json
{
  "name": "Valid bug report",
  "stage": "triage",
  "input": {
    "title": "App crashes on startup",
    "body": "## Steps to reproduce\n1. Open app\n2. See crash"
  },
  "expected": {
    "decision": "valid",
    "reason_contains": ["crash", "reproduce"]
  }
}
```

Run tests:
```bash
beneissue test                    # Run all tests
beneissue test --case valid-bug   # Run specific test
beneissue test --stage triage     # Run only triage tests
beneissue test --dry-run          # Validate without API calls
```

## Labels

beneissue uses these labels:

| Label | Description |
|-------|-------------|
| `triage/valid` | Valid issue, ready for analysis |
| `triage/invalid` | Out of scope or invalid |
| `triage/duplicate` | Duplicate issue |
| `triage/needs-info` | Needs more information |
| `fix/auto-eligible` | Eligible for auto-fix (score >= 80) |
| `fix/manual-required` | Requires manual implementation |
| `fix/completed` | Fix completed |
| `fix/failed` | Fix attempted but failed |

## License

Apache 2.0

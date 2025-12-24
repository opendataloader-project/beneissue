# beneissue

AI-powered GitHub issue automation framework using LangGraph and Claude.

## Features

- **Triage**: Classify issues as valid, invalid, duplicate, or needs-info
- **Analyze**: Deep analysis with affected files, fix approach, and scoring
- **Auto-labeling**: Automatically apply labels based on analysis
- **LangSmith Integration**: Full observability with tracing

## Installation

```bash
pip install beneissue
```

## CLI Usage

```bash
# Triage only (no GitHub actions)
beneissue triage owner/repo --issue 123

# Full analysis with labels and comments
beneissue analyze owner/repo --issue 123

# Dry run (no GitHub actions)
beneissue analyze owner/repo --issue 123 --dry-run
```

## GitHub Action

```yaml
name: beneissue

on:
  issues:
    types: [opened]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: opendataloader-project/beneissue@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          anthropic-api-key: ${{ secrets.ANTHROPIC_API_KEY }}
          langchain-api-key: ${{ secrets.LANGCHAIN_API_KEY }}
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key |
| `BENEISSUE_TOKEN` | GitHub token |
| `LANGCHAIN_API_KEY` | LangSmith API key (optional) |

## License

Apache 2.0

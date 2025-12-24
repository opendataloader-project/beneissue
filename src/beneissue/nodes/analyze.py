"""Analyze node implementation using Claude Code."""

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

from langsmith import traceable

from beneissue.config import load_config
from beneissue.graph.state import IssueState
from beneissue.nodes.schemas import AnalyzeResult

# Load prompt from file
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "analyze.md"
ANALYZE_PROMPT = PROMPT_PATH.read_text()

# Timeout for Claude Code execution (3 minutes for analysis)
CLAUDE_CODE_TIMEOUT = 180


def _clone_repo(repo: str, target_dir: str) -> bool:
    """Clone a repository to a target directory."""
    token = os.environ.get("BENEISSUE_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        repo_url = f"https://x-access-token:{token}@github.com/{repo}.git"
    else:
        repo_url = f"https://github.com/{repo}.git"

    result = subprocess.run(
        ["git", "clone", "--depth", "1", repo_url, target_dir],
        capture_output=True,
        timeout=60,
    )
    return result.returncode == 0


def _build_analyze_prompt(state: IssueState) -> str:
    """Build the analyze prompt for Claude Code."""
    config = load_config()
    project_desc = config.project.description or f"Repository: {state['repo']}"

    # Claude Code will explore the codebase directly
    system_context = ANALYZE_PROMPT.format(
        project_description=project_desc,
        codebase_structure="Use Glob and Read tools to explore the codebase.",
    )

    return f"""{system_context}

---

## Issue to Analyze

**Title**: {state['issue_title']}

**Body**:
{state['issue_body']}

**Repository**: {state['repo']}

---

## Instructions

1. Use Read, Glob, and Grep tools to explore the codebase
2. Identify affected files by searching for relevant code
3. Analyze the scope, risk, and complexity
4. Return your analysis as JSON with this exact structure:

```json
{{
  "summary": "Brief summary of the issue and what needs to be done",
  "affected_files": ["path/to/file1.py", "path/to/file2.py"],
  "approach": "Recommended approach to fix the issue",
  "score": {{
    "total": 85,
    "scope": 25,
    "risk": 25,
    "verifiability": 20,
    "clarity": 15
  }},
  "priority": "P2",
  "story_points": 2,
  "labels": ["bug", "backend"],
  "comment_draft": null
}}
```

IMPORTANT: Your final output MUST be valid JSON matching this structure.
"""


def _parse_analyze_response(output: str) -> AnalyzeResult | None:
    """Parse Claude Code output to extract AnalyzeResult."""
    # Try to extract JSON from code blocks
    json_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", output, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            return AnalyzeResult(**data)
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    # Try to find raw JSON object with summary key
    json_match = re.search(r'\{[^{}]*"summary"[^}]*\}', output, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            return AnalyzeResult(**data)
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    # Try parsing entire output as JSON
    try:
        data = json.loads(output)
        return AnalyzeResult(**data)
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    return None


@traceable(name="claude_code_analyze", run_type="chain")
def analyze_node(state: IssueState) -> dict:
    """Analyze an issue using Claude Code CLI."""
    config = load_config()
    prompt = _build_analyze_prompt(state)

    # Create temporary directory for the repo
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = os.path.join(temp_dir, "repo")

        # Clone the repository
        if not _clone_repo(state["repo"], repo_path):
            # Fallback: return minimal analysis without codebase access
            return _fallback_analyze("Failed to clone repository")

        try:
            # Run Claude Code with read-only tools
            result = subprocess.run(
                [
                    "claude",
                    "-p",
                    prompt,
                    "--allowedTools",
                    "Read,Glob,Grep",
                    "--output-format",
                    "text",
                ],
                capture_output=True,
                timeout=CLAUDE_CODE_TIMEOUT,
                cwd=repo_path,
                env={
                    **os.environ,
                    "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
                },
            )

            stdout = result.stdout.decode() if result.stdout else ""

            # Parse the response
            response = _parse_analyze_response(stdout)

            if response:
                return _build_result(response, config)
            else:
                # Parsing failed, return fallback
                return _fallback_analyze(
                    f"Failed to parse analysis output: {stdout[:200]}"
                )

        except subprocess.TimeoutExpired:
            return _fallback_analyze(
                f"Analysis timeout after {CLAUDE_CODE_TIMEOUT} seconds"
            )
        except FileNotFoundError:
            return _fallback_analyze(
                "Claude Code CLI not installed. Run: npm install -g @anthropic-ai/claude-code"
            )
        except Exception as e:
            return _fallback_analyze(str(e)[:200])


def _build_result(response: AnalyzeResult, config) -> dict:
    """Build the result dict from AnalyzeResult."""
    min_score = config.policy.auto_fix.min_score
    fix_decision: Literal["auto_eligible", "manual_required", "comment_only"]

    if config.policy.auto_fix.enabled and response.score.total >= min_score:
        fix_decision = "auto_eligible"
    elif response.score.total >= 50:
        fix_decision = "manual_required"
    else:
        fix_decision = "comment_only"

    return {
        "analysis_summary": response.summary,
        "affected_files": response.affected_files,
        "fix_approach": response.approach,
        "score": response.score.model_dump(),
        "fix_decision": fix_decision,
        "comment_draft": response.comment_draft,
        "labels_to_add": [
            f"priority/{response.priority.lower()}",
            f"sp/{response.story_points}",
            f"fix/{fix_decision.replace('_', '-')}",
            *response.labels,
        ],
    }


def _fallback_analyze(error: str) -> dict:
    """Return a fallback analysis when Claude Code fails."""
    return {
        "analysis_summary": f"Analysis incomplete: {error}",
        "affected_files": [],
        "fix_approach": "Manual investigation required",
        "score": {"total": 0, "scope": 0, "risk": 0, "verifiability": 0, "clarity": 0},
        "fix_decision": "manual_required",
        "comment_draft": f"Automated analysis encountered an issue: {error}\n\nPlease investigate manually.",
        "labels_to_add": ["fix/manual-required"],
    }



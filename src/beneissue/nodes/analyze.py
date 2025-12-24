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
    return ANALYZE_PROMPT.format(
        issue_title=state["issue_title"],
        issue_body=state["issue_body"],
    )


def _parse_analyze_response(output: str) -> AnalyzeResult | None:
    """Parse Claude Code output to extract AnalyzeResult."""
    # Try to extract JSON from code blocks (greedy match for complete JSON)
    json_match = re.search(r"```(?:json)?\s*\n?(\{.*\})\s*\n?```", output, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            return AnalyzeResult(**data)
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    # Try to find any JSON object that starts with { and contains "summary"
    # Use a more robust approach: find all { and try to parse from each
    for match in re.finditer(r'\{', output):
        start_idx = match.start()
        # Try to find matching closing brace by counting braces
        brace_count = 0
        end_idx = start_idx
        for i, char in enumerate(output[start_idx:], start=start_idx):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break

        if end_idx > start_idx:
            candidate = output[start_idx:end_idx]
            if '"summary"' in candidate:
                try:
                    data = json.loads(candidate)
                    return AnalyzeResult(**data)
                except (json.JSONDecodeError, ValueError, TypeError):
                    continue

    # Try parsing entire output as JSON
    try:
        data = json.loads(output)
        return AnalyzeResult(**data)
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    return None


def _run_analysis(repo_path: str, prompt: str, config, *, verbose: bool = False) -> dict:
    """Run Claude Code analysis on a repository path."""
    try:
        cmd = [
            "claude",
            "-p",
            prompt,
            "--allowedTools",
            "Read,Glob,Grep",
        ]
        if verbose:
            cmd.append("--verbose")

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=CLAUDE_CODE_TIMEOUT,
            cwd=repo_path,
            env={
                **os.environ,
                "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
            },
        )

        stdout = result.stdout.decode() if result.stdout else ""

        response = _parse_analyze_response(stdout)

        if response:
            return _build_result(response, config)
        else:
            return _fallback_analyze(f"Failed to parse analysis output: {stdout[:200]}")

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


@traceable(name="claude_code_analyze", run_type="chain")
def analyze_node(state: IssueState) -> dict:
    """Analyze an issue using Claude Code CLI."""
    config = load_config()
    prompt = _build_analyze_prompt(state)
    verbose = state.get("verbose", False)

    # Use project_root if provided (for testing), otherwise clone
    if state.get("project_root"):
        return _run_analysis(str(state["project_root"]), prompt, config, verbose=verbose)

    # Create temporary directory for the repo
    with tempfile.TemporaryDirectory() as temp_dir:
        repo_path = os.path.join(temp_dir, "repo")

        # Clone the repository
        if not _clone_repo(state["repo"], repo_path):
            return _fallback_analyze("Failed to clone repository")

        return _run_analysis(repo_path, prompt, config, verbose=verbose)


def _build_result(response: AnalyzeResult, config) -> dict:
    """Build the result dict from AnalyzeResult."""
    threshold = config.scoring.threshold
    fix_decision: Literal["auto_eligible", "manual_required", "comment_only"]

    if response.score.total >= threshold:
        fix_decision = "auto_eligible"
    elif response.score.total >= 50:
        fix_decision = "manual_required"
    else:
        fix_decision = "comment_only"

    return {
        "analysis_summary": response.summary,
        "affected_files": response.affected_files,
        "score": response.score.model_dump(),
        "priority": response.priority,
        "story_points": response.story_points,
        "fix_decision": fix_decision,
        "comment_draft": response.comment_draft,
        "assignee": response.assignee,
        "labels_to_add": [f"fix/{fix_decision.replace('_', '-')}"],
    }


def _fallback_analyze(error: str) -> dict:
    """Return a fallback analysis when Claude Code fails."""
    return {
        "analysis_summary": f"Analysis incomplete: {error}",
        "affected_files": [],
        "score": {"total": 0, "scope": 0, "risk": 0, "verifiability": 0, "clarity": 0},
        "fix_decision": "manual_required",
        "comment_draft": f"Automated analysis encountered an issue: {error}\n\nPlease investigate manually.",
        "assignee": None,
        "labels_to_add": ["fix/manual-required"],
    }

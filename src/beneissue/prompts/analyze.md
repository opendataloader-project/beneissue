Perform deep analysis for GitHub issue using the ai-issue skill.

**Title**: {issue_title}

**Body**:
{issue_body}

## Instructions
1. Read skill files in .claude/skills/beneissue/beneissue-config.yml
2. Analyze codebase to identify affected files and root cause
3. Score: Scope(0-30), Risk(0-30), Verifiability(0-25), Clarity(0-15)
4. Action: score >= threshold → "fix/auto-eligible", else → "fix/manual-required", no code → "fix/comment-only"
5. Select labels, priority, story_points, assignee per policies

## Output

Return your analysis as JSON:

```json
{{
  "summary": "2-3 sentences: what the issue is, why it occurs, and how to fix",
  "affected_files": ["path/to/file1.py", "path/to/file2.py"],
  "score": {{
    "total": 85,
    "scope": 25,
    "risk": 25,
    "verifiability": 20,
    "clarity": 15
  }},
  "priority": "P0 | P1 | P2",
  "story_points": 1 | 2 | 3 | 5 | 8,
  "labels": ["bug"],
  "assignee": "github_username from team config, or null if none suitable",
  "comment_draft": "null, or guidance for issue author if fix/comment-only"
}}
```

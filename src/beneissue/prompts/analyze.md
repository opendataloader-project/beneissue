# Analyze Issue

You are analyzing a GitHub issue for implementation planning and auto-fix eligibility.

## Issue to Analyze

**Title**: {issue_title}

**Body**:
{issue_body}

**Repository**: {repo}

## Instructions

Use the beneissue skill to analyze this issue:

1. Explore the codebase using Read, Glob, and Grep tools
2. Identify affected files
3. Score the issue based on scoring criteria
4. Return your analysis as JSON:

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
  "priority": "P2",
  "story_points": 2,
  "labels": ["bug"],
  "comment_draft": null
}}
```

## Comment Draft

- For `fix/auto-eligible` (score >= threshold): set `comment_draft` to `null`
- For `fix/manual-required` or `fix/comment-only`: provide helpful analysis and guidance

IMPORTANT: Your final output MUST be valid JSON matching this structure.

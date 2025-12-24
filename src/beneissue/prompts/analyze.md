Analyze GitHub issue and determine fix approach.

**Title**: {issue_title}

**Body**:
{issue_body}

## Classification Rules

### Step 1: Code change needed?
- No (docs question, usage help, discussion) → **comment_only**
- Yes → Step 2

### Step 2: Auto-fix eligible? (ALL must be true)
- [ ] affected_files ≤ 3
- [ ] Testable (existing tests or clear verification)
- [ ] Uses existing patterns (no new architecture)
- [ ] No security/auth code changes

All true → **auto_eligible**, otherwise → **manual_required**

## Assignee (from .claude/skills/beneissue/beneissue-config.yml)
Read config. Always assign: best specialty match, or first available.

## Output (JSON only)

```json
{{
  "summary": "2-3 sentences: what the issue is, root cause, fix approach",
  "affected_files": ["path/to/file.py"],
  "fix_decision": "auto_eligible | manual_required | comment_only",
  "reason": "1-sentence justification for fix_decision",
  "priority": "P0 | P1 | P2",
  "story_points": 1 | 2 | 3 | 5 | 8,
  "labels": ["bug"],
  "assignee": "github_id (required - always assign someone)",
  "comment_draft": "null, or response if comment_only"
}}
```

# Fix Issue #{issue_number}: {issue_title}

## Analysis

{analysis_summary}

## Affected Files

{affected_files}

## Instructions

Use the beneissue skill to fix this issue:

1. Write tests first (if applicable)
2. Implement the fix with minimal changes
3. Run tests to verify
4. Return your result as JSON:

```json
{{
  "success": true,
  "title": "Add null check in UserService",
  "description": "Added guard clause to prevent NPE when user is null",
  "error": null
}}
```

- `title`: Brief summary (50 chars max, imperative mood)
- `description`: What was changed and why
- `error`: Error message if success is false

Keep changes minimal and focused. Don't refactor unrelated code.
Do NOT create commits or PRs - just make the code changes.

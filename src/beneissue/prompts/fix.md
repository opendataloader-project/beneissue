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
  "description": "## Summary\nBrief description of what was fixed.\n\n## Changes\n- `path/to/file.py`: Added guard clause to prevent NPE\n- `tests/test_file.py`: Added test case for null input\n\n## Testing\nDescribe how the fix was verified.",
  "error": null
}}
```

- `title`: Brief summary (50 chars max, imperative mood)
- `description`: Detailed markdown with Summary, Changes (file-by-file), and Testing sections
- `error`: Error message if success is false

Keep changes minimal and focused. Don't refactor unrelated code.
Do NOT create commits or PRs - just make the code changes.

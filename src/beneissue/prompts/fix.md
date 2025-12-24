# Fix Instructions

You are fixing a GitHub issue. Follow these instructions carefully.

## Context

Issue: {issue_title}
Repository: {repo}

## Analysis Summary

{analysis_summary}

## Affected Files

{affected_files}

## Recommended Approach

{fix_approach}

## Instructions

1. **Understand the issue**: Read the analysis and affected files carefully
2. **Write tests first**: Create failing tests that will pass after the fix (if applicable)
3. **Implement the fix**: Make the minimal changes needed to fix the issue
4. **Run tests**: Verify all tests pass
5. **Create a PR**:
   - Branch name: `fix/issue-{issue_number}`
   - PR title: `Fix #{issue_number}: {brief_description}`
   - PR body: Include the analysis summary and what was changed

## Important

- Keep changes minimal and focused
- Don't refactor unrelated code
- Follow existing code style
- Add comments only where necessary

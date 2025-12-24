---
name: beneissue
description: Process GitHub issues with AI-powered triage, analysis, and auto-fix. Use when processing new issues, categorizing bugs, or attempting automatic fixes.
---

# beneissue

GitHub 이슈를 AI로 자동 처리합니다.

## Commands

- `beneissue triage <repo> --issue <number>`: 이슈 분류 (라벨 적용 안함)
- `beneissue analyze <repo> --issue <number>`: 이슈 분석 및 라벨/코멘트 적용
- `beneissue fix <repo> --issue <number>`: 자동 수정 시도 (eligible한 경우)

## Workflow

1. **Triage**: 이슈가 valid/invalid/duplicate/needs_info 인지 분류
2. **Analyze**: valid 이슈에 대해 영향 범위, 수정 방법, 자동수정 점수 분석
3. **Fix**: 점수가 80점 이상이면 Claude Code로 자동 수정 시도

## Configuration

설정 파일: `.claude/skills/beneissue/beneissue.yml`

## Policy Tests

테스트 케이스: `.claude/skills/beneissue/tests/cases/*.json`

실행: `beneissue test`

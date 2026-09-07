---
name: memory-location
description: 이 프로젝트의 기억은 전역 폴더가 아니라 프로젝트 안 .claude 폴더에 저장한다.
metadata:
  type: feedback
---

기억해야 할 내용은 사용자 홈의 전역 메모리 폴더가 아니라, 이 저장소 안의
`.claude/CLAUDE.md` 와 `.claude/memory/` 에 남깁니다. 2026년 9월 7일에 사용자가
직접 요청했습니다.

**Why:** 프로젝트와 함께 버전 관리되어야 다른 기기나 새 세션에서도 같은 맥락을
그대로 이어받을 수 있기 때문입니다.

**How to apply:** 새로운 사실을 기억할 때 `.claude/memory/<이름>.md` 를 만들고
`.claude/memory/MEMORY.md` 와 `.claude/CLAUDE.md` 의 기억 목록에 한 줄을 더합니다.
검증 도구처럼 실행 가능한 산출물은 [[windows-gui-test-gotchas]] 와 함께
프로젝트의 `test/` 폴더에 둡니다.

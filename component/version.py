"""프로그램 버전입니다. 배포할 때 이 값만 고치면 됩니다.

- 창 오른쪽 아래와 창 제목에 그대로 나옵니다.
- GitHub 에 올릴 때는 같은 값으로 태그를 답니다. 예: ``git tag v1.0.0``
- 바꾼 내용은 저장소의 CHANGELOG.md 에 함께 적습니다.

번호는 major.minor.patch 로 세 자리를 씁니다.

- major: 설정 파일 형식이 바뀌는 등, 쓰던 방식을 고쳐야 할 때
- minor: 기능이 늘거나 화면 구성이 바뀔 때
- patch: 버그 수정과 문구 다듬기
"""

APP_NAME = "ShadowPlay Notifier"
VERSION = "1.0.1"
AUTHOR = "deuxdoom"


def label():
    """화면에 표시할 짧은 버전 문구입니다."""
    return "v" + VERSION


def title():
    """창 제목입니다."""
    return "%s %s" % (APP_NAME, VERSION)

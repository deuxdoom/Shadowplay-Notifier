"""화면에 넣기 좋게 문자열을 다듬습니다."""

import os


def ellipsize(text, limit):
    """긴 문자열의 가운데를 줄입니다."""
    if len(text) <= limit:
        return text
    head = (limit - 1) // 2
    tail = limit - 1 - head
    return text[:head] + "…" + text[-tail:]


def folder_label(path, roots):
    """감시 폴더를 기준으로 저장 폴더 이름(예: OnimushaWotS)을 뽑아냅니다."""
    parent = os.path.dirname(path)
    for root in roots:
        try:
            rel = os.path.relpath(parent, root)
        except ValueError:
            continue
        if rel == os.curdir:
            return os.path.basename(root.rstrip("\\/")) or root
        if not rel.startswith(".."):
            return rel.split(os.sep)[0]
    return os.path.basename(parent) or parent


def relative_path(path, roots):
    """로그에 적을 때 감시 폴더 아래의 상대 경로만 남깁니다."""
    for root in roots:
        try:
            rel = os.path.relpath(path, root)
        except ValueError:
            continue
        if not rel.startswith(".."):
            return rel
    return path

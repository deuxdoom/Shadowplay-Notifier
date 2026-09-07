"""중복 실행 방지가 실제로 동작하는지 확인합니다.

실행: python test\\test_single_instance.py
별도 프로세스에 뮤텍스를 잡게 하고, 그 동안 이 프로세스가 자리를 잡지 못하는지
봅니다. 창을 띄우지 않고 녹화 폴더도 건드리지 않습니다.
"""

import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from component.instance import MUTEX_NAME, claim, release  # noqa: E402

# 검사에만 쓰는 이름입니다. 진짜 앱이 떠 있어도 서로 방해하지 않습니다.
TEST_NAME = MUTEX_NAME + "-test"

CHILD = (
    "import sys, time\n"
    "sys.path.insert(0, %r)\n"
    "from component.instance import claim\n"
    "print('ok' if claim(%r) else 'no', flush=True)\n"
    "time.sleep(30)\n" % (ROOT, TEST_NAME)
)

holder = None
try:
    # 1) 아무도 잡고 있지 않으면 자리를 잡습니다.
    assert claim(TEST_NAME), "빈 자리인데 잡지 못했습니다"
    print("[통과] 처음 실행은 자리를 잡습니다")

    # 2) 이미 잡혀 있으면 막습니다.
    assert not claim(TEST_NAME), "이미 잡혀 있는데 또 잡았습니다"
    print("[통과] 두 번째 실행은 막힙니다")

    # 3) 놓으면 다시 잡을 수 있습니다. 앱이 죽어도 다음 실행이 막히지 않습니다.
    release()
    assert claim(TEST_NAME), "놓았는데도 다시 잡지 못했습니다"
    release()
    print("[통과] 놓으면 다음 실행이 다시 잡습니다")

    # 4) 다른 프로세스가 잡고 있어도 막힙니다. 실제 상황과 같은 조건입니다.
    holder = subprocess.Popen([sys.executable, "-c", CHILD], cwd=ROOT,
                              stdout=subprocess.PIPE, text=True)
    assert holder.stdout.readline().strip() == "ok", "자식이 잡지 못했습니다"
    assert not claim(TEST_NAME), "다른 프로세스가 잡고 있는데 또 잡았습니다"
    print("[통과] 다른 프로세스가 떠 있으면 막힙니다")

    # 5) 그 프로세스가 끝나면 자리가 풀립니다.
    holder.terminate()
    holder.wait(timeout=5)
    holder = None
    for _ in range(20):
        if claim(TEST_NAME):
            break
        time.sleep(0.1)
    else:
        raise AssertionError("프로세스가 끝났는데도 자리가 풀리지 않았습니다")
    release()
    print("[통과] 앞선 프로세스가 끝나면 자리가 풀립니다")

    print("\n모든 검사를 통과했습니다.")
finally:
    release()
    if holder is not None:
        holder.kill()

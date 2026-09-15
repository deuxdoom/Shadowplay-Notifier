"""팝업 창에 쓰는 아이콘입니다. PNG 로 구워서 base64 로 담아 두었습니다.

tkinter 의 PhotoImage 는 PNG 를 그대로 읽으므로 별도 라이브러리가 필요 없습니다.
Fluent UI System Icons 에서 가져왔습니다. ``FOLDER_LIT`` 은 환경설정의 폴더
고르기 단추에, ``APP_16`` 은 팝업 타이틀 줄에 답니다. ``APP_*`` 는
``test/build_icon.py`` 가 ``assets/appicon.svg`` 에서 다시 구워 넣습니다.

본 창의 환경설정·전체화면·닫기 단추는 캔버스에 글리프로 직접 그리므로
(``component/wallpaper.py`` 의 ``control_items``) 여기에 그림을 두지 않습니다.
"""


FOLDER_LIT = (
    "iVBORw0KGgoAAAANSUhEUgAAABoAAAAaCAYAAACpSkzOAAAB40lEQVR42u2Wu2pVURCGvzlnHzDE"
    "NnhLI6KttQZr0cJCCVr5BAr6FmInVj6FjRaC2IiWNiHeCCGiEENAHyA557NwFuyzs825ksqBxWLv"
    "PXvNzP/PZcERSdQf1AC6wKBFz4gYzGwxjYzS6cwUkRoRoboEPARWgF45H1gHHkXEploB/SYadX8A"
    "IsIDXqqhLqsb/pVd9bv6I5fqjnpxAoS6zRdV7s/ywNtqlcaLE9fUPXVbvaSeUE+rp1rWUivUhRv1"
    "s/qlFmU3916+u+r4sqZerxuralhWwO/Et55dg1RezefnwLfUt4WfReAW8FJdiYj3ajdqkX0CFoB7"
    "meICndzvAjeBJxHxYAx+zgEfgVcRcWOIL/XDCDgeF5LVXvLYulJvTf1KDa4iC8AWcL8WUYFjMyLW"
    "k89BRPQPq8fU2weOtRnqAb8i4sW/inXczpA1OVRnVYPIKvGMBtEzt5+q6XhE9EunmGdT7RxV9/5v"
    "aG7JUNoNOnUulDoaytKqlmH7wOIcpqjp6HFgrxRxJ7sAwBvggrpaxsM0Uzr/vQOcB17np24kVAIn"
    "gXfAWWB7xBQ9LJoqz9oArgA7QDRH+ZnsdZdr/MUkkCUFb4GnEfHzQPFPA9UkF55oueV0Wq5b05RN"
    "f95tbCz5AwTWv2zmxwXnAAAAAElFTkSuQmCC"
)


# 창 아이콘입니다. appicon.ico 를 크기별로 PNG 로 구워 넣었습니다. 저장소에는 ico
# 원본을 올리지 않으므로(빌드할 때만 루트에 둡니다) 여기에 함께 담아 둡니다.
# 윈도우는 타이틀바에 작은 아이콘, 작업 전환 화면에 큰 아이콘을 쓰고 그 크기가
# DPI 배율에 따라 달라지므로, 100%/150%/200%/300% 에 맞춰 네 벌을 넣었습니다.
APP_SIZES = (16,)

APP_16 = (
    "iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAADE0lEQVR4nG2TTWxUVRiGn3O+ezsz"
    "nXZmFLQRsAi1EEgTkRULFyWISkxMjNVgQDf+hKiEWBWXLDT+JcbGJdGFsaQ1FqxKWYgbExdCDWno"
    "XwjWQGPUmVbtDNPOzJ17zjHntpCYeDZncfK+Od/7fK8CFOAKnTsOW2v3O0dGlEICUdaBVmCMxTnr"
    "Aq2Iraopzfml+dlBr1WcOKFznwyfNMY8Z61BRGjUGzSrVRDxalQ6TZhKE9WbpDIhYRCgtf608vzB"
    "F1Whc+ehZhQNmmZkJAxYLlfYtLmTJ/oeZ+PGDcRxzOjoGNevTNHbczffXf6N5XpESyotQRge1sbE"
    "jzpr7ZpYevftlYGPP5Ta8ooMDQ7JhZ8uSksmIwPP7pHh1/bL8cfuk6hhUM5ar9U4QqWUjmp1tnRt"
    "5eixl3n91eOc/Oh9tnbdw/jFcX48e45yw7Gy3GChUk8m9/F4bQD4eZKZnzr4JGdOj3Jt9gqS6+DA"
    "w/soLSxS+mOBN4fGGTg7wdXiDTKZEGsdor2LR+AcpFJ0dNzJ5OUpgnwOU2+gtdDa2kpcXeJGpcr2"
    "Pb309OwgqtVQysNbM0hAGpvgSqVSSfItmTRDwyP0HzvCK2/0Y2tVHtz7ALlcDmPMquaWgT/GMDk5"
    "xSMHHiKuLJJua+P89z/wwpF+isUSm7q3kcsXmLg0QSqbxfkluWlgjSVdyHP6ixG67u3imZeOUimW"
    "II6Zn5nh22/O8d4H7zB65muq5TKB34+1o9o3bPvSxHGfUhiPMdue5e133yKXz/PL1Tny+Rzd27sZ"
    "/OwUX31+iqCQJwxbjFJaJAhGEgNrTF8zapidu3fLXZ2bWa5W2XX/LtbfsY64GTM9PUPpzxK3r1/H"
    "/Nwc05d+NkGYEhEZCVA0nXPWo/x7YZG/ikVUEDI7OUXUiJK0s21ZwkD4dXYaLZLQ8eXw2kAkGLPG"
    "Pq2sMr9fv2b8XO2F25LdEGdxFmqVMitAdemfBHkYhiit/Qxj/ylTsg84rMe0GtHa7fBPEvjwVPIr"
    "EVkt0//V2VfYWXdTvWqlVUJOKWpa61t1/heDu24PTICUWgAAAABJRU5ErkJggg=="
)

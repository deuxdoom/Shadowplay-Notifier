"""화면에 나오는 말을 한국어·영어·일본어로 바꿔 줍니다.

찾아보는 열쇠를 한국어 원문 그대로 씁니다. 코드에서 ``tr("저장")`` 처럼
읽히므로 무슨 말이 나오는지 그 자리에서 알 수 있고, 번역이 빠진 말은
한국어가 그대로 나와서 화면이 비지 않습니다.

기본값은 한국어입니다. 환경설정에서 고른 값을 ``config.json`` 의
``language`` 에 적어 두고, 프로그램이 켜질 때 :func:`set_language` 로
정합니다. 날짜와 요일처럼 짜임새가 나라마다 다른 것은 :func:`date_text`
와 :func:`weekday` 가 맡습니다.

기록(``paths.log``)은 한국어로 남깁니다. 그것은 화면이 아니라 문제를 찾을
때 읽는 글이므로 언어 설정을 따르지 않습니다.
"""

# (코드, 환경설정에 나오는 이름) 입니다. 이름은 그 언어를 쓰는 사람이
# 자기 말로 알아볼 수 있게 제 나라 글로 적습니다.
LANGUAGES = (("ko", "한국어"), ("en", "English"), ("ja", "日本語"))
DEFAULT = "ko"

_lang = DEFAULT

EN = {
    # ---------------------------------------------------------- 월페이퍼 화면
    "고요한 순간": "A Quiet Moment",
    "음악을 재생하면 이곳에 표시됩니다": "Play something and it will show up here",
    "날씨 연결 중": "Connecting…",
    "날씨 정보 없음": "No weather data",
    "최고 %d°": "High %d°",
    "최저 %d°": "Low %d°",
    "습도 %d%%": "Humidity %d%%",
    "강수 %d%%": "Rain %d%%",
    "환경설정": "Settings",
    "전체화면 · F11": "Fullscreen · F11",
    "트레이로 이동": "Hide to tray",
    # ---------------------------------------------------------- 녹화 화면
    "감시 %s   ·   주기 %.1f초   ·   갱신 %s   ·   세션 누적 %d회":
        "Watching %s   ·   every %.1fs   ·   updated %s   ·   %d this session",
    "(감시 폴더 없음)": "(no folder to watch)",
    "측정 중": "measuring",
    "%.1f초 전 증가": "%.1fs since it grew",
    "시작": "START",
    "중단": "STOP",
    "완료 파일 생성": "final file written",
    "임시 파일 사라짐": "temp file gone",
    "파일 닫힘": "file closed",
    "증가 멈춤": "growth stopped",
    "폴더에 접근할 수 없습니다: ": "Cannot reach folder: ",
    # ---------------------------------------------------------- 트레이
    "창 열기": "Open window",
    "윈도우 시작 시 실행": "Run at Windows start",
    "최신 버전 확인": "Check for updates",
    "GitHub 프로젝트": "GitHub project",
    "프로그램 종료": "Quit",
    "녹화 중": "Recording",
    "녹화 대기": "Standing by",
    # ---------------------------------------------------------- 팝업 공통
    "확인": "OK",
    "취소": "Cancel",
    "닫기": "Close",
    "저장": "Save",
    "폴더 선택": "Choose folder",
    "상위 폴더": "Parent folder",
    "이동": "Go",
    "폴더를 읽고 있습니다…": "Reading folder…",
    "폴더를 열 수 없습니다. 경로와 접근 권한을 확인해 주세요.":
        "Cannot open that folder. Check the path and your permissions.",
    "두 번 클릭하면 하위 폴더를 엽니다. 주소를 입력해 이동할 수도 있습니다.":
        "Double-click to open a folder, or type a path to go there.",
    # ---------------------------------------------------------- 환경설정 창
    "저장하면 config.json 에 적고 감시를 다시 시작합니다.":
        "Saving writes config.json and restarts watching.",
    "녹화 폴더": "Recording folder",
    "녹화 중에 파일이 커지는 폴더입니다. 하위 폴더까지 함께 봅니다.":
        "The folder whose files grow while you record. Subfolders are watched too.",
    "폴링 주기 (초)": "Poll interval (s)",
    "중단 판정 시간 (초)": "Stop after idle (s)",
    "최소 파일 크기 (MB)": "Minimum file size (MB)",
    "시작 판정 증가량 (KB)": "Growth to call it started (KB)",
    "표시할 모니터 번호 (-1 이면 자동)": "Monitor number (-1 for automatic)",
    "날씨를 볼 도시": "City for weather",
    "화면에 쓰는 말": "Display language",
    "도시는 Seo 까지만 적어도 Seoul 이 후보로 나옵니다. "
    "골라 두면 그 좌표를 함께 저장합니다.":
        "Type just \"Seo\" and Seoul shows up. Picking one saves its "
        "coordinates as well.",
    "항상 위": "Always on top",
    "소리": "Sound",
    "날씨를 볼 도시를 적으십시오.": "Enter a city for the weather.",
    "%s 을(를) 찾지 못했습니다. 후보에서 고르십시오.":
        "Could not find %s. Please pick one from the list.",
    "녹화 폴더를 지정하십시오.": "Choose a recording folder.",
    "숫자 칸에는 숫자만 넣을 수 있습니다.": "Number fields take numbers only.",
    "폴링 주기는 0.2초 이상이어야 합니다.":
        "The poll interval must be at least 0.2 seconds.",
    "중단 판정 시간은 폴링 주기의 두 배 이상이어야 합니다.":
        "The stop time must be at least twice the poll interval.",
    "크기 값은 0보다 커야 합니다.": "The size values must be greater than zero.",
    "폴더가 없습니다. 경로를 확인하십시오: %s":
        "No such folder. Please check the path: %s",
    "설정 파일을 쓰지 못했습니다. 로그를 보십시오.":
        "Could not write the settings file. See the log.",
    # ---------------------------------------------------------- 업데이트 창
    "업데이트": "Update",
    "최신 버전 확인 중": "Checking for updates",
    "현재 버전  ": "Current  ",
    "GitHub에서 최신 정식 릴리스를 확인하고 있습니다.":
        "Checking GitHub for the latest release.",
    "연결 중…": "Connecting…",
    "공식 GitHub 릴리스 · ": "Official GitHub release · ",
    "새 버전을 내려받고 있습니다": "Downloading the new version",
    "다운로드 파일 확인": "Checking the download",
    "기존 프로그램 종료": "Closing the old version",
    "실행 파일 교체": "Replacing the program",
    "새 버전 시작 확인": "Starting the new version",
    "이전 버전 복구": "Restoring the old version",
    "업데이트 완료": "Update finished",
    "업데이트를 완료하지 못했습니다": "The update did not finish",
    "업데이트 취소": "Update cancelled",
    "다운로드 → 확인 → 설치 → 재실행":
        "Download → check → install → restart",
    "확인하지 못했습니다": "Could not check",
    "다시 확인": "Check again",
    "현재  %s    →    최신  %s": "Current  %s    →    Latest  %s",
    "새 버전이 있습니다": "A new version is available",
    "업데이트하면 프로그램이 잠시 종료된 뒤 자동으로 다시 실행됩니다.":
        "The program closes for a moment and starts again on its own.",
    "설정과 로그는 그대로 유지됩니다.": "Your settings and logs are kept.",
    "최신 버전입니다": "You are up to date",
    "설치할 새 정식 버전이 없습니다.": "There is no newer release to install.",
    "현재 %s  ·  GitHub 최신 %s": "Current %s  ·  Latest on GitHub %s",
    "EXE에서 업데이트해 주세요": "Please update from the EXE",
    "소스 실행 중에는 파일을 교체할 수 없습니다. 릴리스에서 EXE를 내려받아 실행해 주세요.":
        "Running from source cannot replace the program file. Download the "
        "EXE from the releases page and run that.",
    "릴리스 열기": "Open releases",
    "업데이트 준비": "Getting ready",
    "진행 창을 준비하고 있습니다.": "Preparing the progress window.",
    "잠시만 기다려 주세요.": "One moment, please.",
    "업데이트 진행 창을 시작하지 못했습니다. 다시 시도해 주세요.":
        "Could not start the update window. Please try again.",
    "업데이트 준비에 시간이 걸리고 있습니다. 잠시 후 다시 확인해 주세요.":
        "Getting ready is taking a while. Please check again in a moment.",
    "업데이트 준비 실패": "Could not get ready",
    "취소 중…": "Cancelling…",
    "새 버전  ": "New version  ",
    "다운로드를 준비하고 있습니다.": "Preparing the download.",
    # ---------------------------------------------------------- 업데이트 오류
    "정식 버전 번호를 읽을 수 없습니다: %s": "Cannot read the version number: %s",
    "공개된 정식 릴리스가 아닙니다.": "That is not a published release.",
    "최신 릴리스에 %s 파일이 아직 준비되지 않았습니다.":
        "The latest release does not have %s yet.",
    "공식 저장소의 다운로드 주소가 아닙니다.":
        "That download address is not from the official repository.",
    "릴리스 파일의 SHA-256 확인 정보가 아직 준비되지 않았습니다.":
        "The release does not carry a SHA-256 to check against yet.",
    "릴리스 파일의 크기 정보가 올바르지 않습니다.":
        "The size given for the release file is not right.",
    "보안 연결이 아닌 다운로드 주소를 거부했습니다.":
        "Refused a download address that is not a secure connection.",
    "GitHub 요청 한도에 도달했거나 접근이 제한되었습니다. 잠시 후 다시 확인해 주세요.":
        "GitHub has rate-limited or blocked the request. Please check again "
        "in a few minutes.",
    "공개된 릴리스 또는 다운로드 파일을 찾지 못했습니다. 잠시 후 다시 확인해 주세요.":
        "Could not find a published release or its file. Please check again "
        "in a few minutes.",
    "GitHub에 연결하지 못했습니다 (HTTP %d). 다시 시도해 주세요.":
        "Could not reach GitHub (HTTP %d). Please try again.",
    "연결이 끊겼거나 응답이 없습니다. 인터넷 연결을 확인하고 다시 시도해 주세요.":
        "The connection dropped or never answered. Check your internet and "
        "try again.",
    "설치 폴더에 쓰거나 파일을 교체할 수 없습니다. 폴더 권한과 실행 파일 차단 여부를 확인해 주세요.":
        "Cannot write to the install folder or replace the file. Check the "
        "folder permissions and whether the program is being blocked.",
    "GitHub 응답이 너무 큽니다.": "The answer from GitHub is too large.",
    "다운로드 파일의 크기 또는 SHA-256이 일치하지 않습니다. 다시 시도해 주세요.":
        "The size or SHA-256 of the download does not match. Please try again.",
    "올바른 Windows 실행 파일이 아닙니다.": "That is not a valid Windows program.",
    "실행 파일의 헤더가 손상되었습니다.": "The program header is damaged.",
    "콘솔 없는 Windows 앱 파일이 아닙니다.":
        "That is not a windowed Windows program.",
    "서버의 파일 크기가 릴리스 정보와 다릅니다.":
        "The size on the server differs from what the release says.",
    "업데이트 작업 폴더가 올바르지 않습니다.":
        "The update working folder is not valid.",
    "재실행 인자가 올바르지 않습니다.": "The restart arguments are not valid.",
    "다운로드 크기가 릴리스 정보보다 큽니다.":
        "The download is larger than the release says.",
    "업데이트 도우미는 별도 위치에서 실행해야 합니다.":
        "The update helper has to run from a separate location.",
    "업데이트와 복구 파일을 저장할 디스크 공간이 부족합니다.":
        "There is not enough disk space for the update and its backup.",
    "업데이트 준비 중 기존 실행 파일이 변경되었습니다.":
        "The program on disk changed while the update was getting ready.",
    "기존 실행 파일이 변경되어 업데이트를 중단했습니다.":
        "The program on disk changed, so the update was stopped.",
    "자동 업데이트는 배포된 EXE에서 사용할 수 있습니다.":
        "Automatic updates work only from the released EXE.",
    "%s\n이전 프로그램을 다시 실행했습니다.":
        "%s\nThe previous program has been started again.",
    "%s\n복구 후 실행을 확인하지 못했습니다: %s\n기존 파일: %s":
        "%s\nCould not confirm it started after recovery: %s\nPrevious file: %s",
    # ---------------------------------------------------------- 날씨
    "맑음": "Clear",
    "대체로 맑음": "Mostly clear",
    "구름 조금": "Partly cloudy",
    "흐림": "Overcast",
    "안개": "Fog",
    "서리 안개": "Rime fog",
    "약한 이슬비": "Light drizzle",
    "이슬비": "Drizzle",
    "짙은 이슬비": "Heavy drizzle",
    "어는 이슬비": "Freezing drizzle",
    "짙게 어는 이슬비": "Heavy freezing drizzle",
    "약한 비": "Light rain",
    "비": "Rain",
    "강한 비": "Heavy rain",
    "어는 비": "Freezing rain",
    "강하게 어는 비": "Heavy freezing rain",
    "약한 눈": "Light snow",
    "눈": "Snow",
    "강한 눈": "Heavy snow",
    "싸락눈": "Snow grains",
    "약한 소나기": "Light showers",
    "소나기": "Showers",
    "강한 소나기": "Heavy showers",
    "소낙눈": "Snow showers",
    "강한 소낙눈": "Heavy snow showers",
    "뇌우": "Thunderstorm",
    "우박 동반 뇌우": "Thunderstorm with hail",
    "강한 우박 뇌우": "Severe hailstorm",
}

JA = {
    # ---------------------------------------------------------- 월페이퍼 화면
    "고요한 순간": "静かなひととき",
    "음악을 재생하면 이곳에 표시됩니다": "音楽を再生するとここに表示されます",
    "날씨 연결 중": "天気を取得中",
    "날씨 정보 없음": "天気情報がありません",
    "최고 %d°": "最高 %d°",
    "최저 %d°": "最低 %d°",
    "습도 %d%%": "湿度 %d%%",
    "강수 %d%%": "降水 %d%%",
    "환경설정": "設定",
    "전체화면 · F11": "全画面 · F11",
    "트레이로 이동": "トレイにしまう",
    # ---------------------------------------------------------- 녹화 화면
    "감시 %s   ·   주기 %.1f초   ·   갱신 %s   ·   세션 누적 %d회":
        "監視 %s   ·   周期 %.1f秒   ·   更新 %s   ·   このセッション %d 回",
    "(감시 폴더 없음)": "(監視フォルダーなし)",
    "측정 중": "測定中",
    "%.1f초 전 증가": "%.1f 秒前に増加",
    "시작": "開始",
    "중단": "停止",
    "완료 파일 생성": "完成ファイル作成",
    "임시 파일 사라짐": "一時ファイル消失",
    "파일 닫힘": "ファイルが閉じられた",
    "증가 멈춤": "増加が止まった",
    "폴더에 접근할 수 없습니다: ": "フォルダーにアクセスできません: ",
    # ---------------------------------------------------------- 트레이
    "창 열기": "ウィンドウを開く",
    "윈도우 시작 시 실행": "Windows 起動時に実行",
    "최신 버전 확인": "最新バージョンを確認",
    "GitHub 프로젝트": "GitHub プロジェクト",
    "프로그램 종료": "終了",
    "녹화 중": "録画中",
    "녹화 대기": "待機中",
    # ---------------------------------------------------------- 팝업 공통
    "확인": "OK",
    "취소": "キャンセル",
    "닫기": "閉じる",
    "저장": "保存",
    "폴더 선택": "フォルダーを選ぶ",
    "상위 폴더": "上のフォルダー",
    "이동": "移動",
    "폴더를 읽고 있습니다…": "フォルダーを読み込んでいます…",
    "폴더를 열 수 없습니다. 경로와 접근 권한을 확인해 주세요.":
        "フォルダーを開けません。パスとアクセス権を確認してください。",
    "두 번 클릭하면 하위 폴더를 엽니다. 주소를 입력해 이동할 수도 있습니다.":
        "ダブルクリックでフォルダーを開きます。パスを入力して移動もできます。",
    # ---------------------------------------------------------- 환경설정 창
    "저장하면 config.json 에 적고 감시를 다시 시작합니다.":
        "保存すると config.json に書き込み、監視をやり直します。",
    "녹화 폴더": "録画フォルダー",
    "녹화 중에 파일이 커지는 폴더입니다. 하위 폴더까지 함께 봅니다.":
        "録画中にファイルが大きくなるフォルダーです。下のフォルダーもまとめて見ます。",
    "폴링 주기 (초)": "確認の間隔 (秒)",
    "중단 판정 시간 (초)": "停止と見なす時間 (秒)",
    "최소 파일 크기 (MB)": "最小ファイルサイズ (MB)",
    "시작 판정 증가량 (KB)": "開始と見なす増加量 (KB)",
    "표시할 모니터 번호 (-1 이면 자동)": "表示するモニター番号 (-1 で自動)",
    "날씨를 볼 도시": "天気を見る都市",
    "화면에 쓰는 말": "表示する言語",
    "도시는 Seo 까지만 적어도 Seoul 이 후보로 나옵니다. "
    "골라 두면 그 좌표를 함께 저장합니다.":
        "Seo まで入力すると Seoul が候補に出ます。選ぶとその座標も一緒に保存します。",
    "항상 위": "常に手前",
    "소리": "音",
    "날씨를 볼 도시를 적으십시오.": "天気を見る都市を入力してください。",
    "%s 을(를) 찾지 못했습니다. 후보에서 고르십시오.":
        "%s が見つかりません。候補から選んでください。",
    "녹화 폴더를 지정하십시오.": "録画フォルダーを指定してください。",
    "숫자 칸에는 숫자만 넣을 수 있습니다.": "数字の欄には数字だけ入力できます。",
    "폴링 주기는 0.2초 이상이어야 합니다.":
        "確認の間隔は 0.2 秒以上にしてください。",
    "중단 판정 시간은 폴링 주기의 두 배 이상이어야 합니다.":
        "停止と見なす時間は、確認の間隔の 2 倍以上にしてください。",
    "크기 값은 0보다 커야 합니다.": "サイズの値は 0 より大きくしてください。",
    "폴더가 없습니다. 경로를 확인하십시오: %s":
        "フォルダーがありません。パスを確認してください: %s",
    "설정 파일을 쓰지 못했습니다. 로그를 보십시오.":
        "設定ファイルを書けませんでした。ログを見てください。",
    # ---------------------------------------------------------- 업데이트 창
    "업데이트": "アップデート",
    "최신 버전 확인 중": "最新バージョンを確認中",
    "현재 버전  ": "現在のバージョン  ",
    "GitHub에서 최신 정식 릴리스를 확인하고 있습니다.":
        "GitHub で最新の正式リリースを確認しています。",
    "연결 중…": "接続中…",
    "공식 GitHub 릴리스 · ": "公式 GitHub リリース · ",
    "새 버전을 내려받고 있습니다": "新しいバージョンをダウンロードしています",
    "다운로드 파일 확인": "ダウンロードの確認",
    "기존 프로그램 종료": "今のプログラムを終了",
    "실행 파일 교체": "実行ファイルの入れ替え",
    "새 버전 시작 확인": "新しいバージョンの起動確認",
    "이전 버전 복구": "前のバージョンに戻す",
    "업데이트 완료": "アップデート完了",
    "업데이트를 완료하지 못했습니다": "アップデートを終えられませんでした",
    "업데이트 취소": "アップデートを取り消しました",
    "다운로드 → 확인 → 설치 → 재실행":
        "ダウンロード → 確認 → インストール → 再起動",
    "확인하지 못했습니다": "確認できませんでした",
    "다시 확인": "もう一度確認",
    "현재  %s    →    최신  %s": "現在  %s    →    最新  %s",
    "새 버전이 있습니다": "新しいバージョンがあります",
    "업데이트하면 프로그램이 잠시 종료된 뒤 자동으로 다시 실행됩니다.":
        "アップデートすると、いったん終了してから自動で立ち上がります。",
    "설정과 로그는 그대로 유지됩니다.": "設定とログはそのまま残ります。",
    "최신 버전입니다": "最新のバージョンです",
    "설치할 새 정식 버전이 없습니다.": "新しく入れる正式バージョンはありません。",
    "현재 %s  ·  GitHub 최신 %s": "現在 %s  ·  GitHub の最新 %s",
    "EXE에서 업데이트해 주세요": "EXE からアップデートしてください",
    "소스 실행 중에는 파일을 교체할 수 없습니다. 릴리스에서 EXE를 내려받아 실행해 주세요.":
        "ソースから動かしているときはファイルを入れ替えられません。"
        "リリースから EXE をダウンロードして実行してください。",
    "릴리스 열기": "リリースを開く",
    "업데이트 준비": "アップデートの準備",
    "진행 창을 준비하고 있습니다.": "進行状況の窓を用意しています。",
    "잠시만 기다려 주세요.": "少しお待ちください。",
    "업데이트 진행 창을 시작하지 못했습니다. 다시 시도해 주세요.":
        "進行状況の窓を開けませんでした。もう一度お試しください。",
    "업데이트 준비에 시간이 걸리고 있습니다. 잠시 후 다시 확인해 주세요.":
        "準備に時間がかかっています。しばらくしてからもう一度確認してください。",
    "업데이트 준비 실패": "準備に失敗しました",
    "취소 중…": "取り消しています…",
    "새 버전  ": "新しいバージョン  ",
    "다운로드를 준비하고 있습니다.": "ダウンロードの準備をしています。",
    # ---------------------------------------------------------- 업데이트 오류
    "정식 버전 번호를 읽을 수 없습니다: %s": "バージョン番号を読み取れません: %s",
    "공개된 정식 릴리스가 아닙니다.": "公開された正式リリースではありません。",
    "최신 릴리스에 %s 파일이 아직 준비되지 않았습니다.":
        "最新のリリースにまだ %s がありません。",
    "공식 저장소의 다운로드 주소가 아닙니다.":
        "公式リポジトリのダウンロード先ではありません。",
    "릴리스 파일의 SHA-256 확인 정보가 아직 준비되지 않았습니다.":
        "リリースに照合用の SHA-256 がまだありません。",
    "릴리스 파일의 크기 정보가 올바르지 않습니다.":
        "リリースに書かれたファイルサイズが正しくありません。",
    "보안 연결이 아닌 다운로드 주소를 거부했습니다.":
        "安全な接続でないダウンロード先を拒みました。",
    "GitHub 요청 한도에 도달했거나 접근이 제한되었습니다. 잠시 후 다시 확인해 주세요.":
        "GitHub の要求上限に達したか、接続が制限されています。"
        "しばらくしてからもう一度確認してください。",
    "공개된 릴리스 또는 다운로드 파일을 찾지 못했습니다. 잠시 후 다시 확인해 주세요.":
        "公開されたリリースやファイルが見つかりません。"
        "しばらくしてからもう一度確認してください。",
    "GitHub에 연결하지 못했습니다 (HTTP %d). 다시 시도해 주세요.":
        "GitHub につながりませんでした (HTTP %d)。もう一度お試しください。",
    "연결이 끊겼거나 응답이 없습니다. 인터넷 연결을 확인하고 다시 시도해 주세요.":
        "接続が切れたか応答がありません。インターネット接続を確かめてください。",
    "설치 폴더에 쓰거나 파일을 교체할 수 없습니다. 폴더 권한과 실행 파일 차단 여부를 확인해 주세요.":
        "インストール先に書き込めないか、ファイルを入れ替えられません。"
        "フォルダーの権限と、実行ファイルが止められていないかを確かめてください。",
    "GitHub 응답이 너무 큽니다.": "GitHub からの応答が大きすぎます。",
    "다운로드 파일의 크기 또는 SHA-256이 일치하지 않습니다. 다시 시도해 주세요.":
        "ダウンロードしたファイルのサイズか SHA-256 が合いません。"
        "もう一度お試しください。",
    "올바른 Windows 실행 파일이 아닙니다.": "正しい Windows 実行ファイルではありません。",
    "실행 파일의 헤더가 손상되었습니다.": "実行ファイルのヘッダーが壊れています。",
    "콘솔 없는 Windows 앱 파일이 아닙니다.":
        "コンソールなしの Windows アプリではありません。",
    "서버의 파일 크기가 릴리스 정보와 다릅니다.":
        "サーバー上のファイルサイズがリリースの情報と違います。",
    "업데이트 작업 폴더가 올바르지 않습니다.":
        "アップデート用の作業フォルダーが正しくありません。",
    "재실행 인자가 올바르지 않습니다.": "再起動の引数が正しくありません。",
    "다운로드 크기가 릴리스 정보보다 큽니다.":
        "ダウンロードした大きさがリリースの情報より大きいです。",
    "업데이트 도우미는 별도 위치에서 실행해야 합니다.":
        "アップデート補助プログラムは別の場所で実行する必要があります。",
    "업데이트와 복구 파일을 저장할 디스크 공간이 부족합니다.":
        "アップデートと復元用ファイルを置くディスクの空きが足りません。",
    "업데이트 준비 중 기존 실행 파일이 변경되었습니다.":
        "アップデートの準備中に既存の実行ファイルが変わりました。",
    "기존 실행 파일이 변경되어 업데이트를 중단했습니다.":
        "既存の実行ファイルが変わったため、アップデートを中止しました。",
    "자동 업데이트는 배포된 EXE에서 사용할 수 있습니다.":
        "自動アップデートは配布された EXE でのみ使えます。",
    "%s\n이전 프로그램을 다시 실행했습니다.":
        "%s\n以前のプログラムを実行し直しました。",
    "%s\n복구 후 실행을 확인하지 못했습니다: %s\n기존 파일: %s":
        "%s\n復元後の起動を確認できませんでした: %s\n以前のファイル: %s",
    # ---------------------------------------------------------- 날씨
    "맑음": "晴れ",
    "대체로 맑음": "おおむね晴れ",
    "구름 조금": "薄曇り",
    "흐림": "曇り",
    "안개": "霧",
    "서리 안개": "霧氷",
    "약한 이슬비": "弱い霧雨",
    "이슬비": "霧雨",
    "짙은 이슬비": "強い霧雨",
    "어는 이슬비": "着氷性の霧雨",
    "짙게 어는 이슬비": "強い着氷性の霧雨",
    "약한 비": "弱い雨",
    "비": "雨",
    "강한 비": "強い雨",
    "어는 비": "着氷性の雨",
    "강하게 어는 비": "強い着氷性の雨",
    "약한 눈": "弱い雪",
    "눈": "雪",
    "강한 눈": "強い雪",
    "싸락눈": "霰",
    "약한 소나기": "弱いにわか雨",
    "소나기": "にわか雨",
    "강한 소나기": "強いにわか雨",
    "소낙눈": "にわか雪",
    "강한 소낙눈": "強いにわか雪",
    "뇌우": "雷雨",
    "우박 동반 뇌우": "雹を伴う雷雨",
    "강한 우박 뇌우": "激しい雹の雷雨",
}

TABLES = {"en": EN, "ja": JA}

# 요일입니다. 월요일부터 시작하는 ``time.struct_time.tm_wday`` 차례입니다.
WEEKDAYS = {
    "ko": ("월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"),
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
           "Saturday", "Sunday"),
    "ja": ("月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"),
}

MONTHS_EN = ("January", "February", "March", "April", "May", "June", "July",
             "August", "September", "October", "November", "December")


def set_language(code):
    """쓸 말을 정합니다. 모르는 값이면 한국어로 둡니다."""
    global _lang
    code = str(code or "").strip().lower()
    _lang = code if code in dict(LANGUAGES) else DEFAULT
    return _lang


def language():
    """지금 쓰고 있는 말의 코드입니다."""
    return _lang


def name_of(code):
    """환경설정에 내놓을 이름입니다."""
    return dict(LANGUAGES).get(code, dict(LANGUAGES)[DEFAULT])


def code_of(name):
    """환경설정에서 고른 이름을 코드로 되돌립니다."""
    for code, label in LANGUAGES:
        if label == name:
            return code
    return DEFAULT


def tr(text):
    """한국어 원문을 지금 쓰는 말로 바꿉니다.

    옮겨 둔 것이 없으면 원문을 그대로 돌려줍니다. 그래야 번역이 빠져도
    화면이 비지 않습니다.
    """
    if _lang == DEFAULT:
        return text
    return TABLES.get(_lang, {}).get(text, text)


def weekday_leads():
    """요일을 날짜 앞에 적는 말인지 알려 줍니다.

    영어는 ``Monday, July 13, 2026`` 처럼 요일이 앞에 옵니다. 한국어와
    일본어는 뒤에 붙습니다.
    """
    return _lang == "en"


def weekday(index):
    """요일 이름입니다. 월요일이 0 입니다."""
    return WEEKDAYS.get(_lang, WEEKDAYS[DEFAULT])[index % 7]


def date_text(tm):
    """월페이퍼 날짜 줄에서 요일을 뺀 부분입니다.

    요일은 토·일요일에 색을 달리 칠하므로 :func:`weekday` 로 따로 그립니다.
    """
    if _lang == "en":
        return "%s %d, %d" % (MONTHS_EN[tm.tm_mon - 1], tm.tm_mday, tm.tm_year)
    # 한국어와 일본어는 요일이 뒤에 붙습니다.
    if _lang == "ja":
        return "%d年 %d月 %d日" % (tm.tm_year, tm.tm_mon, tm.tm_mday)
    return "%d년 %d월 %d일" % (tm.tm_year, tm.tm_mon, tm.tm_mday)

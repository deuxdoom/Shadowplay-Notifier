# README 에 넣는 두 장(main.png, wallpaper.png)을 다시 찍습니다.
# 버전을 올릴 때마다 돌려서 화면을 최신으로 맞춥니다.
#
#   powershell -ExecutionPolicy Bypass -File test\capture_screenshots.ps1
#
# 녹화 감시 화면은 가짜 파일로 흉내 냅니다. 실제 녹화 폴더는 건드리지 않으며,
# 감시 경로에 사용자 이름이 드러나지 않도록 드라이브 바로 아래 임시 폴더를 씁니다.
param(
    [string]$FakeRoot = "F:\shadowplay record",
    [switch]$SkipWallpaper,
    [switch]$SkipRecording
)

$dpi = Add-Type -PassThru -Name DpiShot -Namespace SpnShot -MemberDefinition @'
[DllImport("shcore.dll")] public static extern int SetProcessDpiAwareness(int value);
'@
[void]$dpi::SetProcessDpiAwareness(2)
Add-Type -AssemblyName System.Windows.Forms, System.Drawing

# 창 좌표는 창에서 직접 읽습니다. monitor.log 에는 녹화와 오류만 남기 때문입니다.
Add-Type -Name WinFind -Namespace SpnShot -MemberDefinition @'
[StructLayout(LayoutKind.Sequential)]
public struct RECT { public int Left, Top, Right, Bottom; }
[DllImport("user32.dll", CharSet = CharSet.Unicode)]
public static extern IntPtr FindWindowW(string lpClassName, string lpWindowName);
[DllImport("user32.dll")]
public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
'@

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

# 창 제목은 component/version.py 한 곳에서 정합니다.
$verLine = Select-String -Path (Join-Path $root "component\version.py") `
    -Pattern '^VERSION\s*=\s*"([^"]+)"' | Select-Object -First 1
$version = $verLine.Matches[0].Groups[1].Value
$title = "ShadowPlay Notifier $version"

function Stop-App {
    Get-Process -Name ShadowPlayNotifier -ErrorAction SilentlyContinue | Stop-Process -Force
    @(Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" |
        Where-Object { $_.CommandLine -like '*ShadowPlayNotifier*' }) |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Milliseconds 600
}

function Get-WindowSpot {
    # 창을 이름으로 찾아보고, 못 찾으면 앱과 같은 셈법으로 자리를 구합니다.
    for ($i = 0; $i -lt 8; $i++) {
        $h = [SpnShot.WinFind]::FindWindowW($null, $title)
        if ($h -ne [IntPtr]::Zero) {
            $r = New-Object SpnShot.WinFind+RECT
            if ([SpnShot.WinFind]::GetWindowRect($h, [ref]$r)) {
                $w = $r.Right - $r.Left
                if ($w -gt 100) { return @($r.Left, $r.Top, $w, ($r.Bottom - $r.Top)) }
            }
        }
        Start-Sleep -Milliseconds 400
    }
    $code = "import sys;sys.path.insert(0,'.');" +
            "from component.display import enable_dpi_awareness, window_position;" +
            "enable_dpi_awareness();" +
            "spot=window_position(-1) or (0,0);print(spot[0],spot[1])"
    $out = (& python -c $code) -split '\s+'
    if ($out.Count -ge 2) {
        Write-Host ("창 이름으로 못 찾아 자리를 계산했습니다: {0},{1}" -f $out[0], $out[1])
        return @([int]$out[0], [int]$out[1], 960, 640)
    }
    Write-Host "자리를 구하지 못해 화면 왼쪽 위를 찍습니다."
    return @(0, 0, 960, 640)
}

function Save-Shot($spot, $name) {
    $bmp = New-Object System.Drawing.Bitmap $spot[2], $spot[3]
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($spot[0], $spot[1], 0, 0, $bmp.Size)
    $g.Dispose()
    $out = Join-Path $root $name
    $bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Host ("저장: {0}  ({1},{2}) {3}x{4}" -f $name, $spot[0], $spot[1], $spot[2], $spot[3])
}

Stop-App

if (-not $SkipWallpaper) {
    Write-Host "월페이퍼 화면을 찍습니다. 음악을 재생해 두면 곡 정보까지 담깁니다."
    $proc = Start-Process pythonw -WindowStyle Hidden -PassThru `
        -ArgumentList @("ShadowPlayNotifier.py")
    Start-Sleep -Seconds 12
    Save-Shot (Get-WindowSpot) "wallpaper.png"
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 800
}

if (-not $SkipRecording) {
    Write-Host "녹화 감시 화면을 찍습니다."
    $folder = Join-Path $FakeRoot "FFRS"
    if (Test-Path $FakeRoot) { Remove-Item $FakeRoot -Recurse -Force }
    New-Item -ItemType Directory $folder -Force | Out-Null

    $proc = Start-Process pythonw -WindowStyle Hidden -PassThru `
        -ArgumentList @("ShadowPlayNotifier.py", "--dir", "`"$FakeRoot`"", "--interval", "0.4")
    Start-Sleep -Seconds 9
    $spot = Get-WindowSpot

    $path = Join-Path $folder ("FFRS " + (Get-Date -Format "yyyy.MM.dd - HH.mm.ss") + ".mp4")
    $fs = [System.IO.File]::Open($path, "Create", "Write", "Read")
    $chunk = New-Object byte[] (1MB)
    for ($i = 0; $i -lt 40; $i++) { $fs.Write($chunk, 0, $chunk.Length) }
    $fs.Flush()
    Start-Sleep -Milliseconds 1200
    for ($i = 0; $i -lt 26; $i++) {
        $fs.Write($chunk, 0, $chunk.Length); $fs.Flush()
        Start-Sleep -Milliseconds 260
    }
    Save-Shot $spot "main.png"
    $fs.Close()

    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 900
    Remove-Item $FakeRoot -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host ("임시 폴더 정리: " + (-not (Test-Path $FakeRoot)))
}

Write-Host ("남은 프로세스: " + (@(Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" |
    Where-Object { $_.CommandLine -like '*ShadowPlayNotifier*' }).Count))

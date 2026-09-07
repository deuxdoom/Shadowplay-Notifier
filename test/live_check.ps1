# 실제 앱을 보조 디스플레이에 띄운 뒤, 임시 폴더에서 가짜 녹화 파일을 키워
# 녹화 시작과 중단 전환에 걸리는 시간을 측정합니다.
#   powershell -ExecutionPolicy Bypass -File test\live_check.ps1
# 실제 녹화 폴더는 건드리지 않고 임시 폴더만 사용합니다.
param(
    [int]$Monitor = 1,
    [double]$Interval = 0.5,
    [double]$Stall = 4.0
)

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
Add-Type -AssemblyName System.Drawing

$rect = (& python (Join-Path $here "where.py") $Monitor) -split '\s+'
$x, $y, $w, $h = [int]$rect[0], [int]$rect[1], [int]$rect[2], [int]$rect[3]
Write-Host "창 위치: $x,$y ($w x $h)"

function Save-Shot([string]$name) {
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($x, $y, 0, 0, $bmp.Size)
    $g.Dispose()
    $path = Join-Path $here "live_$name.png"
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Host "캡처: $path"
}

$temp = Join-Path $env:TEMP ("spn_live_" + [guid]::NewGuid().ToString("N").Substring(0, 6))
$game = Join-Path $temp "OnimushaWotS"
New-Item -ItemType Directory -Path $game -Force | Out-Null
$file = Join-Path $game "Onimusha 2026.09.07 - 12.00.00.04.DVR.tmp"

$arguments = @(
    ('"{0}"' -f (Join-Path $root "shadowplay_notifier.py")),
    "--dir", ('"{0}"' -f $temp),
    "--interval", $Interval, "--stall", $Stall,
    "--monitor", $Monitor, "--borderless", "--no-beep"
)
$proc = Start-Process pythonw -PassThru -ArgumentList $arguments
Start-Sleep -Seconds 3
Save-Shot "1_idle"

# 2MB 씩 키워서 실제 녹화와 비슷하게 파일을 늘립니다.
$chunk = New-Object byte[] (2 * 1024 * 1024)
$stream = [System.IO.File]::Create($file)
$began = Get-Date
for ($i = 0; $i -lt 12; $i++) {
    $stream.Write($chunk, 0, $chunk.Length)
    $stream.Flush($true)
    Start-Sleep -Milliseconds 600
    if ($i -eq 4) { Save-Shot "2_recording" }
}
$stream.Close()
Write-Host ("파일 증가 시작 시각: {0:HH:mm:ss.fff}" -f $began)
Write-Host ("파일 증가 종료 시각: {0:HH:mm:ss.fff}" -f (Get-Date))

Start-Sleep -Seconds ($Stall + 3)
Save-Shot "3_back_to_idle"

Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "`n--- monitor.log 마지막 12줄 ---"
Get-Content (Join-Path $root "monitor.log") -Tail 12

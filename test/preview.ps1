# 보조 디스플레이에 미리보기 창을 띄우고 그 화면을 그대로 캡처합니다.
#   powershell -ExecutionPolicy Bypass -File test\preview.ps1 -Mode rec -Monitor 1
param(
    [string]$Mode = "rec",
    [int]$Monitor = 1,
    [int]$Seconds = 12,
    [switch]$Borderless
)

$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# 캡처하는 쪽도 DPI 인식을 켜야 보조 디스플레이 좌표가 물리 좌표로 잡힙니다.
$dpi = Add-Type -PassThru -Name Dpi -Namespace Shot -MemberDefinition @'
[DllImport("shcore.dll")] public static extern int SetProcessDpiAwareness(int value);
'@
[void]$dpi::SetProcessDpiAwareness(2)
Add-Type -AssemblyName System.Windows.Forms, System.Drawing

# 경로에 공백이 있으므로 반드시 따옴표로 묶어서 넘겨야 합니다.
$script = '"{0}"' -f (Join-Path $here "preview_gui.py")
$extra = if ($Borderless) { "nb" } else { "bar" }
$proc = Start-Process pythonw -PassThru -ArgumentList $script, $Mode, $Monitor, $Seconds, $extra
Start-Sleep -Seconds 4

# 화면 캡처는 물리 좌표로 동작하므로 파이썬 쪽이 남긴 좌표를 그대로 씁니다.
$rectFile = Join-Path $here "monitor_rect.txt"
if (Test-Path $rectFile) {
    $n = (Get-Content $rectFile -Raw).Trim() -split '\s+'
    $bounds = New-Object System.Drawing.Rectangle ([int]$n[0]), ([int]$n[1]),
        ([int]$n[2]), ([int]$n[3])
} else {
    $screens = @([System.Windows.Forms.Screen]::AllScreens |
        Sort-Object { $_.Bounds.X }, { $_.Bounds.Y })
    if ($Monitor -ge $screens.Count) { $Monitor = 0 }
    $bounds = $screens[$Monitor].Bounds
    Write-Host "창 좌표 파일이 없어 화면 목록의 좌표를 씁니다."
}
Write-Host ("캡처 영역: {0}" -f $bounds)

$bitmap = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.X, $bounds.Y, 0, 0, $bitmap.Size)
$graphics.Dispose()

# 캡처하는 쪽이 주 모니터 배율로 좌표를 보면 화면이 확대되어 잡히므로
# 실제 창 크기(960x640)로 되돌립니다.
if ($bounds.Width -ne 960 -or $bounds.Height -ne 640) {
    $scaled = New-Object System.Drawing.Bitmap 960, 640
    $g2 = [System.Drawing.Graphics]::FromImage($scaled)
    $g2.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g2.DrawImage($bitmap, 0, 0, 960, 640)
    $g2.Dispose()
    $bitmap.Dispose()
    $bitmap = $scaled
    Write-Host "캡처를 960x640 으로 되돌렸습니다."
}
$out = Join-Path $here "shot_$Mode.png"
$bitmap.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
$bitmap.Dispose()
Write-Host "저장: $out"

$proc.WaitForExit()
Get-Content (Join-Path $here "layout_$Mode.txt")

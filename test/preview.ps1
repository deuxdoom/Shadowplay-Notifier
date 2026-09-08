# 보조 디스플레이에 미리보기 창을 띄우고 그 화면을 그대로 캡처합니다.
#   powershell -ExecutionPolicy Bypass -File test\preview.ps1 -Mode rec -Monitor 1
param(
    [string]$Mode = "rec",
    [int]$Monitor = 1,
    [int]$Seconds = 12,
    [switch]$Borderless,
    [switch]$Fullscreen
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
$previewArgs = @($script, $Mode, $Monitor, $Seconds, $extra)
if ($Fullscreen) { $previewArgs += "full" }
$proc = Start-Process pythonw -WindowStyle Hidden -PassThru -ArgumentList $previewArgs
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

# DPI 인식이 켜진 실제 창 크기를 그대로 보존합니다. 전체화면 이미지를
# 960x640 으로 강제 변환하면 화면비가 달라져 비례 배치 검증을 할 수 없습니다.
$out = Join-Path $here "shot_$Mode.png"
$bitmap.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
$bitmap.Dispose()
Write-Host "저장: $out"

$proc.WaitForExit()
Get-Content (Join-Path $here "layout_$Mode.txt")

# 오프라인 미리보기를 보조 화면에서 캡처합니다. 본 앱을 먼저 닫으십시오.
param(
    [int]$Scene = 0,
    [string]$Season = 'autumn',
    [string]$Size = '960x640',
    [double]$After = 4,
    [switch]$Empty,
    [switch]$Controls
)
$ErrorActionPreference = 'Stop'
$wallRoot = Split-Path -Parent $PSScriptRoot
$wallDpi = Add-Type -PassThru -Name Dpi -Namespace WallpaperShot -MemberDefinition @'
[DllImport("shcore.dll")] public static extern int SetProcessDpiAwareness(int value);
'@
[void]$wallDpi::SetProcessDpiAwareness(2)
Add-Type -AssemblyName System.Drawing
$wallSize = $Size.Split('x')
$wallWidth, $wallHeight = [int]$wallSize[0], [int]$wallSize[1]
if ($wallWidth -gt 960 -or $wallHeight -gt 640) {
    $wallX, $wallY = 100,100
} else {
    $wallRect = (python (Join-Path $PSScriptRoot 'where.py') 1).Trim().Split(' ')
    $wallX, $wallY = [int]$wallRect[0], [int]$wallRect[1]
}
$wallArguments = '"{0}" --scene {1} --size {2} --seconds {3}' -f (
    (Join-Path $PSScriptRoot 'wallpaper_preview.py'), $Scene, $Size, ($After + 3))
if ($Empty) { $wallArguments += ' --empty' }
$wallArguments += ' --season ' + $Season
if ($Controls) { $wallArguments += ' --controls' }
$wallProcess = Start-Process pythonw -ArgumentList $wallArguments -WorkingDirectory $wallRoot -WindowStyle Hidden -PassThru
try {
    Start-Sleep -Milliseconds ([int]($After * 1000))
    $wallBitmap = New-Object System.Drawing.Bitmap $wallWidth,$wallHeight
    $wallGraphics = [System.Drawing.Graphics]::FromImage($wallBitmap)
    try {
        $wallGraphics.CopyFromScreen($wallX,$wallY,0,0,$wallBitmap.Size)
        $suffix = if ($Empty) { '_empty' } elseif ($Controls) { '_controls' } else { '' }
        $wallOutput = Join-Path $PSScriptRoot ('shot_wallpaper_{0}_{1}_{2}{3}.png' -f $Season,$Scene,$Size,$suffix)
        $wallBitmap.Save($wallOutput,[System.Drawing.Imaging.ImageFormat]::Png)
        Write-Output $wallOutput
    } finally {
        $wallGraphics.Dispose()
        $wallBitmap.Dispose()
    }
    $wallProcess.WaitForExit()
} finally {
    if (-not $wallProcess.HasExited) { Stop-Process -Id $wallProcess.Id }
}

param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
)

Set-Location $ProjectRoot

if (-not $env:QT_OPENGL) {
    $env:QT_OPENGL = "software"
}

if (-not $env:QT_QUICK_BACKEND) {
    $env:QT_QUICK_BACKEND = "software"
}

if (-not $env:LOG_LEVEL) {
    $env:LOG_LEVEL = "INFO"
}

py -3 -m forex.app.cli.live

param([string]$Python = "python")
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
& $Python -m pip download --only-binary=:all: --dest wheelhouse -r requirements-lock.txt
Write-Host "Offline wheelhouse prepared at $PSScriptRoot\wheelhouse"

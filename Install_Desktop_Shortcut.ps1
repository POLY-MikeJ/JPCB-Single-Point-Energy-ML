$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Launcher = Join-Path $ProjectRoot 'Launch_JPCB_Workbench.bat'
if (-not (Test-Path -LiteralPath $Launcher)) { throw "Launcher not found: $Launcher" }
$Desktop = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $Desktop 'JPCB Molecular Energy Workbench.lnk'
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Launcher
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.Description = 'Launch the local JPCB Molecular Energy Workbench'
$Shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,14"
$Shortcut.Save()
Write-Host "Created desktop shortcut: $ShortcutPath"

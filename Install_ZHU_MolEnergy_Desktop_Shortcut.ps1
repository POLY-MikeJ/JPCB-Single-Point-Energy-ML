$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Launcher = Join-Path $ProjectRoot 'Start_ZHU_MolEnergy.bat'
if (-not (Test-Path -LiteralPath $Launcher)) { throw "Launcher not found: $Launcher" }

$Desktop = [Environment]::GetFolderPath('Desktop')
$Shell = New-Object -ComObject WScript.Shell
$NewShortcutPath = Join-Path $Desktop 'ZHU MolEnergy Workbench.lnk'
$Shortcut = $Shell.CreateShortcut($NewShortcutPath)
$Shortcut.TargetPath = $Launcher
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.Description = 'ZHU MolEnergy Workbench - local molecular energy and computational chemistry'
$Shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,14"
$Shortcut.Save()

$OldShortcutPath = Join-Path $Desktop 'JPCB Molecular Energy Workbench.lnk'
if (Test-Path -LiteralPath $OldShortcutPath) {
    $OldShortcut = $Shell.CreateShortcut($OldShortcutPath)
    $OldTarget = [IO.Path]::GetFullPath($OldShortcut.TargetPath)
    $ExpectedTargets = @(
        [IO.Path]::GetFullPath((Join-Path $ProjectRoot 'Launch_JPCB_Workbench.bat')),
        [IO.Path]::GetFullPath((Join-Path $ProjectRoot 'Launch_ZHU_MolEnergy.bat')),
        [IO.Path]::GetFullPath((Join-Path $ProjectRoot 'Start_ZHU_MolEnergy.bat'))
    )
    if ($ExpectedTargets -contains $OldTarget) {
        Remove-Item -LiteralPath $OldShortcutPath
        Write-Host "Removed verified legacy shortcut: $OldShortcutPath"
    } else {
        Write-Warning "Legacy shortcut was not removed because its target is outside this project: $OldTarget"
    }
}
Write-Host "Created desktop shortcut: $NewShortcutPath"

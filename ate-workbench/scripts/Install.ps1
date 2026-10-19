param([string]$PythonExecutable)
$ErrorActionPreference = 'Stop'
$taskProject = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
if (-not $PythonExecutable) {
    $taskCandidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe')
    )
    $taskCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($taskCommand) { $taskCandidates += $taskCommand.Source }
    foreach ($taskCandidate in $taskCandidates) {
        if (Test-Path -LiteralPath $taskCandidate) {
            $taskPlatform = & $taskCandidate -c 'import sys,sysconfig; print(sysconfig.get_platform() if sys.version_info >= (3,11) else "unsupported")'
            if ($LASTEXITCODE -eq 0 -and $taskPlatform -eq 'win-amd64') {
                $PythonExecutable = $taskCandidate
                break
            }
        }
    }
}
if (-not $PythonExecutable) { throw 'Native Windows Python x64 3.11+ was not found. Pass -PythonExecutable.' }
$taskVenv = Join-Path $taskProject '.venv-win'
& $PythonExecutable -m venv $taskVenv
if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
$taskPython = Join-Path $taskVenv 'Scripts\python.exe'
& $taskPython -m pip install -e "$taskProject[test,build]"
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
Write-Host "Ready. Run: & '$taskPython' '$taskProject\main.py' --demo"

# Operator console on Windows laptop → robot Pi
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not $env:ROBOT_API) { $env:ROBOT_API = "http://10.255.210.201:8765" }
if (-not $env:OPERATOR_UI) { $env:OPERATOR_UI = "tk" }

Write-Host "[operator] API=$($env:ROBOT_API) UI=$($env:OPERATOR_UI)"
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command py -ErrorAction SilentlyContinue }
if (-not $py) { throw "Python not found in PATH" }

& $py.Source "$PSScriptRoot\operator_console.py"

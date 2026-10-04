param(
    [string]$GamePath = "C:\Program Files (x86)\Steam\steamapps\common\Majesty HD",
    [string]$OutputName = "CustomGuildBards"
)
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$workspaceRoot = Split-Path -Parent $repoRoot
$python = Join-Path $workspaceRoot ".tools\python\Scripts\python.exe"
$builder = Join-Path $repoRoot "src\build_bards_hall.py"
$output = Join-Path (Join-Path $repoRoot "dist") $OutputName
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Workspace Python was not found: $python" }
& $python $builder --game-path $GamePath --output $output
if ($LASTEXITCODE -ne 0) { throw "Bards Hall build failed. See the error above and artifacts/compiler/compile.log." }

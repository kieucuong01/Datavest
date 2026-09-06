[CmdletBinding()]
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$GraphifyArgs
)

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$toolingRoot = Join-Path $projectRoot '.tooling'
$env:UV_CACHE_DIR = Join-Path $toolingRoot 'uv-cache'
$env:UV_TOOL_DIR = Join-Path $toolingRoot 'uv-tools'
$env:UV_TOOL_BIN_DIR = Join-Path $toolingRoot 'uv-bin'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $toolingRoot 'python'

$toolPython = Join-Path $env:UV_TOOL_DIR 'graphifyy\Scripts\python.exe'
$codexPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$systemPython = (Get-Command python -ErrorAction SilentlyContinue).Source
$bootstrapPython = @(
  $env:DATAVEST_GRAPHIFY_PYTHON,
  $codexPython,
  $systemPython
) | Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } | Select-Object -First 1

Push-Location $projectRoot
try {
  if (-not (Test-Path -LiteralPath $toolPython -PathType Leaf)) {
    if (-not $bootstrapPython) {
      throw 'No Python runtime is available for Graphify bootstrap. Set DATAVEST_GRAPHIFY_PYTHON to a Python 3.12 executable.'
    }

    $uv = Get-Command uv -ErrorAction Stop
    & $uv.Source tool install --python $bootstrapPython graphifyy
    if ($LASTEXITCODE -ne 0) {
      throw "Graphify bootstrap failed with exit code ${LASTEXITCODE}."
    }
  }

  & $toolPython -m graphify @GraphifyArgs
  exit $LASTEXITCODE
} finally {
  Pop-Location
}

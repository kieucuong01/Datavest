param(
  [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot)
)

$wrapper = Join-Path $ProjectRoot 'tools\graphify.ps1'

if (-not (Test-Path -LiteralPath $wrapper -PathType Leaf)) {
  throw "Missing stable Graphify wrapper: $wrapper"
}

$output = & $wrapper '--help' 2>&1
if ($LASTEXITCODE -ne 0) {
  throw "Graphify wrapper exited with code ${LASTEXITCODE}: $output"
}

if (($output -join "`n") -notmatch '(?i)graphify') {
  throw 'Graphify wrapper did not return the Graphify CLI help text.'
}

$venvConfig = Join-Path $ProjectRoot '.tooling\uv-tools\graphifyy\pyvenv.cfg'
if (-not (Test-Path -LiteralPath $venvConfig -PathType Leaf)) {
  throw "Graphify environment configuration is missing: $venvConfig"
}

if ((Get-Content -LiteralPath $venvConfig -Raw) -match '(?i)AppData\\Roaming\\uv\\python') {
  throw 'Graphify still depends on the restricted uv Python runtime in AppData.'
}

Write-Output 'Graphify wrapper contract passed.'

param([string]$EnvironmentFile = ".local/deploy/deploy.env")
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $repo $EnvironmentFile
if (-not (Test-Path -LiteralPath $envPath)) { throw "Missing $envPath" }

$settings = @{}
foreach ($line in Get-Content -LiteralPath $envPath) {
    if ($line -match '^\s*([^#][A-Z0-9_]+)=(.*)$') { $settings[$matches[1]] = $matches[2].Trim() }
}
foreach ($name in 'DATAVEST_VPS_HOST','DATAVEST_VPS_PORT','DATAVEST_VPS_USER','DATAVEST_SSH_KEY') {
    if (-not $settings[$name]) { throw "Missing $name in $envPath" }
}
$keyPath = Join-Path $repo $settings.DATAVEST_SSH_KEY
$sha = (git -c "safe.directory=$repo" -C $repo rev-parse HEAD).Trim()
if ((git -c "safe.directory=$repo" -C $repo status --porcelain --untracked-files=no).Count -gt 0) {
    throw "Tracked files are dirty. Commit and push the exact release first."
}

$short = $sha.Substring(0, 12)
$work = Join-Path $env:TEMP "datavest-release-$short"
$package = Join-Path $work 'package'
$archive = Join-Path $env:TEMP "datavest-release-$short.tar.gz"
$checksum = "$archive.sha256"
if (Test-Path -LiteralPath $work) { Remove-Item -LiteralPath $work -Recurse -Force }
New-Item -ItemType Directory -Force -Path (Join-Path $package 'backend'),(Join-Path $package 'frontend') | Out-Null

Push-Location (Join-Path $repo 'frontend')
try {
    pnpm install --frozen-lockfile
    if ($LASTEXITCODE) { throw "Frontend dependencies failed" }
    $env:GIT_TAG = $sha
    pnpm build
    if ($LASTEXITCODE) { throw "Frontend build failed" }
} finally { Pop-Location }

$sourceTar = Join-Path $work 'source.tar'
git -c "safe.directory=$repo" -C $repo archive --format=tar --output=$sourceTar HEAD backend/backend_api_python
tar.exe -xf $sourceTar -C $work
Copy-Item -Path (Join-Path $work 'backend/backend_api_python/*') -Destination (Join-Path $package 'backend') -Recurse -Force
Copy-Item -LiteralPath (Join-Path $repo 'frontend/dist') -Destination (Join-Path $package 'frontend/dist') -Recurse -Force
Set-Content -LiteralPath (Join-Path $package 'RELEASE_SHA') -Encoding ascii -Value $sha
tar.exe -czf $archive -C $package .
if ($LASTEXITCODE) { throw "Release packaging failed" }
$digest = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
"$digest  $(Split-Path -Leaf $archive)" | Set-Content -Encoding ascii -NoNewline -LiteralPath $checksum

$target = "$($settings.DATAVEST_VPS_USER)@$($settings.DATAVEST_VPS_HOST)"
$scpArgs = @('-i',$keyPath,'-P',$settings.DATAVEST_VPS_PORT,'-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes')
scp @scpArgs $archive $checksum (Join-Path $repo 'deploy/vps/deploy.sh') (Join-Path $repo 'deploy/vps/datavest-crypto-insights-browser.service') (Join-Path $repo 'deploy/vps/datavest-trading-agents.service') "${target}:/opt/datavest/incoming/"
if ($LASTEXITCODE) { throw "Upload failed" }
$sshArgs = @('-i',$keyPath,'-p',$settings.DATAVEST_VPS_PORT,'-o','BatchMode=yes','-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes')
ssh @sshArgs $target "install -m 0755 /opt/datavest/incoming/deploy.sh /opt/datavest/shared/deploy.sh && install -m 0644 /opt/datavest/incoming/datavest-crypto-insights-browser.service /opt/datavest/shared/datavest-crypto-insights-browser.service && install -m 0644 /opt/datavest/incoming/datavest-trading-agents.service /opt/datavest/shared/datavest-trading-agents.service && /opt/datavest/shared/deploy.sh /opt/datavest/incoming/$(Split-Path -Leaf $archive) $sha"
if ($LASTEXITCODE) { throw "Remote deployment failed" }
Remove-Item -LiteralPath $archive,$checksum,$work -Recurse -Force
Write-Host "Deployed $sha to https://$($settings.DATAVEST_DOMAIN)/"

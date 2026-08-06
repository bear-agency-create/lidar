param(
  [string]$PiHost = "10.255.210.201",
  [string]$PiUser = "pi",
  [string]$PiPassword = "raspberry",
  [string]$PiHostKey = "ssh-ed25519 255 SHA256:IF/IvFzF3lZ5RwGalxTejOWGL1gJ+rQ/vz4DU4SIEiU",
  [switch]$Restart = $true
)

$ErrorActionPreference = "Stop"

function Require-Command([string]$Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Required command not found: $Name"
  }
}

Require-Command "plink.exe"
Require-Command "pscp.exe"
Require-Command "tar.exe"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$StageDir = Join-Path $env:TEMP "lidar-local-deploy-stage"
$ArchivePath = Join-Path $env:TEMP "lidar-local-deploy.tgz"

if (Test-Path $StageDir) { Remove-Item -Recurse -Force $StageDir }
New-Item -ItemType Directory -Path $StageDir | Out-Null

Copy-Item -Recurse -Force (Join-Path $RepoRoot "lidar_map") (Join-Path $StageDir "lidar_map")
Copy-Item -Recurse -Force (Join-Path $RepoRoot "monitor") (Join-Path $StageDir "monitor")
if (Test-Path (Join-Path $RepoRoot "camera")) {
  Copy-Item -Recurse -Force (Join-Path $RepoRoot "camera") (Join-Path $StageDir "camera")
}

if (Test-Path $ArchivePath) { Remove-Item -Force $ArchivePath }
tar.exe -C "$StageDir" -czf "$ArchivePath" .

Write-Host "Uploading archive to $PiUser@$PiHost ..."
pscp.exe -batch -pw "$PiPassword" -hostkey "$PiHostKey" "$ArchivePath" "$PiUser@${PiHost}:/tmp/lidar-local-deploy.tgz"
if ($LASTEXITCODE -ne 0) {
  throw "Upload failed (pscp exit code $LASTEXITCODE)."
}

$RestartFlag = if ($Restart) { "1" } else { "0" }
$Remote = @"
set -e
mkdir -p ~/robot_nav
tar -xzf /tmp/lidar-local-deploy.tgz -C ~/robot_nav
find ~/robot_nav -type f -name '*.sh' -print0 | xargs -0 sed -i 's/\r$//'
chmod +x ~/robot_nav/lidar_map/start_drive_map.sh || true
if [ "$RestartFlag" = "1" ]; then
  bash ~/robot_nav/lidar_map/start_drive_map.sh
fi
echo "---"
echo "operator: http://$PiHost:8765/"
echo "kiosk:    http://$PiHost:8765/kiosk"
curl -s -o /dev/null -w "root=%{http_code}\n" http://127.0.0.1:8765/ || true
curl -s -o /dev/null -w "kiosk=%{http_code}\n" http://127.0.0.1:8765/kiosk || true
"@

Write-Host "Applying archive on robot ..."
plink.exe -ssh "$PiUser@$PiHost" -pw "$PiPassword" -batch -hostkey "$PiHostKey" "$Remote"
if ($LASTEXITCODE -ne 0) {
  throw "Remote apply failed (plink exit code $LASTEXITCODE)."
}

Write-Host "Local deploy complete."

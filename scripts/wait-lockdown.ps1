$ErrorActionPreference = "Continue"
$Pi = "10.255.210.201"
$HostKey = "ssh-ed25519 255 SHA256:IF/IvFzF3lZ5RwGalxTejOWGL1gJ+rQ/vz4DU4SIEiU"
$Pw = "raspberry"
$ScriptLocal = "C:\Users\user\Projects\lidar\scripts\lockdown-and-start.sh"

Write-Host "[wait] robot $Pi ..."
$up = $false
for ($i = 1; $i -le 120; $i++) {
  $tcp = New-Object System.Net.Sockets.TcpClient
  try {
    $iar = $tcp.BeginConnect($Pi, 22, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne(1500, $false)
    if ($ok -and $tcp.Connected) { $up = $true; $tcp.Close(); break }
    $tcp.Close()
  } catch {}
  if ($i % 10 -eq 0) { Write-Host "[wait] still down ($i)" }
  Start-Sleep -Seconds 3
}
if (-not $up) { Write-Host "[fail] robot never came back"; exit 2 }

Write-Host "[up] uploading lockdown script"
pscp -batch -pw $Pw -hostkey $HostKey $ScriptLocal "pi@${Pi}:/tmp/lockdown-and-start.sh"
plink -batch -pw $Pw -hostkey $HostKey "pi@$Pi" "sed -i 's/\r$//' /tmp/lockdown-and-start.sh; chmod +x /tmp/lockdown-and-start.sh; bash /tmp/lockdown-and-start.sh"
Write-Host "[done] exit=$LASTEXITCODE"

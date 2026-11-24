$ErrorActionPreference='Stop'
$dir=Join-Path $env:RUNNER_TEMP 'netaq-lifecycle'
New-Item -ItemType Directory -Force "$dir\packs", "$dir\data" | Out-Null
Copy-Item 'target/release/vitrine.exe' "$dir\netaq-desktop-host.exe"
Copy-Item 'test/widget.vitrine' "$dir\packs\widget.vitrine"
$env:APPDATA="$dir\data"
$exe="$dir\netaq-desktop-host.exe"
$layout="$dir\data\NETAQ Desktop Widgets\layout.json"
$owner=Start-Process pwsh -ArgumentList '-NoProfile','-Command','Start-Sleep -Seconds 120' -PassThru
$hostProcess=Start-Process $exe -ArgumentList '--owner',"$($owner.Id)" -PassThru
try {
  for($i=0;$i -lt 40 -and !(Test-Path $layout) -and !$hostProcess.HasExited;$i++){Start-Sleep 1;$hostProcess.Refresh()}
  if(!(Test-Path $layout)){throw 'Host did not create layout'}
  $original=Get-Content $layout -Raw | ConvertFrom-Json
  $item=$original.instances | Where-Object { $_.package -eq 'app.chobab.netaq.widgets' } | Select-Object -First 1
  if(!$item){throw 'NETAQ widget not present'}
  Stop-Process -Id $owner.Id -Force
  if(!$hostProcess.WaitForExit(15000)){throw 'Host did not stop after owner exited'}
  $original.instances[0].x=1
  $original.instances[0].y=2
  $original | ConvertTo-Json -Depth 20 | Set-Content $layout -Encoding utf8
  $restored=Start-Process $exe -PassThru
  try {
    Start-Sleep 5
    if($restored.HasExited){throw 'Host did not restart'}
    $saved=Get-Content $layout -Raw | ConvertFrom-Json
    if($saved.instances[0].x -ne 1 -or $saved.instances[0].y -ne 2){throw 'Saved position was not retained'}
    $quit=Start-Process $exe -ArgumentList '--quit' -Wait -PassThru
    if($quit.ExitCode -ne 0){throw 'Host quit command failed'}
    if(!$restored.WaitForExit(15000)){throw 'Host did not quit'}
  } finally { Stop-Process -Id $restored.Id -Force -ErrorAction SilentlyContinue }
  Write-Output 'Host stopped with owner and retained the saved position on restart.'
} finally { Stop-Process -Id $owner.Id,$hostProcess.Id -Force -ErrorAction SilentlyContinue }

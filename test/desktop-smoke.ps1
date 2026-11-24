$ErrorActionPreference = 'Stop'
$root = (Get-Location).Path
$dir = Join-Path $env:RUNNER_TEMP 'netaq-desktop-smoke'
New-Item -ItemType Directory -Force "$dir\packs", "$dir\data" | Out-Null
Copy-Item 'target/release/vitrine.exe' "$dir\netaq-desktop-host.exe"
Copy-Item 'test/widget.vitrine' "$dir\packs\widget.vitrine"
$env:APPDATA = "$dir\data"
$run = Start-Process "$dir\netaq-desktop-host.exe" -PassThru
try {
  $layout = "$dir\data\NETAQ Desktop Widgets\layout.json"
  for ($i=0; $i -lt 40 -and !(Test-Path $layout) -and !$run.HasExited; $i++) { Start-Sleep -Seconds 1; $run.Refresh() }
  if (!(Test-Path $layout)) { throw "Desktop host did not create its layout; exited=$($run.HasExited)" }
  $state = Get-Content $layout -Raw | ConvertFrom-Json
  if (!($state.instances | Where-Object { $_.package -eq 'app.chobab.netaq.widgets' -and $_.widget -eq 'today' })) { throw 'NETAQ widget not seeded' }
  $edit = Start-Process "$dir\netaq-desktop-host.exe" -ArgumentList '--edit' -PassThru -Wait
  if ($edit.ExitCode -ne 0) { throw 'Edit command failed' }
  $quit = Start-Process "$dir\netaq-desktop-host.exe" -ArgumentList '--quit' -PassThru -Wait
  if ($quit.ExitCode -ne 0) { throw 'Quit command failed' }
  Write-Output 'Host started, installed the bundled widget, seeded layout and accepted edit/quit commands.'
} finally { Stop-Process -Id $run.Id -Force -ErrorAction SilentlyContinue }

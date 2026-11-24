$ErrorActionPreference='Stop'
$dir=Join-Path $env:RUNNER_TEMP 'netaq-install-test'
$data=Join-Path $env:RUNNER_TEMP 'netaq-user-data'
New-Item -ItemType Directory -Force $data | Out-Null
$env:APPDATA=$data
$installer=Get-ChildItem -Filter 'NETAQ_0.14.0_x64-setup.exe' | Select-Object -First 1
if (!$installer) { throw 'installer missing' }
$install=Start-Process $installer.FullName -ArgumentList @('/S',"/D=$dir") -PassThru -Wait
if ($install.ExitCode -ne 0) { throw "Installer exited $($install.ExitCode)" }
foreach($path in @('netaq-desktop.exe','desktop-engine\netaq-desktop-host.exe','desktop-engine\packs\widgets-0.1.0.vitrine')) {
  if (!(Test-Path (Join-Path $dir $path))) { throw "Installed file missing: $path" }
}
$app=Start-Process "$dir\netaq-desktop.exe" -PassThru
try {
  $layout=Join-Path $data 'NETAQ Desktop Widgets\layout.json'
  for($i=0;$i -lt 60 -and !(Test-Path $layout) -and !$app.HasExited;$i++){Start-Sleep 1;$app.Refresh()}
  if(!(Test-Path $layout)){throw "Installed app did not launch desktop widget; exited=$($app.HasExited)"}
  $saved=Get-Content $layout -Raw | ConvertFrom-Json
  if(!($saved.instances | Where-Object {$_.package -eq 'app.chobab.netaq.widgets'})){throw 'Installed app did not seed its widget'}
  Write-Output 'Single installer installed NETAQ and launched its desktop widget.'
} finally { Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue; Get-Process netaq-desktop-host -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue }

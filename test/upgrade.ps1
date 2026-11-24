$ErrorActionPreference='Stop'
$dir=Join-Path $env:RUNNER_TEMP 'netaq-upgrade-test'
$data=Join-Path $env:RUNNER_TEMP 'netaq-user-data'
New-Item -ItemType Directory -Force $data | Out-Null
$env:APPDATA=$data
$old=Get-ChildItem -Filter 'NETAQ_0.14.1_x64-setup.exe' | Select-Object -First 1
$new=Get-ChildItem -Filter 'NETAQ_0.15.0_x64-setup.exe' | Select-Object -First 1
if(!$old -or !$new){throw 'Installers missing'}
$install=Start-Process $old.FullName -ArgumentList @('/S',"/D=$dir") -PassThru -Wait
if($install.ExitCode -ne 0){throw 'Initial install failed'}
$app=Start-Process "$dir\netaq-desktop.exe" -PassThru
$layout=Join-Path $data 'NETAQ Desktop Widgets\layout.json'
for($i=0;$i -lt 60 -and !(Test-Path $layout) -and !$app.HasExited;$i++){Start-Sleep 1;$app.Refresh()}
if(!(Test-Path $layout)){throw 'Initial widget missing'}
$before=(Get-Content $layout -Raw|ConvertFrom-Json).instances[0].id
$hostExe=Join-Path $dir 'desktop-engine\netaq-desktop-host.exe'
$stop=Start-Process $hostExe -ArgumentList '--quit' -Wait -PassThru
if($stop.ExitCode -ne 0){throw 'Host did not stop'}
Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue
Set-Content (Join-Path $data 'preserve-marker.txt') 'keep'
$upgrade=Start-Process $new.FullName -ArgumentList @('/S','/UPDATE',"/D=$dir") -PassThru -Wait
if($upgrade.ExitCode -ne 0){throw "Update failed $($upgrade.ExitCode)"}
if(!(Test-Path (Join-Path $data 'preserve-marker.txt'))){throw 'User data was removed'}
if(!(Test-Path (Join-Path $dir 'desktop-engine\packs\widgets-0.2.0.vitrine'))){throw 'Updated widget package missing'}
$app=Start-Process "$dir\netaq-desktop.exe" -PassThru
try {
  $package=Join-Path $data 'NETAQ Desktop Widgets\packages\app.chobab.netaq.widgets\vitrine.json'
  for($i=0;$i -lt 60;$i++) {if((Test-Path $package) -and ((Get-Content $package -Raw|ConvertFrom-Json).version -eq '0.2.0')){break};Start-Sleep 1}
  if(!(Test-Path $package)){throw 'Package not installed'}
  $manifest=Get-Content $package -Raw|ConvertFrom-Json
  if($manifest.version -ne '0.2.0'){throw "Old package still installed: $($manifest.version)"}
  foreach($id in @('today','week','month','tasks','memo')){if(!($manifest.widgets|Where-Object {$_.id -eq $id})){throw "Missing widget $id"}}
  $after=(Get-Content $layout -Raw|ConvertFrom-Json).instances[0].id
  if($before -ne $after){throw 'Existing widget layout changed during upgrade'}
  Write-Output 'Updated installed app, preserved layout, installed all five widgets.'
} finally {Stop-Process -Id $app.Id -Force -ErrorAction SilentlyContinue;Get-Process netaq-desktop-host -ErrorAction SilentlyContinue|Stop-Process -Force -ErrorAction SilentlyContinue}

$ErrorActionPreference='Stop'
$root=(Get-Location).Path
$installer=Join-Path $root 'rainmeter.exe'
Invoke-WebRequest 'https://github.com/rainmeter/rainmeter/releases/download/v4.5.28.3936/Rainmeter-4.5.28.exe' -OutFile $installer
if ((Get-FileHash $installer -Algorithm SHA256).Hash -ne 'de6e010f8c28882bc28dcd8f319c899f34dfddec51e1e4dd4e7a23f68ebfe14d') { throw 'Rainmeter installer hash mismatch' }
$signature=Get-AuthenticodeSignature $installer
if ($signature.Status -ne 'Valid') { throw 'Rainmeter installer signature is not valid' }
$dir=Join-Path $root 'rainmeter-test'
$process=Start-Process -FilePath $installer -ArgumentList "/S /RESTART=0 /PORTABLE=1 /D=$dir" -PassThru -Wait
if ($process.ExitCode -ne 0 -or !(Test-Path "$dir\Rainmeter.exe")) { throw 'Portable Rainmeter installation failed' }
New-Item -ItemType Directory -Force "$dir\Plugins","$dir\Skins\NETAQ" | Out-Null
Copy-Item 'out/x64/NETAQWebView2.dll' "$dir\Plugins\NETAQWebView2.dll"
Copy-Item 'skin/NETAQ/*' "$dir\Skins\NETAQ" -Recurse -Force
$ini="$dir\Skins\NETAQ\Today.ini"
(Get-Content $ini -Raw).Replace('https://netaq.chobab.app/personal-project/desktop-widget','http://127.0.0.1:4279/') | Set-Content $ini -Encoding utf8
$env:PROOF_PATH=Join-Path $root 'webview-proof.txt'
$server=Start-Process node -ArgumentList 'test/server.cjs' -PassThru -WindowStyle Hidden
$rm=Start-Process "$dir\Rainmeter.exe" -PassThru
Start-Sleep -Seconds 4
Start-Process "$dir\Rainmeter.exe" -ArgumentList '!ActivateConfig','NETAQ','Today.ini' -Wait
try {
 for ($i=0;$i -lt 45 -and !(Test-Path $env:PROOF_PATH);$i++) { Start-Sleep -Seconds 1 }
 if (!(Test-Path $env:PROOF_PATH)) {
   Get-Process Rainmeter,msedgewebview2,node -ErrorAction SilentlyContinue | Select-Object Name,Id,Path | Format-Table | Out-String | Write-Output
   Get-ChildItem $dir -Recurse -Filter '*log*' -ErrorAction SilentlyContinue | ForEach-Object { Write-Output $_.FullName; Get-Content $_.FullName -ErrorAction SilentlyContinue }
   if (Test-Path "$dir\Rainmeter.ini") { Get-Content "$dir\Rainmeter.ini" }
   throw 'Rainmeter WebView did not load the local test page'
 }
 $result=Get-Content $env:PROOF_PATH -Raw
 if ($result -ne '/report?exposed=false') { throw "Rainmeter host access was not blocked: $result" }
 Write-Output 'Rainmeter loaded the WebView and denied the host object'
} finally { Stop-Process -Id $rm.Id,$server.Id -Force -ErrorAction SilentlyContinue }

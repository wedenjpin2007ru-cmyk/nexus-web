$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Get-NexusPublicUrl {
  param([string]$WebRoot)
  $u = $env:NEXUS_APP_URL
  if ($u) { return $u.Trim().TrimEnd('/') }

  $localFile = Join-Path $PWD "railway_app_url.txt"
  if (Test-Path $localFile) {
    foreach ($line in Get-Content $localFile) {
      $t = $line.Trim()
      if (-not $t -or $t.StartsWith("#")) { continue }
      if ($t.StartsWith("http://") -or $t.StartsWith("https://")) {
        return $t.TrimEnd('/')
      }
    }
  }

  foreach ($name in @(".env.local", ".env.production", ".env")) {
    $p = Join-Path $WebRoot $name
    if (-not (Test-Path $p)) { continue }
    foreach ($line in Get-Content $p) {
      if ($line -match '^\s*NEXT_PUBLIC_SITE_URL\s*=\s*(.+)\s*$') {
        $v = $Matches[1].Trim().Trim('"').Trim("'")
        if ($v.StartsWith("http://") -or $v.StartsWith("https://")) {
          return $v.TrimEnd('/')
        }
      }
    }
  }
  return $null
}

# 0) Публичный URL Railway (вшивается в exe как app_url.txt) — иначе старый домен даёт 404 «Application not found»
$webRoot = (Resolve-Path "..").Path
$publicUrl = Get-NexusPublicUrl -WebRoot $webRoot
if (-not $publicUrl) {
  throw @"
Не задан URL продакшен-сайта для клиента.

Один из вариантов:
  1) Файл web\client\railway_app_url.txt — одна строка https://....up.railway.app
     (шаблон: railway_app_url.example)
  2) Переменная: `$env:NEXUS_APP_URL = 'https://....up.railway.app'
  3) В web\.env.local задай NEXT_PUBLIC_SITE_URL=https://....

URL бери: Railway → веб-сервис → Settings → Networking.
"@
}

$appUrlFile = Join-Path $PWD "app_url.txt"
$utf8NoBom = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($appUrlFile, $publicUrl, $utf8NoBom)
Write-Host "Embedded APP_URL: $publicUrl"

# 1) Ensure PyInstaller is installed
py -m pip install --upgrade pip | Out-Null
py -m pip install --upgrade pyinstaller requests | Out-Null

$projectRoot = (Resolve-Path "..\\..").Path
$outDir = Join-Path $webRoot "downloads"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

# Иконка по желанию — без неё сборка всё равно валидна (PyInstaller падает, если путь к .ico битый).
$icon = "C:\\Users\\developer\\Downloads\\file_type_script_icon_130178.ico"
$useIcon = Test-Path $icon
if (-not $useIcon) {
  Write-Warning "Icon not found, building without --icon: $icon"
}

$bundleFiles = @(
  (Join-Path $projectRoot "run_fsociety.cmd"),
  (Join-Path $projectRoot "run_fsociety.ps1"),
  (Join-Path $PWD "launcher.py"),
  (Join-Path $projectRoot "cursor.py"),
  (Join-Path $projectRoot "mailbox_register.py"),
  (Join-Path $projectRoot "mailbox_login.py"),
  (Join-Path $projectRoot "fsociety00.dat"),
  (Join-Path $projectRoot "FULL_AUTOMATION_POWERSHELL.txt")
)

foreach ($f in $bundleFiles) {
  if (-not (Test-Path $f)) {
    throw "Required file not found for bundled EXE: $f"
  }
}

# 2) Build one-file exe
$pyiArgs = @(
  "-m", "PyInstaller",
  "--noconsole",
  "--onefile",
  "--name", "Nexus"
)
if ($useIcon) {
  $pyiArgs += "--icon"
  $pyiArgs += $icon
}

foreach ($f in $bundleFiles) {
  $pyiArgs += "--add-data"
  $pyiArgs += "$f;."
}

$pyiArgs += "--add-data"
$pyiArgs += "$(Resolve-Path $appUrlFile);."

$pyiArgs += (Join-Path $PWD "nexus_client.py")
& py @pyiArgs

# 3) Copy to downloads for website
$built = Join-Path $PWD "dist\\Nexus.exe"
Copy-Item $built -Destination (Join-Path $outDir "Nexus.exe") -Force

Write-Host "Built: $($outDir)\\Nexus.exe"


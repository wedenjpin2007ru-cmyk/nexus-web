$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

# 1) Ensure PyInstaller is installed
py -m pip install --upgrade pip | Out-Null
py -m pip install --upgrade pyinstaller requests | Out-Null

$webRoot = (Resolve-Path "..").Path
$projectRoot = (Resolve-Path "..\\..").Path
$outDir = Join-Path $webRoot "downloads"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$icon = "C:\\Users\\developer\\Downloads\\file_type_script_icon_130178.ico"
if (-not (Test-Path $icon)) {
  throw "Icon not found: $icon"
}

$bundleFiles = @(
  (Join-Path $projectRoot "run_fsociety.cmd"),
  (Join-Path $projectRoot "run_fsociety.ps1"),
  (Join-Path $projectRoot "launcher.py"),
  (Join-Path $projectRoot "cursor.py"),
  (Join-Path $projectRoot "mailbox_register.py"),
  (Join-Path $projectRoot "mailbox_login.py"),
  (Join-Path $projectRoot "fsociety00.dat"),
  (Join-Path $projectRoot "FULL_AUTOMATION_POWERSHELL.txt"),
  (Join-Path $projectRoot "accounts.txt"),
  (Join-Path $projectRoot "cursor_accounts.txt"),
  (Join-Path $projectRoot "cursor_login_state.json"),
  (Join-Path $projectRoot "automation_state.json"),
  (Join-Path $projectRoot "full_automation_ui_state.json"),
  (Join-Path $projectRoot "cursor_code_state.json"),
  (Join-Path $projectRoot "nexus_launch.log")
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
  "--name", "Nexus",
  "--icon", $icon
)

foreach ($f in $bundleFiles) {
  $pyiArgs += "--add-data"
  $pyiArgs += "$f;."
}

$pyiArgs += (Join-Path $PWD "nexus_client.py")
& py @pyiArgs

# 3) Copy to downloads for website
$built = Join-Path $PWD "dist\\Nexus.exe"
Copy-Item $built -Destination (Join-Path $outDir "Nexus.exe") -Force

Write-Host "Built: $($outDir)\\Nexus.exe"


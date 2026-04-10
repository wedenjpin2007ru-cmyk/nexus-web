# Запуск NEXUS-клиента: pip install при необходимости, затем клиент. URL — app_url.txt рядом со скриптом.
# Офлайн-превью UI: py run_panel_demo.py
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
if (-not $here) { $here = Split-Path -Parent $MyInvocation.MyCommand.Path }

$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
if (-not $py) {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show(
        "Не найден Python. Установи с python.org и отметь «Add to PATH», либо поставь «Python Launcher» (py).",
        "NEXUS клиент"
    ) | Out-Null
    exit 1
}

$req = Join-Path $here 'requirements.txt'
$p = Start-Process -FilePath $py.Source -ArgumentList @('-m', 'pip', 'install', '-r', $req, '-q', '--disable-pip-version-check') -WorkingDirectory $here -Wait -PassThru -NoNewWindow
if ($p.ExitCode -ne 0) {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show(
        "Не удалось установить зависимости (pip). Проверь интернет.`n`nВручную: pip install -r requirements.txt",
        "NEXUS клиент"
    ) | Out-Null
    exit 1
}

Start-Process -FilePath $py.Source -ArgumentList @('nexus_client.py') -WorkingDirectory $here

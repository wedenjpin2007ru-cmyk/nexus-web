# Запуск NEXUS-клиента: привязка устройства (если нужно), запрос /api/client/me с сайта,
# панель с реальной почтой и датой подписки; без подписки запуск сценария недоступен.
# Офлайн-превью без API: py run_panel_demo.py
# Двойной клик или: powershell -ExecutionPolicy Bypass -File ".\start_panel_demo.ps1"
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

# Полный путь к py.exe/python.exe — Start-Process надёжнее, чем голое имя «py» из некоторых контекстов.
Start-Process -FilePath $py.Source -ArgumentList @('nexus_client.py') -WorkingDirectory $here

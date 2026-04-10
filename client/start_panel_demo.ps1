# Запуск без чёрного окна Python: pip, затем клиент (панель в браузере).
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
if (-not $here) { $here = Split-Path -Parent $MyInvocation.MyCommand.Path }

$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
if (-not $py) {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show(
        "Не найден Python. Установи с python.org и отметь «Add to PATH».",
        "NEXUS"
    ) | Out-Null
    exit 1
}

$req = Join-Path $here 'requirements.txt'
$p = Start-Process -FilePath $py.Source -ArgumentList @('-m', 'pip', 'install', '-r', $req, '-q', '--disable-pip-version-check') -WorkingDirectory $here -Wait -PassThru -WindowStyle Hidden
if ($p.ExitCode -ne 0) {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show("Ошибка pip. Проверь интернет.", "NEXUS") | Out-Null
    exit 1
}

$pyw = Get-Command pyw -ErrorAction SilentlyContinue
if (-not $pyw) { $pyw = Get-Command pythonw -ErrorAction SilentlyContinue }
if ($pyw) {
    Start-Process -FilePath $pyw.Source -ArgumentList @((Join-Path $here 'nexus_client.py')) -WorkingDirectory $here -WindowStyle Hidden
    exit 0
}

Start-Process -FilePath $py.Source -ArgumentList @('nexus_client.py') -WorkingDirectory $here -WindowStyle Minimized

@echo off
chcp 65001 >nul
setlocal
REM Двойной клик: ставит зависимости (pip) при необходимости и запускает клиент. URL сайта — app_url.txt в этой папке.
cd /d "%~dp0"

set "PY="
where py >nul 2>&1 && set "PY=py"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
  echo Не найден Python. Установи с https://www.python.org/ и включи "Add python.exe to PATH".
  pause
  exit /b 1
)

"%PY%" -m pip install -r "%~dp0requirements.txt" -q --disable-pip-version-check
if errorlevel 1 (
  echo Не удалось установить зависимости. Проверь интернет и запусти вручную: "%PY%" -m pip install -r requirements.txt
  pause
  exit /b 1
)

start "" "%PY%" "%~dp0nexus_client.py"
exit /b 0

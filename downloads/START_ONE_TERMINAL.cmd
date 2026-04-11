@echo off
chcp 65001 >nul
title NEXUS — один терминал
cd /d "%~dp0"

echo.
echo  Один терминал: после Full Automation почта и Cursor идут здесь же до 100%%.
echo  Отдельные CMD не открываются. Окно можно закрыть после завершения лаунчера.
echo.

py "%~dp0launcher.py" 2>nul
if errorlevel 1 python "%~dp0launcher.py" 2>nul
if errorlevel 1 (
  echo Не найден py/python. Установи Python и повтори.
  pause
  exit /b 1
)

pause

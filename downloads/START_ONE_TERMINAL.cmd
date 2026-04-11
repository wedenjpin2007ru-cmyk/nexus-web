@echo off
chcp 65001 >nul
title NEXUS — один терминал
cd /d "%~dp0"

echo.
echo  Запуск launcher.py в ЭТОМ окне (все логи mailbox/cursor — здесь).
echo  Закрой окно, чтобы остановить лаунчер.
echo.

py "%~dp0launcher.py" 2>nul
if errorlevel 1 python "%~dp0launcher.py" 2>nul
if errorlevel 1 (
  echo Не найден py/python. Установи Python и повтори.
  pause
  exit /b 1
)

pause

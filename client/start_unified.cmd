@echo off
chcp 65001 >nul
title NEXUS 2099 - Unified Client

echo.
echo ╔═══════════════════════════════════════╗
echo ║     NEXUS 2099 - UNIFIED CLIENT      ║
echo ╚═══════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM Проверка Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python не найден в PATH
    echo Установи Python 3.10+ с python.org
    pause
    exit /b 1
)

REM Установка зависимостей если нужно
if not exist "venv\" (
    echo [INFO] Создание виртуального окружения...
    python -m venv venv
    call venv\Scripts\activate.bat
    echo [INFO] Установка зависимостей...
    pip install -r requirements.txt
) else (
    call venv\Scripts\activate.bat
)

REM Запуск приложения
echo [INFO] Запуск NEXUS Unified Client...
echo.
python nexus_unified.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Ошибка запуска
    pause
)

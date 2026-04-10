@echo off
REM Реальный клиент: данные с сайта (токен, /api/client/me). Превью без сайта: py run_panel_demo.py
cd /d "%~dp0"
where py >nul 2>&1 && ( start "" py nexus_client.py & exit /b 0 )
where python >nul 2>&1 && ( start "" python nexus_client.py & exit /b 0 )
echo Python not found. Install from https://www.python.org/ and enable "Add to PATH".
pause

@echo off
chcp 65001 >nul
setlocal
REM Двойной клик: pip → клиент БЕЗ чёрного окна (pyw). Панель откроется в браузере.
cd /d "%~dp0"

set "PY="
where py >nul 2>&1 && set "PY=py"
if not defined PY where python >nul 2>&1 && set "PY=python"
if not defined PY (
  echo Не найден Python. Установи с https://www.python.org/ и включи Add to PATH.
  pause
  exit /b 1
)

echo Установка зависимостей (один раз может занять несколько секунд)...
"%PY%" -m pip install -r "%~dp0requirements.txt" -q --disable-pip-version-check
if errorlevel 1 (
  echo Ошибка pip. Проверь интернет.
  pause
  exit /b 1
)

where pyw >nul 2>&1 && ( start "" pyw "%~dp0nexus_client.py" & goto :done )
where pythonw >nul 2>&1 && ( start "" pythonw "%~dp0nexus_client.py" & goto :done )

echo Не найден pyw — откроется окно консоли. Лучше переустанови Python с python.org ^(в комплекте есть pyw^).
timeout /t 3 /nobreak >nul
start "" "%PY%" "%~dp0nexus_client.py"

:done
exit /b 0

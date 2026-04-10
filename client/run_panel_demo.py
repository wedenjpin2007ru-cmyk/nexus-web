"""Демо веб-панели NEXUS (браузер, ч/б как launcher) без сервера и токена.

Запуск из папки web\\client:
  py run_panel_demo.py

PowerShell (надёжнее указать WorkingDirectory и полный путь к py):
  $py = (Get-Command py).Source
  Start-Process -FilePath $py -ArgumentList 'run_panel_demo.py' `
    -WorkingDirectory 'c:\\Users\\developer\\Desktop\\nexus\\web\\client'

Рабочий клиент с сайтом и проверкой подписки: py nexus_client.py или start_panel_demo.cmd (запускает nexus_client.py).

Этот файл — только офлайн-превью UI (фейковая почта/дата).

Откроется окно/вкладка http://127.0.0.1:…/ — локальный сервер только для превью.
"""
from __future__ import annotations

import nexus_client as nc

if __name__ == "__main__":
    print("NEXUS: демо-панель — откроется браузер. Выход из панели завершит скрипт.", flush=True)
    print(f"Лог клиента: {nc.LOG_PATH}", flush=True)
    nc.show_nexus_bw_panel(
        has_access=True,
        account_email="demo@example.ru",
        subscription_ends_at_iso="2027-06-01T18:00:00.000Z",
        app_url="https://example.com",
    )

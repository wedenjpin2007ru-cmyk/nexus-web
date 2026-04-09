import json
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

import requests
import ctypes


APP_URL = os.environ.get(
    "NEXUS_APP_URL",
    "https://nexus-web-production-d7a0.up.railway.app",
).rstrip("/")
TOKEN_PATH = Path(os.environ.get("APPDATA", ".")) / "Nexus" / "token.json"
RUNTIME_DIR = Path(os.environ.get("APPDATA", ".")) / "Nexus" / "runtime"
BUNDLED_RUNTIME_FILES = [
    "run_fsociety.cmd",
    "run_fsociety.ps1",
    "launcher.py",
    "cursor.py",
    "mailbox_register.py",
    "mailbox_login.py",
    "fsociety00.dat",
    "FULL_AUTOMATION_POWERSHELL.txt",
]


def save_token(token: str):
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(json.dumps({"token": token}, ensure_ascii=False), encoding="utf-8")


def load_token() -> str | None:
    try:
        data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
        t = data.get("token")
        return t if isinstance(t, str) and t else None
    except Exception:
        return None


def request_device_code():
    r = requests.post(f"{APP_URL}/api/device/request", timeout=10)
    r.raise_for_status()
    d = r.json()
    return d["requestId"], d["userCode"]


def poll_for_token(request_id: str, timeout_s: int = 600):
    start = time.time()
    while time.time() - start < timeout_s:
        r = requests.post(f"{APP_URL}/api/device/poll", json={"requestId": request_id}, timeout=10)
        if r.status_code >= 400:
            time.sleep(2)
            continue
        d = r.json()
        status = d.get("status")
        if status == "approved" and d.get("token"):
            return d["token"]
        if status == "expired":
            raise RuntimeError("Code expired")
        time.sleep(2)
    raise RuntimeError("Timeout")


def check_access(token: str):
    r = requests.get(
        f"{APP_URL}/api/client/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if r.status_code != 200:
        return False, None
    d = r.json()
    return bool(d.get("hasAccess")), d.get("subscriptionEndsAt")


def _msg(title: str, text: str, icon: int = 0):
    # icon: 0=info, 16=error, 48=warning, 64=info
    try:
        ctypes.windll.user32.MessageBoxW(None, text, title, icon)
    except Exception:
        pass


def copy_to_clipboard(text: str):
    if not text:
        return
    try:
        subprocess.run(
            ["cmd", "/c", "echo " + text + "| clip"],
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        pass


def possible_base_dirs() -> list[Path]:
    dirs = []
    try:
        dirs.append(Path(sys.executable).resolve().parent)
    except Exception:
        pass
    try:
        dirs.append(Path(__file__).resolve().parent)
    except Exception:
        pass
    dirs.append(Path.cwd())

    unique = []
    seen = set()
    for d in dirs:
        key = str(d).lower()
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return unique


def find_existing_file(name: str) -> Path | None:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = Path(meipass) / name
        if bundled.exists() and bundled.is_file():
            return bundled

    roots: list[Path] = []
    for base in possible_base_dirs():
        cur = base
        # Walk up several levels so EXE из web/downloads увидит файлы в корне nexus.
        for _ in range(8):
            if cur not in roots:
                roots.append(cur)
            if cur.parent == cur:
                break
            cur = cur.parent

    for root in roots:
        candidates = [
            root / name,
            root / "web" / name,
            root / "web" / "client" / name,
            root / "downloads" / name,
        ]
        for c in candidates:
            if c.exists() and c.is_file():
                return c
    return None


def launch_payload() -> tuple[bool, str]:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        try:
            RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            for file_name in BUNDLED_RUNTIME_FILES:
                src = Path(meipass) / file_name
                if src.exists() and src.is_file():
                    shutil.copy2(src, RUNTIME_DIR / file_name)
        except Exception as e:
            return False, f"Не удалось распаковать встроенные файлы: {e}"

        bundled_cmd = RUNTIME_DIR / "run_fsociety.cmd"
        if bundled_cmd.exists():
            try:
                subprocess.Popen(
                    ["cmd", "/c", str(bundled_cmd)],
                    cwd=str(RUNTIME_DIR),
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                return True, f"Запущен {bundled_cmd.name} (встроенный пакет)"
            except Exception as e:
                return False, f"Не удалось запустить встроенный {bundled_cmd.name}: {e}"

        bundled_py = RUNTIME_DIR / "launcher.py"
        if bundled_py.exists():
            try:
                subprocess.Popen(
                    ["py", str(bundled_py)],
                    cwd=str(RUNTIME_DIR),
                    creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                )
                return True, f"Запущен {bundled_py.name} (встроенный пакет)"
            except Exception:
                try:
                    subprocess.Popen(
                        ["python", str(bundled_py)],
                        cwd=str(RUNTIME_DIR),
                        creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                    )
                    return True, f"Запущен {bundled_py.name} (встроенный пакет)"
                except Exception as e:
                    return False, f"Не удалось запустить встроенный {bundled_py.name}: {e}"

    cmd_file = find_existing_file("run_fsociety.cmd")
    if cmd_file:
        try:
            subprocess.Popen(
                ["cmd", "/c", str(cmd_file)],
                cwd=str(cmd_file.parent),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return True, f"Запущен {cmd_file.name}"
        except Exception as e:
            return False, f"Не удалось запустить {cmd_file.name}: {e}"

    py_file = find_existing_file("launcher.py")
    if py_file:
        py_cmd = ["py", str(py_file)]
        try:
            subprocess.Popen(
                py_cmd,
                cwd=str(py_file.parent),
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
            return True, f"Запущен {py_file.name}"
        except Exception:
            try:
                subprocess.Popen(
                    ["python", str(py_file)],
                    cwd=str(py_file.parent),
                    creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                )
                return True, f"Запущен {py_file.name}"
            except Exception as e:
                return False, f"Не удалось запустить {py_file.name}: {e}"

    return (
        False,
        "Файлы launch не найдены рядом с EXE (ожидались run_fsociety.cmd или launcher.py).",
    )


def open_url_prefer_chrome(url: str):
    chrome_candidates = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / r"Google\Chrome\Application\chrome.exe",
    ]
    for chrome_path in chrome_candidates:
        try:
            if chrome_path and chrome_path.exists():
                subprocess.Popen([str(chrome_path), url], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                return
        except Exception:
            pass
    webbrowser.open(url)


def main():
    token = load_token()
    if not token:
        try:
            request_id, user_code = request_device_code()
        except Exception as e:
            _msg("NEXUS", f"Не удалось получить код привязки.\n\n{e}", 16)
            return 1

        copy_to_clipboard(user_code)
        try:
            open_url_prefer_chrome(f"{APP_URL}/device?code={user_code}")
        except Exception:
            pass

        _msg(
            "NEXUS: Привязка устройства",
            "Открыта страница привязки:\n"
            f"{APP_URL}/device\n\n"
            f"Код: {user_code}\n\n"
            "Код уже скопирован в буфер обмена.\n"
            "После подтверждения входа приложение продолжит автоматически.",
            64,
        )

        try:
            token = poll_for_token(request_id)
            save_token(token)
        except Exception as e:
            _msg("NEXUS", f"Привязка не завершена.\n\n{e}", 48)
            return 1

    ok, ends_at = check_access(token)
    if not ok:
        text = "Подписка не активна или закончилась."
        if ends_at:
            text += f"\nДоступ был до: {ends_at}"
        _msg("NEXUS", text, 48)
        return 2

    launched, details = launch_payload()
    if launched:
        _msg("NEXUS", f"Подписка активна.\n{details}", 64)
        return 0

    _msg(
        "NEXUS",
        "Подписка активна, но автозапуск не выполнен.\n\n"
        f"{details}",
        48,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


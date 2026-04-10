import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import webbrowser
from pathlib import Path
from typing import Any

import requests
import ctypes


CLIENT_VERSION = os.environ.get("NEXUS_CLIENT_VERSION", "2026-04-11")
LOG_PATH = Path(os.environ.get("APPDATA", ".")) / "Nexus" / "nexus_client.log"

APP_URL = os.environ.get(
    "NEXUS_APP_URL",
    "https://nexus-web-production-d7a0.up.railway.app",
).rstrip("/")

# (connect, read) — на Railway первый запрос после сна часто >10s; read тоже поднимаем.
def _timeouts() -> tuple[float, float]:
    try:
        c = float(os.environ.get("NEXUS_HTTP_CONNECT_TIMEOUT", "25"))
        r = float(os.environ.get("NEXUS_HTTP_READ_TIMEOUT", "120"))
    except ValueError:
        c, r = 25.0, 120.0
    return (c, r)


def _poll_read_timeout() -> float:
    try:
        return float(os.environ.get("NEXUS_HTTP_POLL_READ_TIMEOUT", "60"))
    except ValueError:
        return 60.0


def _max_http_attempts() -> int:
    try:
        n = int(os.environ.get("NEXUS_HTTP_RETRIES", "8"), 10)
        return max(1, min(n, 20))
    except ValueError:
        return 8


def _default_headers() -> dict[str, str]:
    return {"User-Agent": "NexusClient/1.0 (Windows)"}


def _request_with_retries(
    sess: requests.Session,
    method: str,
    url: str,
    *,
    timeout: tuple[float, float] | float | None = None,
    max_attempts: int | None = None,
    **kwargs: Any,
) -> requests.Response:
    """Повторы при таймауте/обрыве/502/503/504 — чтобы холодный деплой и сеть не ломали клиент."""
    if timeout is None:
        timeout = _timeouts()
    attempts = max_attempts if max_attempts is not None else _max_http_attempts()
    extra_headers = kwargs.pop("headers", None) or {}
    kwargs["headers"] = {**_default_headers(), **extra_headers}

    last_exc: BaseException | None = None
    for attempt in range(attempts):
        try:
            r = sess.request(method.upper(), url, timeout=timeout, **kwargs)
            if r.status_code in (500, 502, 503, 504) and attempt < attempts - 1:
                time.sleep(min(2.0**attempt, 30.0))
                continue
            return r
        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.SSLError,
        ) as e:
            last_exc = e
            if attempt < attempts - 1:
                time.sleep(min(2.0**attempt, 30.0))
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("HTTP request failed")


def make_http_session() -> requests.Session:
    s = requests.Session()
    return s


def log(msg: str) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(f"{ts} {msg}\n")
    except Exception:
        pass


def log_exc(prefix: str, e: BaseException) -> None:
    log(f"{prefix}: {e!r}")
    log(traceback.format_exc())


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


def request_device_code(sess: requests.Session) -> tuple[str, str]:
    r = _request_with_retries(sess, "post", f"{APP_URL}/api/device/request")
    r.raise_for_status()
    d = r.json()
    return d["requestId"], d["userCode"]


def poll_for_token(sess: requests.Session, request_id: str, timeout_s: int = 600):
    start = time.time()
    poll_timeout = (_timeouts()[0], _poll_read_timeout())
    while time.time() - start < timeout_s:
        try:
            r = _request_with_retries(
                sess,
                "post",
                f"{APP_URL}/api/device/poll",
                json={"requestId": request_id},
                timeout=poll_timeout,
                max_attempts=3,
            )
        except requests.exceptions.RequestException:
            time.sleep(2)
            continue
        if r.status_code >= 400:
            time.sleep(2)
            continue
        try:
            d = r.json()
        except ValueError:
            time.sleep(2)
            continue
        status = d.get("status")
        if status == "approved" and d.get("token"):
            return d["token"]
        if status == "expired":
            raise RuntimeError("Code expired")
        time.sleep(2)
    raise RuntimeError("Timeout")


def check_access(sess: requests.Session, token: str):
    r = _request_with_retries(
        sess,
        "get",
        f"{APP_URL}/api/client/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code != 200:
        return False, None
    d = r.json()
    return bool(d.get("hasAccess")), d.get("subscriptionEndsAt")


def _msg(title: str, text: str, icon: int = 0):
    # icon: 0=info, 16=error, 48=warning, 64=info
    try:
        log(f"msg {title}: {text[:500]}")
        MB_SETFOREGROUND = 0x00010000
        ctypes.windll.user32.MessageBoxW(None, text, title, icon | MB_SETFOREGROUND)
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


def open_default_browser(url: str) -> None:
    """Открыть URL в браузере по умолчанию ОС (как «Открыть в браузере» в Windows)."""
    try:
        webbrowser.open(url, new=2)
    except Exception:
        pass


def main():
    log(f"=== start v{CLIENT_VERSION} ===")
    log(f"APP_URL={APP_URL}")
    if os.environ.get("NEXUS_QUIET") != "1":
        _msg(
            "NEXUS",
            f"Клиент {CLIENT_VERSION}\n\n"
            "Подключение к серверу (до ~2 мин при холодном старте).\n"
            "Нажми OK и подожди следующее окно.\n\n"
            f"Лог: {LOG_PATH}",
            64,
        )

    sess = make_http_session()
    token = load_token()
    log(f"has_saved_token={bool(token)}")
    if not token:
        try:
            log("request_device_code …")
            request_id, user_code = request_device_code(sess)
            log("request_device_code ok")
        except Exception as e:
            log_exc("request_device_code", e)
            open_default_browser(APP_URL)
            _msg("NEXUS", f"Не удалось получить код привязки.\n\n{e}", 16)
            return 1

        copy_to_clipboard(user_code)
        open_default_browser(f"{APP_URL}/device?code={user_code}")

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
            log("poll_for_token …")
            token = poll_for_token(sess, request_id)
            save_token(token)
            log("poll_for_token ok")
        except Exception as e:
            log_exc("poll_for_token", e)
            _msg("NEXUS", f"Привязка не завершена.\n\n{e}", 48)
            return 1

    log("check_access …")
    ok, ends_at = check_access(sess, token)
    log(f"check_access ok={ok} ends_at={ends_at!r}")
    if not ok:
        text = "Подписка не активна или закончилась."
        if ends_at:
            text += f"\nДоступ был до: {ends_at}"
        _msg("NEXUS", text, 48)
        return 2

    log("launch_payload …")
    launched, details = launch_payload()
    log(f"launch_payload launched={launched} details={details[:200]!r}")
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
    try:
        code = main()
        log(f"exit {code}")
    except Exception as e:
        log_exc("fatal", e)
        _msg(
            "NEXUS",
            f"Критическая ошибка:\n{e}\n\nЛог:\n{LOG_PATH}",
            16,
        )
        code = 1
    raise SystemExit(code)


import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import requests
import ctypes


CLIENT_VERSION = os.environ.get("NEXUS_CLIENT_VERSION", "2026-04-13")
LOG_PATH = Path(os.environ.get("APPDATA", ".")) / "Nexus" / "nexus_client.log"

# Старый дефолт часто «умирает» на Railway (другой домен / сервис). URL задаётся при сборке (app_url.txt),
# переменной NEXUS_APP_URL или файлом nexus_app_url.txt рядом с exe.
_FALLBACK_APP_URL = "https://nexus-web-production-13f1.up.railway.app"


def _read_app_url_file(path: Path) -> str | None:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        for line in raw.splitlines():
            t = line.strip().lstrip("\ufeff")
            if not t or t.startswith("#"):
                continue
            if t.startswith("http://") or t.startswith("https://"):
                return t.rstrip("/")
    except Exception:
        pass
    return None


def resolve_app_url() -> str:
    env_u = (os.environ.get("NEXUS_APP_URL") or "").strip()
    if env_u:
        return env_u.rstrip("/")

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        u = _read_app_url_file(Path(meipass) / "app_url.txt")
        if u:
            return u

    try:
        u = _read_app_url_file(Path(sys.executable).resolve().parent / "nexus_app_url.txt")
        if u:
            return u
    except Exception:
        pass

    try:
        here = Path(__file__).resolve().parent
        u = _read_app_url_file(here / "app_url.txt")
        if u:
            return u
    except Exception:
        pass

    return _FALLBACK_APP_URL.rstrip("/")


APP_URL = resolve_app_url()


def _railway_dead_domain_hint(resp: requests.Response) -> str | None:
    try:
        j = resp.json()
        if isinstance(j, dict) and j.get("message") == "Application not found":
            return (
                "Этот адрес больше не ведёт в твоё приложение на Railway "
                "(домен сменился или сервис отключён).\n\n"
                f"Сейчас в клиенте: {APP_URL}\n\n"
                "Что сделать:\n"
                "1) Railway → веб-сервис → Settings → Networking — скопируй публичный URL.\n"
                "2) Создай файл nexus_app_url.txt в одной папке с Nexus.exe "
                "(одна строка: https://твой-сервис.up.railway.app) и запусти снова.\n"
                "3) Либо пересобери exe: задай NEXUS_APP_URL или web\\client\\railway_app_url.txt "
                "(см. railway_app_url.example)."
            )
    except Exception:
        pass
    return None

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


def _check_access_timeouts() -> tuple[float, float]:
    """Короче, чем общие HTTP — /api/client/me должен отвечать быстро; длинные 120s только тянут старт."""
    try:
        c = float(os.environ.get("NEXUS_ME_HTTP_CONNECT", "12"))
        r = float(os.environ.get("NEXUS_ME_HTTP_READ", "35"))
    except ValueError:
        c, r = 12.0, 35.0
    return (c, r)


def _check_access_max_attempts() -> int:
    try:
        n = int(os.environ.get("NEXUS_ME_HTTP_RETRIES", "5"), 10)
        return max(1, min(n, 10))
    except ValueError:
        return 5


def _device_request_timeout() -> tuple[float, float]:
    """Отдельные таймауты для /api/device/request — один read=120s даёт «тишину» в логе на минуты."""
    try:
        c = float(os.environ.get("NEXUS_DEVICE_HTTP_CONNECT", "20"))
        r = float(os.environ.get("NEXUS_DEVICE_HTTP_READ", "45"))
    except ValueError:
        c, r = 20.0, 45.0
    return (c, r)


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
        log(
            f"HTTP {method.upper()} attempt {attempt + 1}/{attempts} "
            f"timeout={timeout} → {url[:96]}"
        )
        try:
            r = sess.request(method.upper(), url, timeout=timeout, **kwargs)
            if r.status_code in (500, 502, 503, 504) and attempt < attempts - 1:
                log(f"HTTP retry status={r.status_code}, sleep…")
                time.sleep(min(2.0**attempt, 30.0))
                continue
            log(f"HTTP OK status={r.status_code}")
            return r
        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.SSLError,
        ) as e:
            last_exc = e
            log(f"HTTP attempt {attempt + 1} error: {type(e).__name__}: {e!s}")
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
    # Короче таймаут на одну попытку + меньше попыток, чем у «длинных» запросов — иначе первая попытка висит до 120s без новых строк в логе.
    try:
        dev_attempts = int(os.environ.get("NEXUS_DEVICE_HTTP_RETRIES", "6"), 10)
        dev_attempts = max(1, min(dev_attempts, 12))
    except ValueError:
        dev_attempts = 6
    r = _request_with_retries(
        sess,
        "post",
        f"{APP_URL}/api/device/request",
        timeout=_device_request_timeout(),
        max_attempts=dev_attempts,
    )
    if not r.ok:
        hint = _railway_dead_domain_hint(r)
        if hint:
            raise RuntimeError(hint)
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
    """Возвращает (has_access, subscription_ends_at_iso|None, http_status, api_error_text, account_email|None)."""
    r = _request_with_retries(
        sess,
        "get",
        f"{APP_URL}/api/client/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=_check_access_timeouts(),
        max_attempts=_check_access_max_attempts(),
    )
    if r.status_code != 200:
        err = ""
        try:
            j = r.json()
            if isinstance(j, dict) and j.get("error"):
                err = str(j["error"])
        except Exception:
            err = (r.text or "")[:300]
        return False, None, r.status_code, err, None

    d = r.json()
    if not isinstance(d, dict):
        return False, None, r.status_code, "bad_json", None
    email = d.get("email")
    acc_email = email if isinstance(email, str) and email else None
    return bool(d.get("hasAccess")), d.get("subscriptionEndsAt"), 200, "", acc_email


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


def prepare_bundled_runtime() -> tuple[bool, str]:
    """Копирует встроенные файлы в RUNTIME_DIR. Можно гонять параллельно с check_access."""
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return True, ""
    try:
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        for file_name in BUNDLED_RUNTIME_FILES:
            src = Path(meipass) / file_name
            if src.exists() and src.is_file():
                shutil.copy2(src, RUNTIME_DIR / file_name)
        return True, ""
    except Exception as e:
        return False, f"Не удалось распаковать встроенные файлы: {e}"


def launch_payload(*, assume_bundled_files_ready: bool = False) -> tuple[bool, str]:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        if not assume_bundled_files_ready:
            ok, err = prepare_bundled_runtime()
            if not ok:
                return False, err

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
    if APP_URL.rstrip("/") == _FALLBACK_APP_URL.rstrip("/"):
        log(
            "WARNING: URL сервера по умолчанию (часто устаревший). "
            "Задай nexus_app_url.txt рядом с exe или пересобери с актуальным Railway URL."
        )
    log(f"Лог: {LOG_PATH}")
    # Раньше здесь было блокирующее «Нажми OK» до любых запросов — убрано для мгновенного старта.
    if (
        os.environ.get("NEXUS_QUIET") != "1"
        and os.environ.get("NEXUS_SHOW_START_MSG") == "1"
    ):
        _msg(
            "NEXUS",
            f"Клиент {CLIENT_VERSION}\n\n"
            "Идёт проверка подписки и подготовка файлов.\n\n"
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

    log("check_access + prepare_bundled_runtime (parallel) …")
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_check = pool.submit(check_access, sess, token)
        fut_prep = pool.submit(prepare_bundled_runtime)
        ok, ends_at, http_st, api_err, acct_email = fut_check.result()
        prep_ok, prep_err = fut_prep.result()
    log(
        f"check_access ok={ok} ends_at={ends_at!r} http={http_st} "
        f"api_err={api_err!r} email={acct_email!r}"
    )
    log(f"prepare_bundled_runtime ok={prep_ok} err={prep_err!r}")
    if http_st != 200:
        text = (
            f"Токен клиента отклонён сервером (HTTP {http_st}).\n"
            f"{api_err}\n\n"
            "Часто это значит: сессия сброшена или привязка устарела.\n"
            f"Удали файл:\n{TOKEN_PATH}\n"
            "и запусти Nexus снова (заново привяжи устройство на сайте)."
        )
        _msg("NEXUS", text, 16)
        return 3

    if not ok:
        text = (
            "Для этого аккаунта на сервере нет активной подписки "
            "(дата окончания не задана или уже в прошлом).\n\n"
            "Проверь в кабинете на сайте, что статус ACTIVE и активирован промокод.\n"
            "Убедись, что в браузере ты вошёл в тот же аккаунт, который подтверждал привязку устройства."
        )
        if acct_email:
            text += f"\n\nАккаунт клиента: {acct_email}"
        if ends_at:
            text += f"\n\nДата в базе: {ends_at}"
        else:
            text += "\n\nВ базе нет даты подписки — активируй промокод в кабинете."
        text += f"\n\nОткрою страницу кабинета:\n{APP_URL}/account"
        open_default_browser(f"{APP_URL}/account")
        _msg("NEXUS", text, 48)
        return 2

    if not prep_ok:
        _msg("NEXUS", f"Подписка ок, но подготовка файлов не удалась.\n\n{prep_err}", 16)
        return 1

    log("launch_payload …")
    launched, details = launch_payload(assume_bundled_files_ready=True)
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


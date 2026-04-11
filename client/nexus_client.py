import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import requests
import ctypes

LaunchMode = Literal["auto", "cmd", "launcher"]

CLIENT_VERSION = os.environ.get("NEXUS_CLIENT_VERSION", "2026-04-11h")
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


def _nexus_launch_console_flags() -> int:
    """Один видимый терминал с логом Full Automation: из Nexus.exe открываем ровно одно CMD/консоль (CREATE_NEW_CONSOLE), без скрытых cmd и лишних окон."""
    if os.name != "nt":
        return 0
    try:
        if ctypes.windll.kernel32.GetConsoleWindow():
            return 0
    except Exception:
        pass
    return int(getattr(subprocess, "CREATE_NEW_CONSOLE", 0))


def _windows_system_cmd_exe() -> str:
    """Явный %SystemRoot%\\System32\\cmd.exe — не «через PATH», чтобы хост консоли был классический CMD."""
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "cmd.exe")


def _popen_argv_cmd_c_script(cmd_file: Path) -> list[str]:
    """cmd.exe /d /s /c с корректными кавычками, если в пути есть пробелы."""
    p = str(cmd_file.resolve())
    inner = '""' + p + '""' if " " in p else p
    return [_windows_system_cmd_exe(), "/d", "/s", "/c", inner]


def _popen_via_system_cmd(
    command_line: str,
    cwd: str,
    creationflags: int,
    *,
    env: dict[str, str] | None = None,
) -> subprocess.Popen:
    """Одна консоль: процесс верхнего уровня — всегда System32\\cmd.exe."""
    return subprocess.Popen(
        [_windows_system_cmd_exe(), "/d", "/s", "/c", command_line],
        cwd=cwd,
        creationflags=creationflags,
        stdin=subprocess.DEVNULL,
        env=env,
    )


def _child_env_with_python_path() -> dict[str, str]:
    """У frozen EXE часто урезан PATH — добавляем типичные каталоги Python."""
    env = os.environ.copy()
    env.setdefault("COMSPEC", _windows_system_cmd_exe())
    parts: list[str] = []
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        prog_py = os.path.join(local, "Programs", "Python")
        if os.path.isdir(prog_py):
            try:
                for name in sorted(os.listdir(prog_py), reverse=True):
                    d = os.path.join(prog_py, name)
                    if os.path.isdir(d):
                        parts.append(d)
                        sp = os.path.join(d, "Scripts")
                        if os.path.isdir(sp):
                            parts.append(sp)
            except OSError:
                pass
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    for ver in ("Python313", "Python312", "Python311", "Python310"):
        p = os.path.join(pf, ver)
        if os.path.isdir(p):
            parts.append(p)
            sp = os.path.join(p, "Scripts")
            if os.path.isdir(sp):
                parts.append(sp)
    if parts:
        env["PATH"] = os.pathsep.join(parts) + os.pathsep + env.get("PATH", "")
    return env


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


def launch_payload(
    *,
    assume_bundled_files_ready: bool = False,
    mode: LaunchMode = "auto",
) -> tuple[bool, str]:
    # Панель подписки могла остаться поверх — добиваем ещё раз перед лаунчером.
    close_panel_chromium_profile()

    allow_cmd = mode in ("auto", "cmd")
    allow_launcher = mode in ("auto", "launcher")

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        if not assume_bundled_files_ready:
            ok, err = prepare_bundled_runtime()
            if not ok:
                return False, err

        if allow_cmd:
            bundled_cmd = RUNTIME_DIR / "run_fsociety.cmd"
            if bundled_cmd.exists():
                try:
                    subprocess.Popen(
                        _popen_argv_cmd_c_script(bundled_cmd),
                        cwd=str(RUNTIME_DIR),
                        creationflags=_nexus_launch_console_flags(),
                        stdin=subprocess.DEVNULL,
                        env=_child_env_with_python_path(),
                    )
                    return True, f"Запущен {bundled_cmd.name} (встроенный пакет)"
                except Exception as e:
                    return False, f"Не удалось запустить встроенный {bundled_cmd.name}: {e}"

        if allow_launcher:
            bundled_py = RUNTIME_DIR / "launcher.py"
            _lf = _nexus_launch_console_flags()
            if bundled_py.exists():
                _env = _child_env_with_python_path()
                try:
                    cl = "py -3 " + subprocess.list2cmdline([str(bundled_py.resolve())])
                    _popen_via_system_cmd(cl, str(RUNTIME_DIR), _lf, env=_env)
                    return True, f"Запущен {bundled_py.name} (встроенный пакет)"
                except Exception:
                    try:
                        cl = "python " + subprocess.list2cmdline(
                            [str(bundled_py.resolve())]
                        )
                        _popen_via_system_cmd(cl, str(RUNTIME_DIR), _lf, env=_env)
                        return True, f"Запущен {bundled_py.name} (встроенный пакет)"
                    except Exception as e:
                        return False, f"Не удалось запустить встроенный {bundled_py.name}: {e}"

    if allow_cmd:
        cmd_file = find_existing_file("run_fsociety.cmd")
        if cmd_file:
            try:
                subprocess.Popen(
                    _popen_argv_cmd_c_script(cmd_file),
                    cwd=str(cmd_file.parent),
                    creationflags=_nexus_launch_console_flags(),
                    stdin=subprocess.DEVNULL,
                    env=_child_env_with_python_path(),
                )
                return True, f"Запущен {cmd_file.name}"
            except Exception as e:
                return False, f"Не удалось запустить {cmd_file.name}: {e}"

    if allow_launcher:
        py_file = find_existing_file("launcher.py")
        if py_file:
            _lf = _nexus_launch_console_flags()
            _env = _child_env_with_python_path()
            try:
                cl = "py -3 " + subprocess.list2cmdline([str(py_file.resolve())])
                _popen_via_system_cmd(cl, str(py_file.parent), _lf, env=_env)
                return True, f"Запущен {py_file.name}"
            except Exception:
                try:
                    cl = "python " + subprocess.list2cmdline([str(py_file.resolve())])
                    _popen_via_system_cmd(cl, str(py_file.parent), _lf, env=_env)
                    return True, f"Запущен {py_file.name}"
                except Exception as e:
                    return False, f"Не удалось запустить {py_file.name}: {e}"

    if mode == "cmd":
        return False, "run_fsociety.cmd не найден (ни во встроенном пакете, ни рядом с EXE)."
    if mode == "launcher":
        return False, "launcher.py не найден (ни во встроенном пакете, ни рядом с EXE)."
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


PANEL_APP_PROFILE_DIR = Path(os.environ.get("APPDATA", ".")) / "Nexus" / "panel_app_profile"
# Окно панели подписки (Brave --app=…): PID + порт локального сервера — чтобы гарантированно закрыть при старте лаунчера.
_PANEL_BROWSER_PROC: subprocess.Popen | None = None
_SUBSCRIPTION_PANEL_PORT: int | None = None
# Компактное окно по центру экрана (как у launcher.py после снятия kiosk).
PANEL_WINDOW_W = 880
PANEL_WINDOW_H = 540


def _panel_centered_window_args() -> tuple[int, int, int, int]:
    w, h, x, y = PANEL_WINDOW_W, PANEL_WINDOW_H, 80, 60
    if os.name == "nt":
        try:
            cx = ctypes.windll.user32.GetSystemMetrics(0)
            cy = ctypes.windll.user32.GetSystemMetrics(1)
            x = max(0, (cx - w) // 2)
            y = max(0, (cy - h) // 2)
        except Exception:
            pass
    return w, h, x, y

_BRAVE_PATHS_PANEL = [
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    os.path.expandvars(r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe"),
]
_CHROME_PATHS_PANEL = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
]
_EDGE_PATHS_PANEL = [
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def _find_chromium_for_app_mode() -> str | None:
    for group in (_BRAVE_PATHS_PANEL, _CHROME_PATHS_PANEL, _EDGE_PATHS_PANEL):
        for p in group:
            if os.path.isfile(p):
                return p
    return None


def open_client_panel_app_window(url: str) -> bool:
    """
    Окно без вкладок и без адресной строки (флаг --app), по смыслу как launcher.py.
    NEXUS_PANEL_FULL_BROWSER=1 — обычная вкладка через webbrowser.
    """
    global _PANEL_BROWSER_PROC
    _PANEL_BROWSER_PROC = None

    if os.environ.get("NEXUS_PANEL_FULL_BROWSER", "").strip().lower() in ("1", "true", "yes", "on"):
        try:
            webbrowser.open(url, new=2)
            return True
        except Exception:
            return False

    exe = _find_chromium_for_app_mode()
    if not exe:
        try:
            webbrowser.open(url, new=2)
            return True
        except Exception:
            return False

    try:
        PANEL_APP_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        profile = str(PANEL_APP_PROFILE_DIR.resolve())
        w, h, px, py = _panel_centered_window_args()
        _no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        _PANEL_BROWSER_PROC = subprocess.Popen(
            [
                exe,
                f"--user-data-dir={profile}",
                "--new-window",
                f"--window-size={w},{h}",
                f"--window-position={px},{py}",
                f"--app={url}",
            ],
            cwd=os.environ.get("SystemRoot", "C:\\Windows"),
            creationflags=_no_win,
        )
        log(f"panel app window pid={_PANEL_BROWSER_PROC.pid} {exe} --app=…")
        return True
    except Exception as e:
        log(f"panel app window failed: {e!r}, fallback webbrowser")
        _PANEL_BROWSER_PROC = None
        try:
            webbrowser.open(url, new=2)
            return True
        except Exception:
            return False


def clear_subscription_panel_port() -> None:
    global _SUBSCRIPTION_PANEL_PORT
    _SUBSCRIPTION_PANEL_PORT = None


def close_panel_chromium_profile() -> None:
    """
    Закрыть чёрное окно панели подписки: taskkill дерева PID, затем поиск по профилю и по URL 127.0.0.1:PORT.
    """
    global _PANEL_BROWSER_PROC
    port = _SUBSCRIPTION_PANEL_PORT
    proc = _PANEL_BROWSER_PROC
    _PANEL_BROWSER_PROC = None

    _no_win = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    if proc is not None:
        try:
            if proc.poll() is None:
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True,
                    timeout=18,
                    creationflags=_no_win,
                )
                log(f"panel: taskkill pid={proc.pid}")
        except Exception as e:
            log(f"panel taskkill: {e!r}")

    if os.name != "nt":
        return

    try:
        marker = str(PANEL_APP_PROFILE_DIR.resolve()).replace("\\", "\\\\")
        ps_cmd = (
            "$procs = Get-CimInstance Win32_Process | Where-Object { "
            "$_.CommandLine -and ($_.Name -match '^(brave|chrome|msedge)\\.exe$') "
            f"-and $_.CommandLine -like '*{marker}*' }}; "
            "foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps_cmd,
            ],
            capture_output=True,
            timeout=12,
            creationflags=_no_win,
        )
    except Exception as e:
        log(f"close_panel profile ps: {e!r}")

    if port is not None:
        try:
            port_esc = str(int(port))
            ps_port = (
                "$procs = Get-CimInstance Win32_Process | Where-Object { "
                "$_.CommandLine -and ($_.Name -match '^(brave|chrome|msedge)\\.exe$') "
                f"-and ($_.CommandLine -like '*127.0.0.1*{port_esc}*' -or $_.CommandLine -like '*localhost*{port_esc}*') }}; "
                "foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }"
            )
            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    ps_port,
                ],
                capture_output=True,
                timeout=12,
                creationflags=_no_win,
            )
            log(f"panel: killed by local port hint {port_esc}")
        except Exception as e:
            log(f"close_panel port ps: {e!r}")


def _env_no_gui() -> bool:
    # В PyInstaller EXE не уважаем NEXUS_NO_GUI: иначе случайная системная переменная
    # или старый тест отключают панель — остаётся только MessageBox и сразу run_fsociety.cmd.
    if getattr(sys, "frozen", False):
        return False
    return os.environ.get("NEXUS_NO_GUI", "").strip().lower() in ("1", "true", "yes", "on")


def _format_ru_subscription_ends(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        s = str(iso).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(iso)


# Ч/б веб-панель (как launcher.py): до вставки JSON-состояния и после.
_CLIENT_PANEL_HTML_PRE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEXUS · nexus-cursor</title>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{background:#000;color:#fff;overflow:hidden;font-family:'Rajdhani',sans-serif;font-weight:500;cursor:none}
canvas#bg{position:fixed;inset:0;z-index:0;display:block;width:100vw;height:100vh}
.scanlines{position:fixed;inset:0;pointer-events:none;z-index:5;opacity:.35;
  background:linear-gradient(rgba(255,255,255,0) 50%,rgba(0,0,0,.12) 50%);
  background-size:100% 3px;animation:scan 8s linear infinite}
@keyframes scan{from{background-position:0 0}to{background-position:0 100%}}
.vignette{position:fixed;inset:0;z-index:2;pointer-events:none;
  background:radial-gradient(ellipse at center,transparent 0%,rgba(0,0,0,.85) 100%)}
.noise{position:fixed;inset:-50%;z-index:3;pointer-events:none;opacity:.04;
  background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  animation:grain .8s steps(2) infinite}
@keyframes grain{0%,100%{transform:translate(0,0)}25%{transform:translate(-2%,2%)}50%{transform:translate(2%,-1%)}75%{transform:translate(-1%,-2%)}}
.cursor-dot{position:fixed;width:6px;height:6px;border-radius:50%;background:#fff;
  box-shadow:0 0 12px #fff,0 0 28px rgba(255,255,255,.35);pointer-events:none;z-index:9999;transform:translate(-50%,-50%)}
.ui{position:relative;z-index:10;min-height:100vh;display:flex;flex-direction:column;
  align-items:stretch;padding:14px 18px 20px}
.hdr{position:absolute;top:10px;right:14px;z-index:20;display:flex;justify-content:flex-end}
.center-stack{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:10px;width:100%;max-width:420px;margin:0 auto;padding:40px 8px 20px;box-sizing:border-box}
.btn-x{font-family:'Rajdhani',sans-serif;font-size:22px;font-weight:600;color:rgba(255,255,255,.35);background:none;border:none;
  cursor:none;padding:8px;transition:color .2s,text-shadow .2s}
.btn-x:hover{color:#fff;text-shadow:0 0 20px #fff}
.hero{text-align:center;margin:4px 0 10px}
.title{font-family:'Rajdhani',sans-serif;font-size:clamp(26px,6vw,40px);font-weight:700;letter-spacing:.28em;
  color:#fff;text-shadow:0 0 40px rgba(255,255,255,.25),0 0 80px rgba(255,255,255,.08);
  animation:titlePulse 4s ease-in-out infinite}
@keyframes titlePulse{0%,100%{opacity:1;filter:brightness(1)}50%{opacity:.92;filter:brightness(1.15)}}
.sub{font-size:12px;font-weight:600;letter-spacing:.42em;color:rgba(255,255,255,.4);margin-top:10px;font-family:'Rajdhani',sans-serif}
.card{width:100%;max-width:400px;border:1px solid rgba(255,255,255,.28);background:rgba(0,0,0,.55);
  backdrop-filter:blur(8px);padding:16px 18px;margin-bottom:0;animation:fadeUp .7s ease both}
@keyframes fadeUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
.row{margin-top:14px}
.lbl{font-size:10px;font-weight:600;letter-spacing:.22em;color:rgba(255,255,255,.4);text-transform:uppercase;margin-bottom:6px;font-family:'Rajdhani',sans-serif}
.val{font-family:'Rajdhani',sans-serif;font-size:15px;font-weight:500;color:#fff;word-break:break-all}
.divider{height:1px;background:linear-gradient(90deg,transparent,rgba(255,255,255,.25),transparent);margin:20px 0}
.product{border:1px solid rgba(255,255,255,.35);background:rgba(0,0,0,.4);padding:14px 16px;width:100%;max-width:400px;
  animation:fadeUp .85s ease .12s both}
.product-name{font-family:'Rajdhani',sans-serif;font-size:13px;font-weight:700;letter-spacing:.14em;color:#fff}
.product-desc{font-size:12px;font-weight:500;color:rgba(255,255,255,.5);margin-top:8px;line-height:1.5}
.actions{width:100%;max-width:400px;margin-top:8px;display:flex;flex-direction:column;gap:10px}
.btn{font-family:'Rajdhani',sans-serif;font-size:11px;font-weight:600;letter-spacing:.16em;padding:14px 20px;border:1px solid rgba(255,255,255,.45);
  background:rgba(0,0,0,.6);color:#fff;cursor:none;transition:background .2s,border-color .2s,box-shadow .2s,transform .15s}
.btn:hover{background:#fff;color:#000;border-color:#fff;box-shadow:0 0 24px rgba(255,255,255,.25)}
.btn:active{transform:scale(.98)}
.btn-primary{background:#fff;color:#000;border-color:#fff}
.btn-primary:hover{background:#000;color:#fff;border-color:#fff;box-shadow:0 0 32px rgba(255,255,255,.3)}
.btn-primary:disabled{opacity:.35;cursor:not-allowed;box-shadow:none}
.btn-row{display:flex;gap:10px;flex-wrap:wrap}
.btn-row .btn{flex:1;min-width:140px}
.msg{margin-top:14px;font-size:13px;font-weight:500;color:rgba(255,255,255,.55);text-align:center;min-height:1.2em;font-family:'Rajdhani',sans-serif}
.hint{font-size:11px;font-weight:500;color:rgba(255,255,255,.35);text-align:center;margin-top:10px;max-width:380px;line-height:1.55;font-family:'Rajdhani',sans-serif}
</style>
</head>
<body>
<canvas id="bg" aria-hidden="true"></canvas>
<div class="vignette" aria-hidden="true"></div>
<div class="noise" aria-hidden="true"></div>
<div class="scanlines" aria-hidden="true"></div>
<div class="cursor-dot" id="dot" aria-hidden="true"></div>
<div class="ui">
  <div class="hdr">
    <button type="button" class="btn-x" id="btn-close" title="Выход">✕</button>
  </div>
  <div class="center-stack">
    <div class="hero">
      <div class="title">NEXUS</div>
      <div class="sub">NEXUS CURSOR · CLIENT</div>
    </div>
    <div class="card" id="card-sub">
      <div class="lbl">Статус</div>
      <div class="val" id="line-status">—</div>
      <div class="row"><div class="lbl">Аккаунт</div><div class="val" id="line-email">—</div></div>
      <div class="row"><div class="lbl">Действует до</div><div class="val" id="line-ends">—</div></div>
    </div>
    <div class="product" id="product-box">
      <div class="product-name">nexus-cursor</div>
      <div class="product-desc">Веб-панель и сценарии NEXUS для Cursor — тот же стиль, что и у launcher.py.</div>
    </div>
    <div class="actions">
      <button type="button" class="btn btn-primary" id="btn-launch">ЗАПУСТИТЬ NEXUS-CURSOR</button>
      <div class="btn-row">
        <button type="button" class="btn" id="btn-account">КАБИНЕТ</button>
        <button type="button" class="btn" id="btn-exit">ВЫХОД</button>
      </div>
      <div class="msg" id="msg"></div>
    </div>
    <p class="hint" id="hint"></p>
  </div>
</div>
<script type="application/json" id="nx-s">"""

_CLIENT_PANEL_HTML_POST = r"""</script>
<script>
(function(){
const raw=document.getElementById('nx-s').textContent;
let S=JSON.parse(raw);
const $=id=>document.getElementById(id);
$('line-email').textContent=S.email||'—';
$('line-ends').textContent=S.endsAt||'—';
$('line-status').textContent=S.hasAccess?'●  ПОДПИСКА АКТИВНА':'○  НЕТ ДОСТУПА';
const btnLaunch=$('btn-launch');
btnLaunch.disabled=!S.hasAccess;
btnLaunch.setAttribute('aria-disabled',S.hasAccess?'false':'true');
btnLaunch.title=S.hasAccess?'':'Нет активной подписки — запуск недоступен';
$('hint').textContent=S.hasAccess?'':'Подписка не активна или истекла. Активируй промокод в кабинете или войди в тот же аккаунт, что привязывал устройство. Запуск возможен только при активной подписке.';

const dot=$('dot');
document.addEventListener('mousemove',e=>{if(dot){dot.style.left=e.clientX+'px';dot.style.top=e.clientY+'px';}});

const cv=$('bg');
const ctx=cv.getContext('2d');
let W=0,H=0,fontSize=15,drops=[],mouseX=-1e3,mouseY=-1e3;
const chars='0101100110011010'.split('');
function resize(){
  W=cv.width=innerWidth;H=cv.height=innerHeight;
  const n=Math.ceil(W/fontSize)+2;
  drops=[];for(let i=0;i<n;i++)drops[i]=Math.random()*-80;
}
function frame(){
  ctx.fillStyle='rgba(0,0,0,.11)';
  ctx.fillRect(0,0,W,H);
  ctx.font=fontSize+'px monospace';
  for(let i=0;i<drops.length;i++){
    const x=i*fontSize,y=drops[i]*fontSize;
    const dx=x-mouseX,dy=y-mouseY,d=Math.sqrt(dx*dx+dy*dy);
    if(d<140){ctx.fillStyle=`rgba(255,255,255,${1-d/140})`;ctx.shadowBlur=10;ctx.shadowColor='#fff';}
    else{ctx.fillStyle='rgba(90,90,90,.28)';ctx.shadowBlur=0;}
    ctx.fillText(chars[(Math.random()*chars.length)|0],x,y);
    if(y>H&&Math.random()>.97)drops[i]=0;
    drops[i]+=.85;
  }
}
addEventListener('resize',resize);
addEventListener('mousemove',e=>{mouseX=e.clientX;mouseY=e.clientY;});
addEventListener('mouseleave',()=>{mouseX=-1e3;mouseY=-1e3;});
resize();
(function loop(){frame();requestAnimationFrame(loop);})();

function post(path,cb){
  fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'})
    .then(r=>r.json()).then(d=>cb&&cb(d)).catch(()=>cb&&cb({ok:false,error:'network'}));
}
btnLaunch.addEventListener('click',()=>{
  if(!S.hasAccess){$('msg').textContent='Нет доступа: сначала активируй подписку.';return;}
  $('msg').textContent='Запуск…';
  post('/launch',d=>{$('msg').textContent=d.ok?'Готово. Можно закрыть вкладку.':('Ошибка: '+(d.error||''));});
});
$('btn-account').addEventListener('click',()=>{window.open(S.accountUrl,'_blank','noopener,noreferrer');});
$('btn-exit').addEventListener('click',()=>{post('/exit');});
$('btn-close').addEventListener('click',()=>{post('/exit');});
addEventListener('beforeunload',()=>{try{navigator.sendBeacon('/bye','');}catch(e){}});
async function pollSubscription(){
  try{
    const r=await fetch('/status');
    if(!r.ok)return;
    const d=await r.json();
    if(!d||!d.ok)return;
    S.hasAccess=!!d.hasAccess;
    if(d.email!==undefined&&d.email!=='')S.email=d.email;
    if(d.endsAt!==undefined)S.endsAt=d.endsAt;
    $('line-email').textContent=S.email||'—';
    $('line-ends').textContent=S.endsAt||'—';
    $('line-status').textContent=S.hasAccess?'●  ПОДПИСКА АКТИВНА':'○  НЕТ ДОСТУПА';
    btnLaunch.disabled=!S.hasAccess;
    btnLaunch.setAttribute('aria-disabled',S.hasAccess?'false':'true');
    btnLaunch.title=S.hasAccess?'':'Нет активной подписки — запуск недоступен';
    $('hint').textContent=S.hasAccess?'':'Подписка не активна или истекла. Активируй промокод в кабинете или войди в тот же аккаунт, что привязывал устройство. Запуск возможен только при активной подписке.';
  }catch(e){}
}
setInterval(pollSubscription,20000);
pollSubscription();
})();
</script>
</body>
</html>"""


def show_nexus_bw_panel(
    *,
    has_access: bool,
    account_email: str | None,
    subscription_ends_at_iso: str | None,
    app_url: str,
    poll_sess: requests.Session | None = None,
    poll_token: str | None = None,
) -> LaunchMode | None:
    """
    Панель в браузере (localhost), в духе launcher.py: матрица, scanlines, ч/б.
    Один сценарий «nexus-cursor» → launcher.py. None — выход без запуска.
    При poll_sess + poll_token — GET /status опрашивает сервер; /launch проверяет подписку снова.
    """
    state = {
        "hasAccess": bool(has_access),
        "email": account_email or "",
        "endsAt": _format_ru_subscription_ends(subscription_ends_at_iso),
        "accountUrl": f"{app_url.rstrip('/')}/account",
    }
    blob = json.dumps(state, ensure_ascii=False).replace("<", "\\u003c")
    page = (_CLIENT_PANEL_HTML_PRE + blob + _CLIENT_PANEL_HTML_POST).encode("utf-8")

    result: list[LaunchMode | None] = [None]
    done = threading.Event()
    server_box: list[http.server.HTTPServer] = []
    poll_lock = threading.Lock()

    def schedule_shutdown() -> None:
        def _q() -> None:
            time.sleep(0.08)
            try:
                server_box[0].shutdown()
            except Exception:
                pass

        threading.Thread(target=_q, daemon=True).start()

    class PanelHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass

        def _json(self, code: int, d: dict[str, Any]) -> None:
            b = json.dumps(d, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(b)

        def _drain_body(self) -> None:
            n = int(self.headers.get("Content-Length", "0") or 0)
            if n > 0:
                self.rfile.read(min(n, 65536))

        def do_GET(self) -> None:
            path = self.path.split("?", 1)[0]
            if path == "/status":
                if poll_sess is not None and poll_token:
                    with poll_lock:
                        ok_live, ends_live, http_st, _, em_live = check_access(
                            poll_sess, poll_token
                        )
                    live_ok = bool(ok_live) and http_st == 200
                    ends_fmt = _format_ru_subscription_ends(
                        ends_live if isinstance(ends_live, str) else None
                    )
                    self._json(
                        200,
                        {
                            "ok": True,
                            "live": True,
                            "hasAccess": live_ok,
                            "email": (em_live or account_email or ""),
                            "endsAt": ends_fmt,
                        },
                    )
                else:
                    self._json(
                        200,
                        {
                            "ok": True,
                            "live": False,
                            "hasAccess": bool(has_access),
                            "email": account_email or "",
                            "endsAt": _format_ru_subscription_ends(subscription_ends_at_iso),
                        },
                    )
                return
            if path == "/" or path.startswith("/?"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(page)
                return
            if path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            self.send_error(404)

        def do_POST(self) -> None:
            self._drain_body()
            path = self.path.split("?", 1)[0]
            if path == "/launch":
                effective = has_access
                if poll_sess is not None and poll_token:
                    with poll_lock:
                        ok_live, _, http_st, _, _ = check_access(poll_sess, poll_token)
                    effective = bool(ok_live) and http_st == 200
                if not effective:
                    self._json(403, {"ok": False, "error": "no_access"})
                    return
                result[0] = "launcher"
                if not done.is_set():
                    done.set()
                    schedule_shutdown()
                self._json(200, {"ok": True})
                return
            if path == "/exit":
                if result[0] != "launcher":
                    result[0] = None
                if not done.is_set():
                    done.set()
                    schedule_shutdown()
                self._json(200, {"ok": True})
                return
            if path == "/bye":
                if not done.is_set():
                    done.set()
                    schedule_shutdown()
                self._json(200, {"ok": True})
                return
            self._json(404, {"ok": False, "error": "not_found"})

    server = http.server.HTTPServer(("127.0.0.1", 0), PanelHandler)
    server_box.append(server)
    port = server.server_address[1]
    log(f"NEXUS client panel: http://127.0.0.1:{port}/")

    global _SUBSCRIPTION_PANEL_PORT
    _SUBSCRIPTION_PANEL_PORT = port

    th = threading.Thread(target=server.serve_forever, daemon=True)
    th.start()
    panel_url = f"http://127.0.0.1:{port}/"
    open_client_panel_app_window(panel_url)

    done.wait()
    try:
        server.shutdown()
    except Exception:
        pass
    try:
        server.server_close()
    except Exception:
        pass
    th.join(timeout=3.0)
    close_panel_chromium_profile()
    if result[0] is None:
        clear_subscription_panel_port()
    return result[0]


def main():
    log(f"=== start v{CLIENT_VERSION} ===")
    log(f"APP_URL={APP_URL}")
    if APP_URL.rstrip("/") == _FALLBACK_APP_URL.rstrip("/"):
        log(
            "WARNING: URL сервера по умолчанию (часто устаревший). "
            "Задай nexus_app_url.txt рядом с exe или пересобери с актуальным Railway URL."
        )
    log(f"Лог: {LOG_PATH}")
    if getattr(sys, "frozen", False):
        nog = (os.environ.get("NEXUS_NO_GUI") or "").strip()
        if nog:
            log(
                "EXE: NEXUS_NO_GUI в среде игнорируется — всегда показываем веб-панель "
                f"(в среде было: {nog!r})."
            )
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
        if _env_no_gui():
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
        else:
            show_nexus_bw_panel(
                has_access=False,
                account_email=acct_email,
                subscription_ends_at_iso=ends_at if isinstance(ends_at, str) else None,
                app_url=APP_URL,
                poll_sess=sess,
                poll_token=token,
            )
        return 2

    if not prep_ok:
        _msg("NEXUS", f"Подписка ок, но подготовка файлов не удалась.\n\n{prep_err}", 16)
        return 1

    launch_mode: LaunchMode | None
    if _env_no_gui():
        launch_mode = "launcher"
    else:
        ends_iso = ends_at if isinstance(ends_at, str) else None
        launch_mode = show_nexus_bw_panel(
            has_access=True,
            account_email=acct_email,
            subscription_ends_at_iso=ends_iso,
            app_url=APP_URL,
            poll_sess=sess,
            poll_token=token,
        )

    if launch_mode is None:
        log("panel: выход без запуска")
        return 0

    log(f"launch_payload mode={launch_mode} …")
    launched, details = launch_payload(
        assume_bundled_files_ready=True,
        mode=launch_mode,
    )
    log(f"launch_payload launched={launched} details={details[:200]!r}")
    if launched:
        close_panel_chromium_profile()
        clear_subscription_panel_port()
        if _env_no_gui():
            _msg("NEXUS", f"Подписка активна.\n{details}", 64)
        else:
            _msg("NEXUS", f"Запущено.\n{details}", 64)
        return 0

    clear_subscription_panel_port()
    _msg(
        "NEXUS",
        "Подписка активна, но запуск не выполнен.\n\n"
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


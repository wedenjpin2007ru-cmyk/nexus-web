import http.server
import threading
import subprocess
import webbrowser
import os
import json
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path
import imaplib
import email
from email.header import decode_header

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
CURSOR_SCRIPT   = os.path.join(BASE_DIR, "cursor.py")
MAILBOX_SCRIPT  = os.path.join(BASE_DIR, "mailbox_register.py")
ACCOUNTS_FILE   = os.path.join(BASE_DIR, "accounts.txt")
CURSOR_ACC_FILE = os.path.join(BASE_DIR, "cursor_accounts.txt")
CURSOR_LOGIN_STATE_FILE = os.path.join(BASE_DIR, "cursor_login_state.json")
BG_GIF_FILE = os.path.join(BASE_DIR, "1668637290_4554.gif")
KIOSK_PROFILE_DIR = os.path.join(BASE_DIR, ".nexus_kiosk_profile")
# Аккаунты до этой почты (включительно) в cursor_accounts.txt — считаем «уже заходили через NEXUS» при первой миграции.
CUTOFF_EMAIL_LOGGED_IN = "s35gn7peja@mailbox.org"
AUTOMATION_STATE_FILE = os.path.join(BASE_DIR, "automation_state.json")
FA_UI_STATE_FILE = os.path.join(BASE_DIR, "full_automation_ui_state.json")
CURSOR_EXE_PATH = r"D:\cursor\Cursor.exe"
PORT = 7331
DEFAULT_ACCOUNT_PASSWORD = os.environ.get("NEXUS_DEFAULT_PASSWORD", "Artemka228zxc")
# Окно UI: по центру экрана, компактнее чем полноэкранный kiosk.
NEXUS_UI_WIDTH = 1040
NEXUS_UI_HEIGHT = 720

# ═══════════════════════════════════════════════════════════════════════════
# SUBSCRIPTION STATUS (интеграция с nexus_client.py)
# ═══════════════════════════════════════════════════════════════════════════
_SUBSCRIPTION_STATUS = {
    "has_access": False,
    "email": None,
    "ends_at": None,
    "checked_at": None,
}

def load_subscription_status():
    """Загрузить статус подписки из токена nexus_client"""
    global _SUBSCRIPTION_STATUS
    try:
        token_path = Path(os.environ.get("APPDATA", ".")) / "Nexus" / "token.json"
        if not token_path.exists():
            return

        # Импортируем функции из nexus_client если доступны
        try:
            import requests
            sys.path.insert(0, BASE_DIR)
            from nexus_client import load_token, check_access, make_http_session, resolve_app_url

            token = load_token()
            if not token:
                return

            sess = make_http_session()
            app_url = resolve_app_url()

            has_access, ends_at, http_st, _, email = check_access(sess, token)

            if http_st == 200:
                _SUBSCRIPTION_STATUS = {
                    "has_access": bool(has_access),
                    "email": email,
                    "ends_at": ends_at,
                    "checked_at": datetime.now().isoformat(),
                }
        except Exception:
            pass
    except Exception:
        pass

def get_subscription_status():
    """Получить текущий статус подписки"""
    return dict(_SUBSCRIPTION_STATUS)

def format_subscription_date(iso_date):
    """Форматировать дату подписки"""
    if not iso_date:
        return "—"
    try:
        s = str(iso_date).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return str(iso_date)

# Full automation: одно консольное окно, прогресс 0–100, без отдельных CMD/PowerShell.
_fa_console_lock = threading.Lock()
_fa_console_allocated = False
# True только если консоль создана через AllocConsole (Nexus.exe). Нельзя FreeConsole у терминала пользователя (WT).
_fa_console_from_alloc = False
_fa_automation_lock = threading.Lock()
# Печать full automation в отдельное чёрное окно только при NEXUS_FA_LEGACY_CONSOLE=1
_FA_PRINT_TO_CONSOLE = False

# ── Лог / прогресс в панели лаунчера (без отдельных CMD) ───────────────────
_ACTIVITY_LOCK = threading.Lock()
_ACTIVITY_LINES: deque[str] = deque(maxlen=500)
_ACTIVITY_PCT = 0
_ACTIVITY_PHASE = ""
_ACTIVITY_BUSY = False
_ACTIVITY_TASK = ""
# Full automation / длинная цепочка — для UI «окна» прогресса (spawn_python_logged ставит busy)
_ACTIVITY_PIPELINE = False
# Шаги Full Automation для панели (как чеклист)
_ACTIVITY_FA_STEPS: list[dict[str, str]] = []
_FA_STEP_LABELS = (
    "1. PowerShell",
    "2. Mailbox.org (общий Brave)",
    "3. IMAP / ожидание письма",
    "4. Cursor в том же Brave",
    "5. Завершение",
)


def activity_set_progress(pct: int, phase: str) -> None:
    global _ACTIVITY_PCT, _ACTIVITY_PHASE
    pct = max(0, min(100, int(pct)))
    ph = (phase or "").replace("\r", " ").strip()[:220]
    with _ACTIVITY_LOCK:
        _ACTIVITY_PCT = pct
        _ACTIVITY_PHASE = ph


def activity_append(msg: str, source: str = "") -> None:
    global _ACTIVITY_LINES
    t = (msg or "").replace("\r", " ").rstrip()
    if not t:
        return
    line = (f"[{source}] {t}" if source else t)[:2000]
    with _ACTIVITY_LOCK:
        _ACTIVITY_LINES.append(line)


def activity_set_busy(busy: bool, task: str = "") -> None:
    global _ACTIVITY_BUSY, _ACTIVITY_TASK
    with _ACTIVITY_LOCK:
        _ACTIVITY_BUSY = bool(busy)
        _ACTIVITY_TASK = (task or "")[:120]


def activity_set_pipeline(on: bool) -> None:
    global _ACTIVITY_PIPELINE
    with _ACTIVITY_LOCK:
        _ACTIVITY_PIPELINE = bool(on)


def activity_reset_fa_steps() -> None:
    global _ACTIVITY_FA_STEPS
    with _ACTIVITY_LOCK:
        _ACTIVITY_FA_STEPS = [
            {"label": L, "status": "pending"} for L in _FA_STEP_LABELS
        ]


def activity_clear_fa_steps() -> None:
    global _ACTIVITY_FA_STEPS
    with _ACTIVITY_LOCK:
        _ACTIVITY_FA_STEPS = []


def activity_fa_set_step(idx: int, status: str) -> None:
    """status: pending | active | done | error"""
    st = (status or "pending").strip().lower()
    with _ACTIVITY_LOCK:
        for i, row in enumerate(_ACTIVITY_FA_STEPS):
            if i < idx:
                if row["status"] != "error":
                    row["status"] = "done"
            elif i == idx:
                row["status"] = st
            elif i > idx and row["status"] == "active":
                row["status"] = "pending"


def activity_fa_mark_error() -> None:
    with _ACTIVITY_LOCK:
        for row in _ACTIVITY_FA_STEPS:
            if row["status"] == "active":
                row["status"] = "error"
                break


def activity_snapshot() -> dict:
    with _ACTIVITY_LOCK:
        return {
            "ok": True,
            "pct": _ACTIVITY_PCT,
            "phase": _ACTIVITY_PHASE,
            "busy": _ACTIVITY_BUSY,
            "pipeline": _ACTIVITY_PIPELINE,
            "task": _ACTIVITY_TASK,
            "lines": list(_ACTIVITY_LINES),
            "steps": [dict(x) for x in _ACTIVITY_FA_STEPS],
        }


def _subprocess_capture_kw() -> dict:
    kw: dict = dict(
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    if os.name == "nt":
        kw["creationflags"] = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return kw


def _start_stdout_drain(proc: subprocess.Popen, tag: str) -> threading.Thread:
    def _run() -> None:
        out = proc.stdout
        if not out:
            return
        try:
            for line in iter(out.readline, ""):
                activity_append(line.rstrip("\n\r"), tag)
        except Exception:
            pass
        try:
            out.close()
        except Exception:
            pass

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    return th


def _argv_python_force_unbuffered(argv: list) -> list:
    """Вставить -u после python.exe, чтобы строки шли в лайв (не ждать конца процесса)."""
    if not argv or len(argv) < 2:
        return argv
    if argv[1] == "-u":
        return argv
    exe = os.path.basename(str(argv[0])).lower()
    if exe in ("python.exe", "python3.exe", "pythonw.exe"):
        return [argv[0], "-u"] + list(argv[1:])
    return argv


def resolve_child_python_exe() -> str:
    """Тот же python.exe, что и лаунчер — без py.exe (лишние окна CMD на части систем)."""
    ex = (sys.executable or "").strip()
    if ex and os.path.isfile(ex):
        base = os.path.basename(ex).lower()
        if base == "python.exe":
            return ex
        if base == "pythonw.exe":
            cand = os.path.join(os.path.dirname(ex), "python.exe")
            if os.path.isfile(cand):
                return cand
    return get_console_python_exe()


def _normalize_subprocess_python_argv(argv: list) -> list:
    av = list(argv)
    if not av:
        return av
    b = os.path.basename(str(av[0])).lower()
    if b in ("py.exe", "py3.exe"):
        av[0] = resolve_child_python_exe()
    return _argv_python_force_unbuffered(av)


def spawn_python_logged(argv: list, cwd: str, env: dict, task_name: str) -> None:
    """Запуск Python-скрипта без окна CMD; вывод — в панель ACTIVITY."""

    def _worker() -> None:
        activity_set_busy(True, task_name)
        try:
            activity_append(f"—— старт: {task_name} ——", "run")
            cmd = _normalize_subprocess_python_argv(list(argv))
            kw = dict(_subprocess_capture_kw(), cwd=cwd, env=env)
            proc = subprocess.Popen(cmd, **kw)
            th = _start_stdout_drain(proc, task_name)
            rc = int(proc.wait() or 0)
            th.join(timeout=5.0)
            activity_append(f"готово, код выхода {rc}", task_name)
        except Exception as e:
            activity_append(str(e), task_name)
        finally:
            activity_set_busy(False, "")

    threading.Thread(target=_worker, daemon=True).start()


def _fa_attach_console():
    """Подключить консоль: существующий терминал или новое окно (после отвязки лаунчера)."""
    global _fa_console_allocated, _fa_console_from_alloc
    if os.name != "nt":
        return False
    with _fa_console_lock:
        if _fa_console_allocated:
            return True
        try:
            import ctypes

            k32 = ctypes.windll.kernel32
            if k32.GetConsoleWindow():
                _fa_console_allocated = True
                _fa_console_from_alloc = False
                return True
            if not k32.AllocConsole():
                return False
            conout = open(
                "CONOUT$",
                "w",
                encoding="utf-8",
                errors="replace",
                newline="",
            )
            sys.stdout = conout
            sys.stderr = conout
            _fa_console_allocated = True
            _fa_console_from_alloc = True
            return True
        except Exception:
            return False


def _fa_release_console():
    """Убрать только консоль, созданную AllocConsole; вкладку Windows Terminal не трогаем."""
    global _fa_console_allocated, _fa_console_from_alloc
    if os.name != "nt":
        return
    with _fa_console_lock:
        if not _fa_console_allocated:
            return
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        _fa_console_allocated = False
        if _fa_console_from_alloc:
            try:
                import ctypes

                ctypes.windll.kernel32.FreeConsole()
            except Exception:
                pass
            _fa_console_from_alloc = False
            try:
                dn = open(os.devnull, "w", encoding="utf-8")
                sys.stdout = dn
                sys.stderr = dn
            except Exception:
                pass


def _fa_bar(pct: int) -> str:
    w = 16
    f = max(0, min(w, int(round(w * pct / 100.0))))
    return "[" + "#" * f + "." * (w - f) + "]"


def _fa_progress(pct: int, message: str) -> None:
    """Прогресс 0–100% в панели лаунчера; в консоль — только legacy-режим."""
    pct = max(0, min(100, int(pct)))
    msg = (message or "").replace("\r", " ").replace("\n", " ")[:88]
    activity_set_progress(pct, msg)
    activity_append(f"{pct}% — {msg}", "auto")
    if not _FA_PRINT_TO_CONSOLE:
        return
    try:
        sys.stdout.write(f"\n  {_fa_bar(pct)} {pct:3d}%  {msg}\n")
        sys.stdout.flush()
    except Exception:
        pass


def _fa_progress_ln(pct: int, message: str) -> None:
    _fa_progress(pct, message)


_fa_live_line_active = False


def _fa_progress_live(pct: int, message: str) -> None:
    """Живой прогресс: в UI через activity; в консоль — только legacy."""
    global _fa_live_line_active
    pct = max(0, min(100, int(pct)))
    msg = (message or "").replace("\r", " ").replace("\n", " ")[:62]
    activity_set_progress(pct, msg)
    _fa_live_line_active = True
    if not _FA_PRINT_TO_CONSOLE:
        return
    line = f"  {_fa_bar(pct)} {pct:3d}%  {msg}"
    try:
        sys.stdout.write("\r" + line.ljust(88)[:88])
        sys.stdout.flush()
    except Exception:
        pass


def _fa_progress_live_end() -> None:
    global _fa_live_line_active
    if _FA_PRINT_TO_CONSOLE and _fa_live_line_active:
        try:
            sys.stdout.write("\n")
            sys.stdout.flush()
        except Exception:
            pass
    _fa_live_line_active = False


def _fa_report_banner():
    global _FA_PRINT_TO_CONSOLE
    activity_append("NEXUS — цепочка Mailbox + Cursor (лог ниже, без окон CMD)", "auto")
    activity_append(
        "Этапы: PS → почта → пауза IMAP → Cursor. Прогресс и вывод скриптов — в этой панели.",
        "auto",
    )
    if not _FA_PRINT_TO_CONSOLE:
        return
    try:
        sys.stdout.write(
            "\n"
            + "=" * 60
            + "\n  NEXUS — один терминал до конца (Mailbox + Cursor)\n"
            + "=" * 60
            + "\n\n"
            "  Пока не дойдет до 100%, окно не завершает цепочку.\n"
            "  Отдельные CMD для почты/Cursor не открываются — всё здесь.\n\n"
            "  Карта прогресса:\n"
            "    0–22%   PowerShell (если есть сценарий)\n"
            "   22–58%   Регистрация Mailbox.org (один Brave на всю цепочку до Cursor)\n"
            "   58–74%   Пауза IMAP + сохранение состояния\n"
            "   74–99%   Регистрация Cursor — ждём ПОЛНОГО завершения скрипта\n"
            "      100%   Итог; при отдельном чёрном окне оно закроется само\n"
            + "\n"
        )
        sys.stdout.flush()
    except Exception:
        pass


def _fa_child_env(extra=None):
    """Окружение для mailbox_register / cursor: единый отчёт, без спама Node DEP*."""
    env = os.environ.copy()
    env["NEXUS_UNIFIED_REPORT"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    no = (env.get("NODE_OPTIONS") or "").strip()
    if "--no-deprecation" not in no:
        env["NODE_OPTIONS"] = f"{no} --no-deprecation".strip()
    if extra:
        env.update(extra)
    return env


def _fa_shared_brave_env():
    """
    Один Brave на всю цепочку FA: тот же user-data-dir и CDP-порт для mailbox и Cursor.
    (Иначе почта и Cursor поднимают разные окна Brave.)
    """
    local = os.environ.get("LOCALAPPDATA") or os.path.join(
        os.path.expanduser("~"), "AppData", "Local"
    )
    profile = os.path.join(local, "NexusFA", "BraveShared")
    try:
        os.makedirs(profile, exist_ok=True)
    except OSError:
        pass
    return {
        "NEXUS_SHARED_BRAVE": "1",
        "NEXUS_BRAVE_CDP_PORT": "9228",
        "NEXUS_BRAVE_USER_DATA_DIR": profile,
    }


def run_powershell_in_automation_console(script_text: str) -> int:
    """
    PowerShell в текущей консоли (без второго окна). Без UAC — если нужен admin, запусти Nexus.exe от администратора
    или задай NEXUS_FA_ELEVATED_PS=1 (откроется отдельное окно с RunAs).
    """
    tmp_ps = os.path.join(
        os.environ.get("TEMP", "C:/Windows/Temp"), "nexus_full_automation.ps1"
    )
    with open(tmp_ps, "w", encoding="utf-8-sig") as f:
        f.write(script_text)
    elevated = os.getenv("NEXUS_FA_ELEVATED_PS", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    if elevated and os.name == "nt":
        import ctypes

        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            "powershell.exe",
            f'-ExecutionPolicy Bypass -File "{tmp_ps}"',
            None,
            1,
        )
        return 0
    env_ps = os.environ.copy()
    env_ps.setdefault("PYTHONUNBUFFERED", "1")
    kw = dict(
        _subprocess_capture_kw(),
        cwd=BASE_DIR,
        env=env_ps,
    )
    proc = subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            tmp_ps,
        ],
        **kw,
    )
    th = _start_stdout_drain(proc, "ps")
    rc = int(proc.wait() or 0)
    th.join(timeout=8.0)
    return rc


def _win_has_console_hwnd():
    if os.name != "nt":
        return False
    try:
        import ctypes

        return bool(ctypes.windll.kernel32.GetConsoleWindow())
    except Exception:
        return False


def _detach_launcher_console():
    """
    Без лишнего чёрного окна при двойном клике: глушим вывод и FreeConsole.
    Если лаунчер уже в терминале пользователя — не отцепляемся: full automation и mailbox/cursor в одной вкладке.
    Отладка: NEXUS_KEEP_CONSOLE=1
    """
    if os.getenv("NEXUS_KEEP_CONSOLE", "").strip().lower() in ("1", "true", "yes", "on"):
        return
    if _win_has_console_hwnd():
        return
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    try:
        dn = open(os.devnull, "w", encoding="utf-8")
        sys.stdout = dn
        sys.stderr = dn
    except Exception:
        pass
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.kernel32.FreeConsole()
        except Exception:
            pass


def centered_window_geometry(width: int, height: int) -> tuple[int, int, int, int]:
    """(width, height, x, y) для --window-size / --window-position (центр монитора)."""
    import ctypes as _ctypes

    x, y = 80, 60
    if os.name == "nt":
        try:
            cx = _ctypes.windll.user32.GetSystemMetrics(0)
            cy = _ctypes.windll.user32.GetSystemMetrics(1)
            x = max(0, (cx - width) // 2)
            y = max(0, (cy - height) // 2)
        except Exception:
            pass
    return width, height, x, y

BRAVE_PATHS = [
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Users\developer\AppData\Local\BraveSoftware\Brave-Browser\Application\brave.exe",
]

def find_brave():
    return next((p for p in BRAVE_PATHS if os.path.exists(p)), None)

def load_accounts(filepath):
    accounts = []
    if not os.path.exists(filepath):
        return accounts
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            parts = {}
            for chunk in line.split(' | '):
                if ': ' in chunk:
                    k, v = chunk.split(': ', 1)
                    parts[k.strip()] = v.strip()
            if 'Email' in parts:
                accounts.append(parts)
    return accounts

def add_log(message, level='INFO'):
    # Simple console logger for backend actions.
    print(f"[{level}] {message}")

def save_automation_state(email_addr, password):
    state = {
        "email": email_addr or "",
        "mail_password": password or "",
        "cursor_password": password or "",
        "updated_at": int(time.time()),
    }
    with open(AUTOMATION_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def launch_cursor_app():
    if os.path.exists(CURSOR_EXE_PATH):
        kw = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.name == "nt":
            kw["creationflags"] = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
        subprocess.Popen([CURSOR_EXE_PATH], **kw)
        return True
    return False

def get_console_python_exe():
    """
    Возвращает интерпретатор для automation.
    Приоритет:
      1) интерпретатор, который отдает `py` (обычно туда ставят зависимости),
      2) python.exe рядом с pythonw.exe,
      3) текущий sys.executable.
    """
    try:
        _py_kw = dict(stderr=subprocess.STDOUT, text=True, timeout=5)
        if os.name == "nt":
            _py_kw["creationflags"] = subprocess.CREATE_NO_WINDOW
        out = subprocess.check_output(
            ["py", "-c", "import sys;print(sys.executable)"],
            **_py_kw,
        ).strip()
        if out and os.path.exists(out):
            return out
    except Exception:
        pass

    exe = sys.executable or "python"
    if os.path.basename(exe).lower() == "pythonw.exe":
        candidate = os.path.join(os.path.dirname(exe), "python.exe")
        if os.path.exists(candidate):
            return candidate
    return exe


def _fa_resolve_python_exe():
    """Алиас для Full Automation — см. resolve_child_python_exe."""
    return resolve_child_python_exe()


def launch_admin_powershell_detached():
    """Отдельный процесс от лаунчера — при закрытии NEXUS окно PowerShell не гаснет."""
    import ctypes
    ctypes.windll.shell32.ShellExecuteW(
        None, 'runas', 'powershell.exe',
        '-NoExit -NoLogo',
        None, 1)

def launch_admin_powershell_with_script(script_text):
    """PowerShell Admin с выполнением переданного текста как .ps1 (файл во временной папке)."""
    import ctypes
    tmp_ps = os.path.join(os.environ.get('TEMP', 'C:/Windows/Temp'), 'nexus_full_automation.ps1')
    with open(tmp_ps, 'w', encoding='utf-8-sig') as f:
        f.write(script_text)
    ctypes.windll.shell32.ShellExecuteW(
        None, 'runas', 'powershell.exe',
        f'-NoExit -ExecutionPolicy Bypass -File "{tmp_ps}"',
        None, 1)

def load_fa_ui_state():
    default = {"ps_text": "", "hot_words": ""}
    if not os.path.exists(FA_UI_STATE_FILE):
        return dict(default)
    try:
        with open(FA_UI_STATE_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        pt = d.get("ps_text", "")
        hw = d.get("hot_words", "")
        return {
            "ps_text": pt if isinstance(pt, str) else "",
            "hot_words": hw if isinstance(hw, str) else "",
        }
    except Exception:
        return dict(default)

def save_fa_ui_state(ps_text, hot_words):
    with open(FA_UI_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(
            {"ps_text": ps_text or "", "hot_words": hot_words or ""},
            f,
            ensure_ascii=False,
            indent=2,
        )

def build_combined_ps_script(main_ps, hot_words):
    """Основной скрипт, затем блок «горячих слов» (как PS-код, выполняется после верхней части)."""
    main_ps = (main_ps or "").strip()
    hot_words = (hot_words or "").strip()
    if not hot_words:
        return main_ps
    sep = "\n\n# --- NEXUS: горячие слова (выполняются после основного скрипта) ---\n"
    if main_ps:
        return main_ps + sep + hot_words
    return hot_words

def build_ps_readhost_autoreply():
    """Автоответы для Read-Host внутри PowerShell-скрипта."""
    return r"""
# --- NEXUS: Read-Host auto-replies ---
try {
    if (-not (Get-Variable -Name "__nexus_original_read_host" -Scope Global -ErrorAction SilentlyContinue)) {
        $global:__nexus_original_read_host = ${function:Read-Host}
    }
    if (-not (Get-Variable -Name "__nexus_yes_index" -Scope Global -ErrorAction SilentlyContinue)) {
        $global:__nexus_yes_index = 0
    }
    function Global:Read-Host {
        param([Parameter(Position=0)][string]$Prompt)
        $p = [string]$Prompt
        if ($p -match "请输入选择" -or $p -match "\(1\s*或\s*2\)" -or $p -match "1\s*or\s*2") {
            return "2"
        }
        if ($p -match "yes/no" -or $p -match "y/n" -or $p -match "confirm" -or $p -match "继续" -or $p -match "确认") {
            $global:__nexus_yes_index++
            return "yes"
        }
        if ($p -match "(?i)login" -or $p -match "(?i)sign\s*in" -or $p -match "(?i)войти" -or $p -match "(?i)логин") {
            $global:__nexus_yes_index++
            return "yes"
        }
        return & $global:__nexus_original_read_host $Prompt
    }
} catch {}
"""

def run_full_automation(skip_powershell=False, ps_script='', hot_words=''):
    with _fa_automation_lock:
        _run_full_automation_body(skip_powershell, ps_script, hot_words)


def _run_full_automation_body(skip_powershell=False, ps_script='', hot_words=''):
    global _FA_PRINT_TO_CONSOLE
    legacy = os.getenv("NEXUS_FA_LEGACY_CONSOLE", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    use_console = os.name == "nt" and legacy and _fa_attach_console()
    _FA_PRINT_TO_CONSOLE = bool(use_console)
    fa_used_alloc = _fa_console_from_alloc
    err_note = ""

    def _finish_ok():
        activity_append(
            "Итог: Mailbox и Cursor отработали — полный лог в панели ниже.",
            "auto",
        )
        if _FA_PRINT_TO_CONSOLE:
            try:
                sys.stdout.write(
                    "\n  ────────────────────────────────────────────────────────\n"
                    "  ИТОГ: Mailbox и Cursor отработали в ОДНОМ терминале (см. лог выше).\n"
                    "  ────────────────────────────────────────────────────────\n"
                )
                sys.stdout.flush()
            except Exception:
                pass
        if fa_used_alloc:
            _fa_progress_ln(
                100,
                "Всё готово. Это окно само закроется через несколько секунд…",
            )
            time.sleep(5.0)
        else:
            _fa_progress_ln(
                100,
                "Всё готово."
                if not _FA_PRINT_TO_CONSOLE
                else "Всё готово. Закрой вкладку терминала сам, когда просмотришь лог.",
            )
            time.sleep(0.5 if not _FA_PRINT_TO_CONSOLE else 1.2)
        if use_console:
            _fa_release_console()

    def _finish_err(note: str):
        _fa_progress_ln(0, note or "Ошибка.")
        if use_console:
            time.sleep(8.0)
            _fa_release_console()
        elif not _FA_PRINT_TO_CONSOLE:
            time.sleep(0.4)

    try:
        activity_set_pipeline(True)
        add_log("Automation started", "INFO")
        activity_reset_fa_steps()
        activity_fa_set_step(0, "active")
        _fa_report_banner()
        _fa_progress(0, "Старт full automation")
        py_exe = _fa_resolve_python_exe()

        # 1) PowerShell в этой же консоли (без второго окна), если не пропущен и есть текст скрипта.
        if not skip_powershell:
            user_ps = build_combined_ps_script(ps_script, hot_words)
            if user_ps.strip():
                combined = build_ps_readhost_autoreply() + "\n\n" + user_ps
                _fa_progress(8, "Этап 1/4: PowerShell (ваш сценарий), вывод ниже")
                rc = run_powershell_in_automation_console(combined)
                add_log(f"PowerShell finished rc={rc}", "OK" if rc == 0 else "INFO")
                _fa_progress(22, "Этап 1/4: PowerShell завершён")
            else:
                add_log("PowerShell: пустой скрипт, шаг пропущен", "INFO")
                _fa_progress(22, "Этап 1/4: PowerShell пропущен (нет текста скрипта)")
        else:
            add_log("PowerShell step skipped (user closed dialog)", "INFO")
            _fa_progress(22, "Этап 1/4: PowerShell пропущен (выбор в UI)")

        activity_fa_set_step(0, "done")
        activity_fa_set_step(1, "active")

        # 2) Регистрация почты — тот же терминал, без нового CMD.
        if not os.path.exists(MAILBOX_SCRIPT):
            add_log("mailbox_register.py not found", "ERROR")
            err_note = "Нет mailbox_register.py"
            activity_fa_mark_error()
            _finish_err(err_note)
            return
        _fa_progress(
            28,
            "Этап 2/4: Mailbox.org — ниже лог скрипта (Brave + капча вручную при запросе)",
        )
        env_mb = _fa_child_env(
            {**_fa_shared_brave_env(), "NEXUS_ACCOUNTS_FILE": ACCOUNTS_FILE}
        )
        mailbox_kw = dict(
            _subprocess_capture_kw(),
            cwd=BASE_DIR,
            env=env_mb,
        )
        mailbox_proc = subprocess.Popen(
            _argv_python_force_unbuffered([py_exe, MAILBOX_SCRIPT, "--auto-close"]),
            **mailbox_kw,
        )
        _mb_drain = _start_stdout_drain(mailbox_proc, "mailbox")
        add_log("Mailbox registration launched", "OK")
        n_acc_before = len(load_accounts(ACCOUNTS_FILE))

        def _accounts_mtime():
            try:
                return os.path.getmtime(ACCOUNTS_FILE)
            except OSError:
                return 0.0

        mtime0 = _accounts_mtime()
        tick = 28
        mb_wait_start = time.time()
        while mailbox_proc.poll() is None:
            time.sleep(0.45)
            tick = min(52, tick + 1)
            elapsed = int(time.time() - mb_wait_start)
            _fa_progress_live(tick, f"Этап 2/4: почта… ~{elapsed}s")
        _fa_progress_live_end()
        mailbox_rc = int(mailbox_proc.wait() or 0)
        _mb_drain.join(timeout=8.0)
        if mailbox_rc != 0:
            add_log(f"mailbox_register exit {mailbox_rc}", "ERROR")
            activity_fa_mark_error()
            _finish_err(f"Регистрация почты завершилась с кодом {mailbox_rc}")
            return
        activity_fa_set_step(1, "done")
        activity_fa_set_step(2, "active")
        _fa_progress(55, "Этап 2/4: Mailbox.org — скрипт завершён, проверяем accounts.txt")
        deadline = time.time() + 180.0
        while time.time() < deadline:
            acc = load_accounts(ACCOUNTS_FILE)
            if len(acc) > n_acc_before or _accounts_mtime() > mtime0:
                break
            time.sleep(0.4)

        mailbox_accounts = load_accounts(ACCOUNTS_FILE)
        if not mailbox_accounts:
            add_log("No mailbox accounts found after registration", "ERROR")
            err_note = "Нет аккаунта почты после регистрации"
            activity_fa_mark_error()
            _finish_err(err_note)
            return
        latest_email = mailbox_accounts[-1].get("Email", "").strip()
        if not latest_email:
            add_log("Latest mailbox email is empty", "ERROR")
            err_note = "Пустой email в последней записи"
            activity_fa_mark_error()
            _finish_err(err_note)
            return

        _fa_progress(58, "Этап 3/4: пауза 12 с — синхронизация IMAP для кода Cursor")
        add_log("Pause 12s: mailbox IMAP / sync…", "INFO")
        for sec in range(12):
            time.sleep(1.0)
            _fa_progress_live(
                min(71, 58 + sec),
                f"Этап 3/4: IMAP… {sec + 1}/12 с",
            )
        _fa_progress_live_end()

        save_automation_state(latest_email, DEFAULT_ACCOUNT_PASSWORD)
        add_log(f"Saved automation state for {latest_email}", "OK")
        _fa_progress(72, "Состояние автоматизации сохранено")

        activity_fa_set_step(2, "done")
        activity_fa_set_step(3, "active")

        if not os.path.exists(CURSOR_SCRIPT):
            add_log("cursor.py not found", "ERROR")
            err_note = "Нет cursor.py"
            activity_fa_mark_error()
            _finish_err(err_note)
            return
        cursor_cmd = [
            py_exe,
            CURSOR_SCRIPT,
            "--action",
            "register",
            "--email",
            latest_email,
            "--cursor-pass",
            DEFAULT_ACCOUNT_PASSWORD,
            "--mail-pass",
            DEFAULT_ACCOUNT_PASSWORD,
        ]
        _fa_progress(
            74,
            f"Этап 4/4: Cursor — регистрация {latest_email} (ждём до конца)",
        )
        cur_kw = dict(
            _subprocess_capture_kw(),
            cwd=BASE_DIR,
            env=_fa_child_env(_fa_shared_brave_env()),
        )
        cur_proc = subprocess.Popen(
            _argv_python_force_unbuffered(cursor_cmd),
            **cur_kw,
        )
        _cur_drain = _start_stdout_drain(cur_proc, "cursor")
        cur_rc = int(cur_proc.wait() or 0)
        _cur_drain.join(timeout=8.0)
        add_log(
            f"Cursor registration finished rc={cur_rc} for {latest_email}",
            "OK" if cur_rc == 0 else "ERROR",
        )
        if cur_rc == 0:
            _fa_progress(99, "Этап 4/4: Cursor завершён успешно")
            activity_fa_set_step(3, "done")
            activity_fa_set_step(4, "done")
        else:
            activity_fa_set_step(3, "error")
            _fa_progress(
                99,
                f"Этап 4/4: Cursor завершился с кодом {cur_rc} — смотри сообщения выше",
            )

        if os.getenv("NEXUS_OPEN_CURSOR_AFTER_AUTO", "").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        ):
            if launch_cursor_app():
                add_log(f"Cursor app opened: {CURSOR_EXE_PATH}", "OK")
            else:
                add_log(f"Cursor app not found: {CURSOR_EXE_PATH}", "ERROR")

        _finish_ok()
    except Exception as e:
        add_log(f"Automation crashed: {e}", "ERROR")
        activity_fa_mark_error()
        _finish_err(str(e))
    finally:
        activity_set_pipeline(False)
        _FA_PRINT_TO_CONSOLE = False

def load_cursor_login_state():
    """email(lower) -> bool. Пустой файл — миграция по порядку в cursor_accounts.txt до CUTOFF_EMAIL_LOGGED_IN."""
    logged_in = {}
    if os.path.exists(CURSOR_LOGIN_STATE_FILE):
        try:
            with open(CURSOR_LOGIN_STATE_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            li = d.get("logged_in")
            if isinstance(li, dict):
                logged_in = {str(k).strip().lower(): bool(v) for k, v in li.items()}
        except Exception:
            logged_in = {}
    if not logged_in:
        cursor_acc = load_accounts(CURSOR_ACC_FILE)
        cutoff = CUTOFF_EMAIL_LOGGED_IN.strip().lower()
        idx = -1
        for i, a in enumerate(cursor_acc):
            if a.get("Email", "").strip().lower() == cutoff:
                idx = i
                break
        if idx >= 0:
            for i, a in enumerate(cursor_acc):
                em = a.get("Email", "").strip().lower()
                if em:
                    logged_in[em] = i <= idx
        save_cursor_login_state(logged_in)
    return logged_in


def save_cursor_login_state(logged_in):
    with open(CURSOR_LOGIN_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"logged_in": logged_in}, f, ensure_ascii=False, indent=2)


def mark_cursor_logged_in(email_addr):
    if not email_addr:
        return
    st = load_cursor_login_state()
    st[email_addr.strip().lower()] = True
    save_cursor_login_state(st)


def get_mailbox_password_by_email(email_addr):
    if not email_addr:
        return ''
    for acc in load_accounts(ACCOUNTS_FILE):
        if acc.get('Email', '').strip().lower() == email_addr.strip().lower():
            return acc.get('Password', '')
    return ''

def fetch_inbox(email_addr, password, limit=20):
    """Подключается по IMAP и возвращает список писем"""
    try:
        mail = imaplib.IMAP4_SSL('imap.mailbox.org', 993)
        mail.login(email_addr, password)
        mail.select('INBOX')
        _, data = mail.search(None, 'ALL')
        ids = data[0].split()
        ids = ids[-limit:][::-1]  # последние N писем, новые первые
        messages = []
        for uid in ids:
            _, msg_data = mail.fetch(uid, '(RFC822)')
            msg = email.message_from_bytes(msg_data[0][1])
            # Subject
            subj_raw = msg.get('Subject','')
            subj_parts = decode_header(subj_raw)
            subj = ''
            for part, enc in subj_parts:
                if isinstance(part, bytes):
                    subj += part.decode(enc or 'utf-8', errors='replace')
                else:
                    subj += part
            # From
            from_raw = msg.get('From','')
            # Date
            date_raw = msg.get('Date','')[:25]
            # Body text
            body = ''
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain':
                        try:
                            body = part.get_payload(decode=True).decode('utf-8', errors='replace')[:500]
                        except: pass
                        break
            else:
                try:
                    body = msg.get_payload(decode=True).decode('utf-8', errors='replace')[:500]
                except: pass

            # Ищем 6-значный код
            import re
            codes = re.findall(r'\b\d{6}\b', body + subj)
            code = codes[0] if codes else ''

            messages.append({
                'subject': subj[:80],
                'from': from_raw[:60],
                'date': date_raw,
                'body': body[:300],
                'code': code,
            })
        mail.logout()
        return {'ok': True, 'messages': messages}
    except Exception as e:
        return {'ok': False, 'error': str(e), 'messages': []}

def build_mailbox_html(accounts):
    if not accounts:
        return '<div class="acc-empty">// NO ACCOUNTS FOUND<br><span style="font-size:10px;color:#333">Добавь аккаунты в accounts.txt</span></div>'
    html = ''
    for i, acc in enumerate(accounts):
        email_    = acc.get('Email','')
        password  = acc.get('Password','')
        name      = acc.get('Name','Unknown')
        country   = acc.get('Country','')
        html += f'''<div class="acc-card">
          <div class="acc-num">MAILBOX #{i+1:02d}</div>
          <div class="acc-email">{email_}</div>
          <div class="acc-meta">{name} &nbsp;·&nbsp; 📍 {country}</div>
          <button class="acc-btn" onclick="openMail('{email_}','{password}')">▶ ВОЙТИ В ПОЧТУ</button>
          <button class="acc-btn" onclick="showInbox('{email_}','{password}',this)">📥 ПОКАЗАТЬ INBOX</button>
        </div>'''
    return html

def build_cursor_html(accounts):
    if not accounts:
        return '<div class="acc-empty">// NO CURSOR ACCOUNTS<br><span style="font-size:10px;color:#333">Зарегистрируй аккаунты через ГЛАВНАЯ</span></div>'
    visited = load_cursor_login_state()
    html = ''
    for i, acc in enumerate(accounts):
        email_   = acc.get('Email','')
        password = acc.get('Password','')
        name     = acc.get('Name','')
        ok = visited.get(email_.strip().lower(), False)
        badge = (
            '<span class="acc-visit acc-visit-yes" title="Уже заходил через NEXUS">✓ заходил</span>'
            if ok else
            '<span class="acc-visit acc-visit-no" title="Ещё не нажимал «Войти в Cursor» из NEXUS">✗ не заходил</span>'
        )
        html += f'''<div class="acc-card">
          <div class="acc-visit-row">{badge}</div>
          <div class="acc-num">CURSOR #{i+1:02d}</div>
          <div class="acc-email">{email_}</div>
          <div class="acc-meta">{name}</div>
          <button class="acc-btn" onclick="openCursor('{email_}','{password}')">▶ ВОЙТИ В CURSOR</button>
          <button class="acc-btn danger-btn" onclick="deleteCursor('{email_}','{password}')">✕ УДАЛИТЬ АККАУНТ</button>
        </div>'''
    return html

HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>NEXUS</title>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@700;900&family=Rajdhani:wght@400;600&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{height:100%;overflow:hidden}
body{
  background:#000;overflow:hidden;font-family:'Rajdhani',sans-serif;color:#fff;cursor:none;
  height:100%;min-height:0;max-height:100vh;max-height:100dvh;max-height:100svh;
}
#matrix-bg{position:fixed;inset:0;z-index:0;display:block;width:100%;height:100%;opacity:.45;pointer-events:none}
.particles-bg{position:fixed;inset:0;z-index:0;pointer-events:none}
.particle{position:absolute;width:2px;height:2px;background:#fff;border-radius:50%;box-shadow:0 0 10px #fff;animation:float 20s infinite linear}
@keyframes float{0%{transform:translateY(100vh) translateX(0)}100%{transform:translateY(-100vh) translateX(100px)}}
.waves-bg{position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden}
.wave{position:absolute;width:200%;height:200%;background:radial-gradient(circle,rgba(255,255,255,.03),transparent 70%);border-radius:45%;animation:wave 15s infinite linear}
.wave:nth-child(1){animation-duration:20s;opacity:.4}
.wave:nth-child(2){animation-duration:25s;animation-delay:-5s;opacity:.3}
.wave:nth-child(3){animation-duration:30s;animation-delay:-10s;opacity:.2}
@keyframes wave{0%{transform:translate(-50%,-50%) rotate(0deg)}100%{transform:translate(-50%,-50%) rotate(360deg)}}
.fa-vignette{position:fixed;inset:0;z-index:2;pointer-events:none;background:radial-gradient(ellipse at center,transparent 0%,rgba(0,0,0,.88) 100%)}
.fa-noise{position:fixed;inset:-50%;z-index:3;pointer-events:none;opacity:.035;
  background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  animation:fa-grain .8s steps(2) infinite}
@keyframes fa-grain{0%,100%{transform:translate(0,0)}25%{transform:translate(-2%,2%)}50%{transform:translate(2%,-1%)}75%{transform:translate(-1%,-2%)}}
.activity-steps{font-size:9px;line-height:1.4;margin:2px 0 4px;font-family:'Orbitron',monospace;letter-spacing:.04em;display:flex;flex-direction:column;gap:2px;max-height:76px;overflow-y:auto;padding-right:2px}
.activity-step{opacity:.45;display:flex;gap:6px;align-items:baseline}
.activity-step.active{opacity:1;font-weight:700}
.activity-step.done{opacity:.72}
.activity-step.error{opacity:1;color:#fcc}
.subscription-status{
  margin:8px auto 12px;padding:10px 16px;max-width:600px;
  border:1px solid rgba(255,255,255,.35);border-radius:8px;
  background:rgba(0,0,0,.65);text-align:center;
}
.sub-status-label{font-family:Orbitron,monospace;font-size:8px;letter-spacing:3px;color:rgba(255,255,255,.5);margin-bottom:6px}
.sub-status-row{display:flex;align-items:center;justify-content:center;gap:12px;margin-bottom:4px}
.sub-badge{font-family:Orbitron,monospace;font-size:10px;letter-spacing:2px;padding:4px 10px;border-radius:6px;border:1px solid rgba(255,255,255,.4);background:rgba(0,0,0,.5)}
.sub-badge.active{border-color:#fff;background:rgba(255,255,255,.15);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.7}}
.sub-email{font-family:'Courier New',monospace;font-size:10px;color:rgba(255,255,255,.7)}
.sub-ends{font-size:9px;color:rgba(255,255,255,.45);font-family:Orbitron,monospace;letter-spacing:1px}
.scanlines{
  position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:5;
  background:
    linear-gradient(rgba(18,16,16,0) 50%, rgba(0,0,0,0.1) 50%),
    radial-gradient(circle at center, transparent 20%, rgba(0,0,0,0.8) 100%);
  background-size:100% 4px,100% 100%;
}
.cursor-dot{
  position:fixed;width:4px;height:4px;background:#fff;border-radius:50%;
  box-shadow:0 0 15px 2px #fff,0 0 30px 5px rgba(255,255,255,0.2);
  pointer-events:none;z-index:9999;transform:translate(-50%,-50%);
}
.bg-overlay{
  position:fixed;inset:0;z-index:1;pointer-events:none;
  background:
    radial-gradient(ellipse 70% 50% at 30% 20%, rgba(120,40,180,0.18) 0%, transparent 65%),
    radial-gradient(ellipse 50% 70% at 80% 80%, rgba(80,10,120,0.22) 0%, transparent 60%),
    radial-gradient(ellipse 40% 40% at 60% 50%, rgba(160,80,220,0.08) 0%, transparent 55%);
}
.ui{
  position:relative;z-index:10;display:flex;flex-direction:column;
  height:100%;min-height:0;max-height:100vh;max-height:100dvh;max-height:100svh;
  padding:0 24px 20px;
  overflow:hidden;box-sizing:border-box;
}
.ui-top{flex-shrink:0}
.ui-mid{
  flex:1 1 auto;min-height:0;display:flex;flex-direction:column;
  overflow-x:hidden;overflow-y:auto;-webkit-overflow-scrolling:touch;overscroll-behavior:contain;
}
.ui-mid .page{display:none !important;flex:1;min-height:0;overflow:hidden;flex-direction:column}
.ui-mid .page.active{display:flex !important;animation:fadeIn .5s ease-out}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
#page-main.page.active{justify-content:center;align-items:stretch}
.ui-log{
  display:flex;flex-direction:column;gap:5px;
  position:fixed;left:0;right:0;bottom:0;width:100%;box-sizing:border-box;
  padding:10px 24px max(10px, env(safe-area-inset-bottom, 0px));
  margin:0;
  border-top:2px solid rgba(255,255,255,.55)!important;
  min-height:min(140px,22vh);max-height:min(38vh,300px);overflow-y:auto;overflow-x:hidden;
  background:rgba(8,8,8,.98)!important;z-index:80;
  box-shadow:0 -10px 40px rgba(0,0,0,.97)!important;
  -webkit-overflow-scrolling:touch;
}
.header{display:flex;align-items:center;justify-content:space-between;padding:16px 0 0}
.status{display:flex;align-items:center;gap:8px;font-size:11px;color:#444;letter-spacing:2px}
.sdot{width:7px;height:7px;border-radius:50%;background:#b266ff;box-shadow:0 0 8px #b266ff;animation:blink 1.5s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
.close-btn{font-size:22px;color:#333;cursor:none;transition:color .2s;padding:8px}
.close-btn:hover{color:#b266ff;text-shadow:0 0 20px #b266ff}
.title-wrap{text-align:center;margin:4px 0 14px}
.title{font-family:'Orbitron',monospace;font-size:46px;font-weight:900;letter-spacing:10px;
  background:linear-gradient(90deg,#fff,#b266ff,#fff);background-size:200%;
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  animation:shimmer 3s linear infinite;filter:drop-shadow(0 0 30px #b266ff88)}
@keyframes shimmer{from{background-position:200% 0}to{background-position:-200% 0}}
.subtitle{font-size:10px;letter-spacing:8px;color:#b266ff55;margin-top:3px}
.tabs{display:flex;gap:2px;margin:0 auto 12px auto;border-bottom:1px solid #1f1230;justify-content:center;width:fit-content}
.tab{font-family:'Orbitron',monospace;font-size:9px;letter-spacing:2px;padding:8px 16px;
  cursor:none;color:#444;border-bottom:2px solid transparent;margin-bottom:-1px;transition:color .2s,border-color .2s}
.tab:hover{color:#b266ff}
.tab.active{color:#b266ff;border-bottom-color:#b266ff}
/* MAIN */
#page-main{justify-content:flex-start!important;padding-top:20px}
.status-card-3d{
  width:100%;max-width:600px;margin:0 auto 30px;
  perspective:1000px;
}
.status-card-compact{
  max-width:500px;
  margin-top:30px;
}
.status-card-compact .status-card-inner{
  padding:16px;
}
.status-card-compact .status-header{
  margin-bottom:12px;
}
.status-card-compact .status-icon{
  font-size:24px;
}
.status-card-compact .status-title{
  font-size:14px;
  letter-spacing:3px;
}
.status-card-compact .status-body{
  gap:8px;
}
.status-card-compact .progress-bar-3d{
  height:8px;
}
.status-card-compact .status-message{
  font-size:10px;
}
.status-card-inner{
  position:relative;
  background:rgba(0,0,0,.9);
  border:2px solid rgba(255,255,255,.4);
  border-radius:20px;
  padding:24px;
  transform-style:preserve-3d;
  transition:all .6s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow:0 10px 40px rgba(0,0,0,.5);
}
.status-card-inner:hover{
  transform:translateY(-5px) rotateX(2deg);
  border-color:#fff;
  box-shadow:0 20px 60px rgba(0,0,0,.7),0 0 40px rgba(255,255,255,.1);
  transition:all .4s cubic-bezier(0.4, 0, 0.2, 1);
}
.status-card-glow{
  position:absolute;
  inset:-2px;
  background:linear-gradient(45deg,transparent,rgba(255,255,255,.1),transparent);
  border-radius:20px;
  opacity:0;
  transition:opacity .3s;
  pointer-events:none;
}
.status-card-inner:hover .status-card-glow{
  opacity:1;
  animation:rotate 3s linear infinite;
}
@keyframes rotate{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
.status-header{
  display:flex;
  align-items:center;
  gap:12px;
  margin-bottom:20px;
}
.status-icon{
  font-size:32px;
  animation:pulse 2s infinite;
}
@keyframes pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.1)}}
.status-title{
  font-family:'Orbitron',monospace;
  font-size:18px;
  font-weight:900;
  letter-spacing:4px;
  color:#fff;
  text-shadow:0 0 20px rgba(255,255,255,.5);
}
.status-body{
  display:flex;
  flex-direction:column;
  gap:12px;
}
.status-row{
  display:flex;
  justify-content:space-between;
  align-items:center;
}
.status-label{
  font-family:'Orbitron',monospace;
  font-size:10px;
  letter-spacing:3px;
  color:rgba(255,255,255,.6);
}
.status-value{
  font-family:'Orbitron',monospace;
  font-size:14px;
  font-weight:700;
  color:#fff;
  text-shadow:0 0 10px rgba(255,255,255,.3);
}
.progress-bar-3d{
  width:100%;
  height:12px;
  background:rgba(255,255,255,.1);
  border:1px solid rgba(255,255,255,.3);
  border-radius:6px;
  overflow:hidden;
  position:relative;
  box-shadow:inset 0 2px 4px rgba(0,0,0,.3);
}
.progress-fill-3d{
  height:100%;
  background:linear-gradient(90deg,#fff,rgba(255,255,255,.8));
  border-radius:6px;
  transition:width .3s;
  box-shadow:0 0 20px rgba(255,255,255,.5);
  position:relative;
}
.progress-fill-3d::after{
  content:'';
  position:absolute;
  inset:0;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.3),transparent);
  animation:shimmer 2s infinite;
}
@keyframes shimmer{from{transform:translateX(-100%)}to{transform:translateX(100%)}}
.status-message{
  font-size:11px;
  color:rgba(255,255,255,.7);
  text-align:center;
  font-family:'Rajdhani',sans-serif;
  letter-spacing:1px;
}
.cards{display:grid;grid-template-columns:repeat(3,minmax(220px,280px));gap:18px;width:100%;max-width:1000px;margin:0 auto;justify-content:center}
.card{height:120px;border-radius:18px;background:transparent;border:1px solid rgba(255,255,255,0.1);
  display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;
  cursor:none;animation:popIn .5s ease both;transition:all .2s}
@keyframes popIn{from{transform:scale(0.8);opacity:0}to{transform:scale(1);opacity:1}}
.card:nth-child(1){animation-delay:.1s}
.card:nth-child(2){animation-delay:.2s}
.card:nth-child(3){animation-delay:.3s}
.card:hover{border-color:#b266ff;box-shadow:0 0 35px #b266ff55;transform:scale(1.04);background:rgba(24,10,40,0.7)}
.card.clicking{transform:scale(0.97)!important}
.card.danger:hover{box-shadow:0 0 45px #b266ff99}
.card-icon{font-size:24px;transition:transform .3s}
.card:hover .card-icon{transform:scale(1.2)}
.card-label{font-family:'Orbitron',monospace;font-size:9px;letter-spacing:3px;text-align:center;line-height:1.7}
.card:hover .card-label{color:#c997ff}
/* ACCOUNTS */
.acc-scroll{flex:1;overflow-y:auto;padding-right:4px}
.acc-scroll::-webkit-scrollbar{width:3px}
.acc-scroll::-webkit-scrollbar-thumb{background:#35204f;border-radius:2px}
.acc-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px;padding:2px}
.acc-card{background:rgba(12,5,20,0.85);border:1px solid #241335;border-radius:10px;padding:12px 14px;transition:all .2s;animation:fadeInUp .4s ease-out backwards}
@keyframes fadeInUp{from{opacity:0;transform:translateY(15px)}to{opacity:1;transform:translateY(0)}}
.acc-card:nth-child(1){animation-delay:.05s}
.acc-card:nth-child(2){animation-delay:.1s}
.acc-card:nth-child(3){animation-delay:.15s}
.acc-card:nth-child(4){animation-delay:.2s}
.acc-card:nth-child(5){animation-delay:.25s}
.acc-card:nth-child(6){animation-delay:.3s}
.acc-card:hover{border-color:#b266ff33}
.acc-visit-row{margin-bottom:6px}
.acc-visit{display:inline-block;font-size:9px;letter-spacing:1px;padding:3px 8px;border-radius:6px;font-family:'Orbitron',monospace}
.acc-visit-yes{color:#5ecf7a;border:1px solid #2d6a3d;background:rgba(40,90,55,0.25)}
.acc-visit-no{color:#e07080;border:1px solid #6a2d35;background:rgba(90,40,50,0.25)}
.acc-num{font-size:8px;letter-spacing:3px;color:#b266ff55;margin-bottom:5px;font-family:'Orbitron',monospace}
.acc-email{font-family:'Courier New',monospace;font-size:11px;color:#c997ff;margin-bottom:3px;word-break:break-all}
.acc-meta{font-size:10px;color:#2a2a2a;margin-bottom:8px}
.acc-btn{width:100%;padding:6px;background:transparent;border:1px solid #241335;
  border-radius:6px;color:#b266ff55;font-family:'Orbitron',monospace;font-size:8px;
  letter-spacing:2px;cursor:none;transition:all .2s;margin-top:3px;display:block}
.acc-btn:hover{border-color:#b266ff;color:#b266ff;background:#180d25;box-shadow:0 0 10px #b266ff33}
.danger-btn:hover{border-color:#a95bff;color:#a95bff;background:#1b0f2a}
.acc-empty{text-align:center;color:#1a1a1a;font-family:'Orbitron',monospace;font-size:11px;letter-spacing:4px;padding:40px 0;line-height:2.2}
/* INBOX */
.inbox-wrap{display:flex;gap:12px;flex:1;overflow:hidden}
.inbox-sidebar{width:220px;flex-shrink:0;display:flex;flex-direction:column;gap:8px;overflow-y:auto;transition:width .2s ease,opacity .2s ease,margin .2s ease}
.inbox-sidebar.collapsed{width:0;min-width:0;opacity:0;margin:0;padding:0;overflow:hidden;pointer-events:none;border:none;gap:0}
.inbox-sidebar::-webkit-scrollbar{width:2px}
.inbox-sidebar::-webkit-scrollbar-thumb{background:#35204f}
.inbox-acc-btn{padding:10px 12px;background:rgba(12,5,20,0.8);border:1px solid #1f1230;border-radius:8px;
  cursor:none;transition:all .2s;text-align:left}
.inbox-acc-btn:hover,.inbox-acc-btn.active{border-color:#b266ff66;background:#1b0f2a}
.inbox-acc-btn.active{border-color:#b266ff;box-shadow:0 0 12px #b266ff33}
.inbox-email{font-family:'Courier New',monospace;font-size:10px;color:#c997ff}
.inbox-name{font-size:9px;color:#333;margin-top:2px}
.inbox-main{flex:1;display:flex;flex-direction:column;overflow:hidden}
.inbox-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.inbox-title{font-family:'Orbitron',monospace;font-size:9px;letter-spacing:3px;color:#b266ff66}
.inbox-refresh{font-size:9px;color:#444;cursor:none;padding:4px 10px;border:1px solid #1f1230;border-radius:4px;background:transparent;font-family:'Orbitron',monospace;letter-spacing:1px;transition:all .2s}
.inbox-refresh:hover{color:#b266ff;border-color:#b266ff33}
.inbox-loading{text-align:center;color:#222;font-family:'Orbitron',monospace;font-size:10px;letter-spacing:3px;padding:40px 0;animation:blink 1s infinite}
.inbox-list{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:6px}
.inbox-list::-webkit-scrollbar{width:2px}
.inbox-list::-webkit-scrollbar-thumb{background:#35204f}
.msg-card{background:rgba(12,5,20,0.8);border:1px solid #241335;border-radius:8px;padding:10px 12px;transition:all .2s;cursor:none}
.msg-card:hover{border-color:#b266ff33}
.msg-subj{font-size:11px;color:#b985ff;font-weight:600;margin-bottom:3px;word-break:break-word}
.msg-from{font-size:9px;color:#333;margin-bottom:2px}
.msg-date{font-size:9px;color:#222;margin-bottom:6px}
.msg-body{font-family:'Courier New',monospace;font-size:9px;color:#444;line-height:1.6;word-break:break-all}
.msg-code{display:inline-flex;align-items:center;gap:8px;background:#1f1230;border:1px solid #b266ff44;border-radius:6px;padding:6px 12px;margin-top:6px;cursor:none}
.msg-code-num{font-family:'Orbitron',monospace;font-size:16px;color:#c997ff;letter-spacing:4px}
.msg-code-copy{font-size:8px;color:#b266ff77;letter-spacing:1px;cursor:none;transition:color .2s}
.msg-code-copy:hover{color:#b266ff}
.inbox-empty{text-align:center;color:#1a1a1a;font-family:'Orbitron',monospace;font-size:10px;letter-spacing:3px;padding:40px 0}
/* LOG */
.log-label{font-size:9px;letter-spacing:4px;color:#b266ff33;margin-bottom:2px;font-weight:600}
.log-box{background:rgba(8,4,14,0.95);border:1px solid #180d25;border-radius:5px;
  padding:6px 10px;font-family:'Courier New',monospace;font-size:9px;color:#c997ff;
  min-height:28px;max-height:28px;overflow:hidden;letter-spacing:1px}
.log-box.log-status{min-height:34px;max-height:48px}
.activity-progress-track{width:100%;height:8px;border-radius:4px;background:rgba(255,255,255,.12);overflow:hidden;border:1px solid rgba(255,255,255,.35)}
.activity-progress-fill{height:100%;width:0%;background:#fff;border-radius:3px;transition:width .25s ease}
.log-box.log-scroll{min-height:100px;flex:1;max-height:none;max-width:100%;overflow-y:auto;overflow-x:hidden;white-space:pre-wrap;word-break:break-word;font-size:10px;line-height:1.4;margin:0}
#activity-log{color:#e8e8e8 !important}
@media (max-height:780px){
  .title{font-size:34px!important;letter-spacing:6px!important}
  .title-wrap{margin:2px 0 8px!important}
  .header{padding:8px 0 0!important}
  .tabs{margin-bottom:6px!important}
  .ui{padding-bottom:max(min(34vh, 260px), calc(env(safe-area-inset-bottom, 0px) + 10px))!important}
  .ui-log{min-height:110px;max-height:min(34vh, 260px)}
}
.script-progress-win{
  position:fixed;left:50%;z-index:88;
  bottom:min(max(160px, calc(min(38vh, 300px) + 14px)), 50vh);
  transform:translateX(-50%) translateY(16px);
  width:min(580px,94vw);max-height:min(46vh,420px);z-index:60;
  display:flex;flex-direction:column;gap:6px;
  padding:12px 14px 10px;
  background:rgba(8,4,14,.97);border:1px solid #b266ff55;border-radius:14px;
  box-shadow:0 16px 56px rgba(0,0,0,.9),0 0 0 1px rgba(178,102,255,.12);
  opacity:0;pointer-events:none;visibility:hidden;
  transition:opacity .24s ease,transform .24s ease,visibility 0s linear .25s;
}
.script-progress-win.visible{
  opacity:1;pointer-events:auto;visibility:visible;
  transform:translateX(-50%) translateY(0);
  transition:opacity .24s ease,transform .24s ease,visibility 0s;
}
.script-progress-win-head{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-shrink:0}
.script-progress-win-title{font-family:Orbitron,monospace;font-size:9px;letter-spacing:3px;color:#b266ff88}
.script-progress-win-min{
  flex-shrink:0;width:30px;height:28px;padding:0;border:1px solid #35204f;border-radius:8px;
  background:transparent;color:#888;font-size:12px;line-height:1;cursor:none;font-family:Orbitron,monospace
}
.script-progress-win-min:hover{color:#b266ff;border-color:#b266ff44}
.script-progress-win-task{font-family:Orbitron,monospace;font-size:10px;letter-spacing:2px;color:#c997ff;min-height:1.2em;word-break:break-word}
.script-progress-win-body{display:flex;flex-direction:column;gap:5px;min-height:0;flex:1}
.script-progress-win-pct{font-family:Orbitron,monospace;font-size:10px;letter-spacing:3px;margin-top:1px}
.script-progress-win-phase{font-size:10px;line-height:1.45;color:#888;max-height:3em;overflow:hidden}
.spw-track{flex-shrink:0}
.script-progress-win-log{
  flex:1;min-height:72px;max-height:min(22vh,200px);margin:0;overflow-y:auto;overflow-x:hidden;
  background:rgba(0,0,0,.45);border:1px solid #241335;border-radius:8px;padding:8px 10px;
  font-family:Consolas,'Courier New',monospace;font-size:9px;line-height:1.38;color:#e8e8e8;white-space:pre-wrap;word-break:break-word
}
.script-progress-win--min{max-height:none;padding-bottom:10px}
.script-progress-win--min .script-progress-win-body{display:none!important}

/* ═══════════════════════════════════════════════════════════════════════════
   MONOCHROME THEME: Pure Black & White (Matrix Style)
   ═══════════════════════════════════════════════════════════════════════════ */
html,body{height:100%!important;max-height:100dvh!important;max-height:100svh!important;overflow:hidden!important}
body{background:#000!important;color:#fff!important}
.bg-overlay{display:none!important}

/* Cursor & Status Dot */
.cursor-dot,.sdot{border-color:#fff!important;background:#fff!important;box-shadow:0 0 12px #fff,0 0 24px rgba(255,255,255,.4)!important}

/* Title - White with glow */
.title{
  background:linear-gradient(90deg,#fff,#fff,#fff)!important;
  -webkit-background-clip:text!important;
  -webkit-text-fill-color:transparent!important;
  filter:drop-shadow(0 0 20px rgba(255,255,255,.5))!important;
  animation:titlePulse 4s ease-in-out infinite!important;
}
@keyframes titlePulse{0%,100%{opacity:1;filter:drop-shadow(0 0 20px rgba(255,255,255,.5))}50%{opacity:.92;filter:drop-shadow(0 0 30px rgba(255,255,255,.7))}}

/* All text elements - pure white */
.status,.close-btn,.subtitle,.tab,.acc-meta,.inbox-name,.msg-from,.msg-date,.msg-body,
.inbox-loading,.inbox-empty,.acc-empty,.log-label,.inbox-refresh,.card-label,.inbox-title,
.inbox-email,.acc-email,.msg-subj,.msg-code-num,.msg-code-copy,.acc-num,.acc-btn,
.sub-status-label,.sub-badge,.sub-email,.sub-ends,.activity-progress-track{
  color:#fff!important;
}

/* Borders - white */
.tabs,.tab.active,.tab:hover,.inbox-refresh:hover,.msg-code,
.subscription-status,.sub-badge{
  border-color:rgba(255,255,255,.5)!important;
}

/* Cards & Containers - black with white borders */
.card,.acc-card,.msg-card,.inbox-acc-btn,.log-box,.msg-code,
.subscription-status{
  background:rgba(0,0,0,.85)!important;
  border-color:rgba(255,255,255,.35)!important;
  box-shadow:none!important;
}

/* Hover states - brighter white borders */
.card:hover,.acc-card:hover,.msg-card:hover,.inbox-acc-btn:hover,
.inbox-acc-btn.active,.acc-btn:hover,.danger-btn:hover,.msg-code-copy:hover,
.tab:hover,.close-btn:hover,.inbox-refresh:hover{
  color:#fff!important;
  border-color:#fff!important;
  background:rgba(0,0,0,.95)!important;
  box-shadow:0 0 20px rgba(255,255,255,.15)!important;
}

/* Active subscription badge */
.sub-badge.active{
  border-color:#fff!important;
  background:rgba(255,255,255,.12)!important;
  box-shadow:0 0 15px rgba(255,255,255,.25)!important;
}

/* Badges */
.acc-visit-yes,.acc-visit-no{
  color:#fff!important;
  border-color:rgba(255,255,255,.4)!important;
  background:rgba(0,0,0,.7)!important;
}

/* Progress bars */
.activity-progress-track{
  background:rgba(255,255,255,.15)!important;
  border-color:rgba(255,255,255,.4)!important;
}
.activity-progress-fill{
  background:#fff!important;
  box-shadow:0 0 10px rgba(255,255,255,.5)!important;
}

/* Forms */
input,textarea,button{
  background:rgba(0,0,0,.9)!important;
  color:#fff!important;
  border-color:rgba(255,255,255,.4)!important;
}
input:focus,textarea:focus{
  border-color:#fff!important;
  box-shadow:0 0 10px rgba(255,255,255,.2)!important;
}

/* Log dock */
#nexus-log-dock{
  position:fixed!important;left:0!important;right:0!important;bottom:0!important;
  z-index:85!important;
  box-shadow:0 -10px 36px rgba(0,0,0,.98)!important;
  border-top:2px solid rgba(255,255,255,.6)!important;
  background:rgba(0,0,0,.98)!important;
}

/* Script progress window */
.script-progress-win,.script-progress-win-log{
  background:rgba(0,0,0,.96)!important;
  border-color:rgba(255,255,255,.5)!important;
  box-shadow:0 12px 40px rgba(0,0,0,.95),0 0 0 1px rgba(255,255,255,.1)!important;
}
.script-progress-win-title,.script-progress-win-task,.script-progress-win-pct,
.script-progress-win-phase,.script-progress-win-min,#spw-log,#activity-log{
  color:#fff!important;
}
.script-progress-win-min{
  border-color:rgba(255,255,255,.4)!important;
  background:rgba(0,0,0,.8)!important;
}
.script-progress-win-min:hover{
  border-color:#fff!important;
  color:#fff!important;
}

/* Modals */
#reg-modal>div,#fa-modal>div,#confirm-modal>div{
  background:rgba(0,0,0,.95)!important;
  border-color:rgba(255,255,255,.5)!important;
  box-shadow:0 0 60px rgba(0,0,0,.9),0 0 0 1px rgba(255,255,255,.15)!important;
}

/* Remove all purple/color references */
[style*="#b266ff"],[style*="#c997ff"],[style*="#a95bff"],[style*="#35204f"],
[style*="#241335"],[style*="#1f1230"],[style*="#090511"],[style*="#0f081a"],
[style*="#120b1f"],[style*="#ddaaff"],[style*="#b985ff"]{
  color:#fff!important;
  border-color:rgba(255,255,255,.4)!important;
  background:rgba(0,0,0,.85)!important;
}

/* Matrix background - more visible */
#matrix-bg{opacity:.45!important}
</style>
</head>
<body>
<canvas id="matrix-bg" aria-hidden="true"></canvas>
<div id="particles-container" class="particles-bg"></div>
<div id="waves-container" class="waves-bg"></div>
<div class="fa-vignette" aria-hidden="true"></div>
<div class="fa-noise" aria-hidden="true"></div>
<div class="scanlines"></div>
<div class="cursor-dot" id="dot"></div>
<div class="ui">
  <div class="ui-top">
  <div class="header">
    <div class="status"><div class="sdot"></div><span id="clock">--:--:--</span></div>
    <div class="close-btn" onclick="fetch('/run?action=exit')">✕</div>
  </div>
  <div class="title-wrap">
    <div class="title">NEXUS</div>
    <div class="subtitle">AUTOMATION SUITE</div>
  </div>
  <div class="tabs">
    <div class="tab active" onclick="switchTab('main',this)">// ГЛАВНАЯ</div>
    <div class="tab" onclick="switchTab('mailbox',this)">// MAILBOX</div>
    <div class="tab" onclick="switchTab('cursor',this)">// CURSOR</div>
    <div class="tab" onclick="switchTab('inbox',this);initInbox()">// INBOX</div>
  </div>
  </div>

  <div class="ui-mid">
  <!-- MAIN -->
  <div class="page active" id="page-main">
    <!-- Action Cards -->
    <div class="cards">
      <div class="card" onclick="run('mailbox_register',this)">
        <div class="card-icon">📧</div><div class="card-label">REGISTER<br>MAILBOX</div>
      </div>
      <div class="card" onclick="openPS()">
        <div class="card-icon">⚙️</div><div class="card-label">POWERSHELL<br>ADMIN</div>
      </div>
      <div class="card" onclick="openFullAutomationModal(this)">
        <div class="card-icon">⛓</div><div class="card-label">FULL<br>AUTOMATION</div>
      </div>
    </div>

    <!-- Status Card 3D - smaller and below -->
    <div class="status-card-3d status-card-compact">
      <div class="status-card-inner">
        <div class="status-card-glow"></div>
        <div class="status-header">
          <div class="status-icon">⚡</div>
          <div class="status-title">SYSTEM STATUS</div>
        </div>
        <div class="status-body">
          <div class="status-row">
            <span class="status-label">STATUS</span>
            <span class="status-value" id="system-status">READY</span>
          </div>
          <div class="status-row">
            <span class="status-label">PROGRESS</span>
            <span class="status-value" id="system-progress">0%</span>
          </div>
          <div class="progress-bar-3d">
            <div class="progress-fill-3d" id="progress-fill" style="width:0%"></div>
          </div>
          <div class="status-message" id="status-message">Система готова к работе</div>
        </div>
      </div>
    </div>
  </div>

  <!-- AUTOMATION -->
  <div class="page" id="page-automation">
    <div style="display:flex;flex-direction:column;gap:14px;max-width:760px;margin:0 auto;width:100%;padding-top:4px">
      <div style="font-family:Orbitron,monospace;font-size:10px;letter-spacing:3px;color:#b266ff66">// FULL AUTOMATION FLOW</div>
      <div style="font-size:10px;color:#555;line-height:1.8">
        0) Окно Full Automation: вставь PowerShell или ✕ без PS<br>
        1) Скрипт PS, почта и Cursor пишут вывод в панель «ЛОГ ЗАПУСКОВ» внизу — отдельные CMD не открываются<br>
        2) Mailbox.org — Brave отдельно; шаги и текст скриптов — в логе панели<br>
        3) Пароль по умолчанию: Artemka228zxc<br>
        4) Cursor — вывод туда же<br>
        5) NEXUS_OPEN_CURSOR_AFTER_AUTO=1 — открыть приложение Cursor после цепочки<br>
        6) Log in в Cursor → скопировать ссылку → браузер регистрации → Enter → Yes / Log in<br>
        <span style="opacity:.85">Старая чёрная консоль для цепочки: переменная NEXUS_FA_LEGACY_CONSOLE=1</span>
      </div>
      <button onclick="openFullAutomationModal(this)" style="align-self:flex-start;padding:10px 18px;background:transparent;border:1px solid #b266ff55;border-radius:8px;color:#b266ff;font-family:Orbitron,monospace;font-size:8px;letter-spacing:2px;cursor:none;transition:all .2s" onmouseenter="this.style.background='#1f1230';this.style.borderColor='#b266ff';this.style.boxShadow='0 0 20px #b266ff33'" onmouseleave="this.style.background='transparent';this.style.borderColor='#b266ff55';this.style.boxShadow='none'">⚡ START AUTOMATION</button>
      <div style="font-size:9px;color:#2a2a2a;line-height:1.7">
        Текст для вставки: <span style="color:#b266ff66;font-family:Courier New,monospace">FULL_AUTOMATION_POWERSHELL.txt</span> — можно <a href="/download/FULL_AUTOMATION_POWERSHELL.txt" download style="color:#b266ff">скачать с сайта</a>.<br>
        Запуск с ПК (одно окно CMD → Python → NEXUS; анимация fsociety — <a href="/download/run_fsociety.ps1" download style="color:#b266ff">run_fsociety.ps1</a>): <a href="/download/run_fsociety.cmd" download style="color:#b266ff">run_fsociety.cmd</a><br>
        Регистрация почты / Cursor с главной: лог и прогресс — в панели внизу (без окон CMD).
      </div>
    </div>
  </div>

  <!-- MAILBOX -->
  <div class="page" id="page-mailbox">
    <div class="acc-scroll"><div class="acc-grid">MAILBOX_PLACEHOLDER</div></div>
  </div>

  <!-- CURSOR -->
  <div class="page" id="page-cursor">
    <div class="acc-scroll"><div class="acc-grid">CURSOR_PLACEHOLDER</div></div>
  </div>

  <!-- POWERSHELL -->
  <div class="page" id="page-powershell">
    <div style="display:flex;flex-direction:column;gap:12px;flex:1;overflow:hidden">
      <div style="font-family:Orbitron,monospace;font-size:9px;letter-spacing:3px;color:#b266ff66">// POWERSHELL — ADMIN</div>
      <div style="font-size:10px;color:#444">Скрипты из папки <span style="color:#b266ff66;font-family:Courier New,monospace">nexus/ps_scripts/</span> — положи туда .ps1 файлы</div>
      <div id="ps-list" style="flex:1;overflow-y:auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;align-content:start;padding:2px"></div>
      <button onclick="openPS()" style="align-self:flex-start;padding:7px 16px;background:transparent;border:1px solid #1f1230;border-radius:6px;color:#444;font-family:Orbitron,monospace;font-size:8px;letter-spacing:2px;cursor:none;transition:all .2s" onmouseenter="this.style.color='#b266ff66';this.style.borderColor='#b266ff33'" onmouseleave="this.style.color='#444';this.style.borderColor='#1f1230'">⟳ ОБНОВИТЬ</button>
    </div>
  </div>

  <!-- INBOX -->
  <div class="page" id="page-inbox">
    <div class="inbox-wrap">
      <div class="inbox-sidebar" id="inbox-sidebar">INBOX_SIDEBAR</div>
      <div class="inbox-main">
        <div class="inbox-header">
          <div class="inbox-title" id="inbox-title">// ВЫБЕРИ АККАУНТ</div>
          <button class="inbox-refresh" onclick="refreshInbox()" id="refresh-btn">⟳ ОБНОВИТЬ</button>
        </div>
        <div class="inbox-list" id="inbox-list">
          <div class="inbox-empty">← Выбери аккаунт слева</div>
        </div>
      </div>
    </div>
  </div>
  <!-- PS SCRIPTS -->
  <div class="page" id="page-psscripts">
    <div style="flex:1;overflow-y:auto;display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;padding:2px;align-content:start" id="ps-scripts-grid">
      <div style="color:#1a1a1a;font-family:Orbitron,monospace;font-size:9px;letter-spacing:3px;padding:20px;grid-column:1/-1">ЗАГРУЗКА...</div>
    </div>
  </div>
  </div>

</div>

<div id="script-progress-win" class="script-progress-win" role="status" aria-live="polite" aria-atomic="false">
  <div class="script-progress-win-head">
    <span class="script-progress-win-title">// ХОД ВЫПОЛНЕНИЯ СКРИПТА</span>
    <button type="button" class="script-progress-win-min" onclick="toggleScriptProgressWinMin(event)" title="Свернуть / развернуть">▾</button>
  </div>
  <div id="spw-task" class="script-progress-win-task"></div>
  <div class="script-progress-win-body">
    <div class="activity-progress-track spw-track"><div id="spw-fill" class="activity-progress-fill"></div></div>
    <div id="spw-pct" class="script-progress-win-pct"></div>
    <div id="spw-phase" class="script-progress-win-phase"></div>
    <pre id="spw-log" class="script-progress-win-log"></pre>
  </div>
</div>

<!-- REGISTER MODAL -->
<div id="reg-modal" style="display:none;position:fixed;inset:0;z-index:9000;background:rgba(0,0,0,0.82);backdrop-filter:blur(4px);align-items:center;justify-content:center">
  <div style="background:#090511;border:1px solid #b266ff44;border-radius:16px;padding:32px 36px;width:360px;box-shadow:0 0 60px #b266ff22;position:relative">
    <div style="font-family:Orbitron,monospace;font-size:11px;letter-spacing:4px;color:#b266ff;margin-bottom:24px">// CURSOR REGISTER</div>

    <div style="font-size:9px;letter-spacing:2px;color:#444;margin-bottom:6px;font-family:Orbitron,monospace">CURSOR EMAIL</div>
    <input id="reg-email" type="email" placeholder="user@mailbox.org"
      style="width:100%;background:#0f081a;border:1px solid #35204f;border-radius:8px;padding:10px 12px;color:#c997ff;font-family:Courier New,monospace;font-size:12px;outline:none;margin-bottom:16px;box-sizing:border-box"
      onfocus="this.style.borderColor='#b266ff'" onblur="this.style.borderColor='#35204f'">

    <div style="font-size:9px;letter-spacing:2px;color:#444;margin-bottom:6px;font-family:Orbitron,monospace">CURSOR PASSWORD</div>
    <input id="reg-cursor-pass" type="password" placeholder="Пароль для Cursor" value="Artemka228zxc"
      style="width:100%;background:#0f081a;border:1px solid #35204f;border-radius:8px;padding:10px 12px;color:#c997ff;font-family:Courier New,monospace;font-size:12px;outline:none;margin-bottom:16px;box-sizing:border-box"
      onfocus="this.style.borderColor='#b266ff'" onblur="this.style.borderColor='#35204f'">

    <div style="font-size:9px;letter-spacing:2px;color:#444;margin-bottom:6px;font-family:Orbitron,monospace">MAILBOX PASSWORD (для авточтения кода)</div>
    <input id="reg-mail-pass" type="password" placeholder="Пароль от mailbox.org" value="Artemka228zxc"
      style="width:100%;background:#0f081a;border:1px solid #35204f;border-radius:8px;padding:10px 12px;color:#c997ff;font-family:Courier New,monospace;font-size:12px;outline:none;margin-bottom:24px;box-sizing:border-box"
      onfocus="this.style.borderColor='#b266ff'" onblur="this.style.borderColor='#35204f'"
      onkeydown="if(event.key==='Enter')submitRegister()">

    <div style="display:flex;gap:10px">
      <button onclick="closeRegisterModal()"
        style="flex:1;padding:10px;background:transparent;border:1px solid #2d1a44;border-radius:8px;color:#444;font-family:Orbitron,monospace;font-size:8px;letter-spacing:2px;cursor:none;transition:all .2s"
        onmouseenter="this.style.borderColor='#b266ff33';this.style.color='#777'"
        onmouseleave="this.style.borderColor='#2d1a44';this.style.color='#444'">ОТМЕНА</button>
      <button onclick="submitRegister()"
        style="flex:2;padding:10px;background:transparent;border:1px solid #b266ff55;border-radius:8px;color:#b266ff;font-family:Orbitron,monospace;font-size:8px;letter-spacing:2px;cursor:none;transition:all .2s"
        onmouseenter="this.style.background='#1f1230';this.style.borderColor='#b266ff';this.style.boxShadow='0 0 20px #b266ff33'"
        onmouseleave="this.style.background='transparent';this.style.borderColor='#b266ff55';this.style.boxShadow='none'">⚡ ЗАПУСТИТЬ</button>
    </div>
  </div>
</div>

<!-- FULL AUTOMATION — PowerShell prompt -->
<div id="fa-modal" style="display:none;position:fixed;inset:0;z-index:9001;background:rgba(0,0,0,0.82);backdrop-filter:blur(4px);align-items:center;justify-content:center">
  <div style="background:#090511;border:1px solid #b266ff44;border-radius:16px;padding:28px 32px;width:min(520px,92vw);max-height:85vh;box-shadow:0 0 60px #b266ff22;position:relative;display:flex;flex-direction:column;gap:14px;box-sizing:border-box">
    <button type="button" onclick="fullAutomationSkipPs()" title="Без PowerShell — сразу автоматизация"
      style="position:absolute;top:14px;right:14px;width:36px;height:36px;padding:0;background:transparent;border:1px solid #2d1a44;border-radius:8px;color:#888;font-size:16px;line-height:1;cursor:none;transition:all .2s"
      onmouseenter="this.style.borderColor='#b266ff44';this.style.color='#b266ff'"
      onmouseleave="this.style.borderColor='#2d1a44';this.style.color='#888'">✕</button>
    <div style="font-family:Orbitron,monospace;font-size:11px;letter-spacing:4px;color:#b266ff;padding-right:40px">// FULL AUTOMATION — POWERSHELL</div>
    <div style="font-size:9px;color:#555;line-height:1.6">Вставь основной скрипт (или из <span style="color:#b266ff66;font-family:Courier New,monospace">FULL_AUTOMATION_POWERSHELL.txt</span>). <b style="color:#666">Горячие слова</b> — дополнительный PowerShell ниже, он выполнится после верхней части в том же запуске. Оба поля автоматически сохраняются. Пустые оба + «Запустить» — пустое окно Admin PS. ✕ — без PowerShell.</div>
    <div style="font-size:9px;letter-spacing:2px;color:#444;font-family:Orbitron,monospace">ОСНОВНОЙ СКРИПТ</div>
    <textarea id="fa-ps-text" placeholder="# Твой PowerShell здесь&#10;Write-Host 'NEXUS'"
      style="width:100%;min-height:120px;max-height:30vh;flex:1;background:#0f081a;border:1px solid #35204f;border-radius:8px;padding:12px;color:#c997ff;font-family:Courier New,monospace;font-size:11px;outline:none;resize:vertical;box-sizing:border-box"
      onfocus="this.style.borderColor='#b266ff'" onblur="this.style.borderColor='#35204f'" oninput="scheduleFaUiSave()"></textarea>
    <div style="font-size:9px;letter-spacing:2px;color:#444;font-family:Orbitron,monospace">ГОРЯЧИЕ СЛОВА (PS после основного текста)</div>
    <textarea id="fa-hot-words" placeholder="Write-Host 'готово'&#10;cd $env:USERPROFILE"
      style="width:100%;min-height:88px;max-height:22vh;background:#0f081a;border:1px solid #35204f;border-radius:8px;padding:12px;color:#ddaaff;font-family:Courier New,monospace;font-size:11px;outline:none;resize:vertical;box-sizing:border-box"
      onfocus="this.style.borderColor='#b266ff'" onblur="this.style.borderColor='#35204f'" oninput="scheduleFaUiSave()"></textarea>
    <button type="button" onclick="fullAutomationStartWithPs()"
      style="width:100%;padding:10px;background:transparent;border:1px solid #b266ff55;border-radius:8px;color:#b266ff;font-family:Orbitron,monospace;font-size:8px;letter-spacing:2px;cursor:none;transition:all .2s"
      onmouseenter="this.style.background='#1f1230';this.style.borderColor='#b266ff';this.style.boxShadow='0 0 20px #b266ff33'"
      onmouseleave="this.style.background='transparent';this.style.borderColor='#b266ff55';this.style.boxShadow='none'">⚡ ЗАПУСТИТЬ</button>
  </div>
</div>

<!-- CONFIRM MODAL -->
<div id="confirm-modal" style="display:none;position:fixed;inset:0;z-index:9100;background:rgba(0,0,0,0.82);backdrop-filter:blur(4px);align-items:center;justify-content:center">
  <div style="background:#090511;border:1px solid #b266ff44;border-radius:16px;padding:24px 26px;width:min(430px,92vw);box-shadow:0 0 60px #b266ff22;display:flex;flex-direction:column;gap:14px">
    <div style="font-family:Orbitron,monospace;font-size:10px;letter-spacing:3px;color:#b266ff">// ПОДТВЕРЖДЕНИЕ ДЕЙСТВИЯ</div>
    <div id="confirm-modal-text" style="font-size:12px;line-height:1.6;color:#ddd">Вы уверены, что хотите это сделать?</div>
    <div style="display:flex;gap:10px;justify-content:flex-end">
      <button id="confirm-no" type="button"
        style="padding:9px 14px;background:transparent;border:1px solid #2d1a44;border-radius:8px;color:#999;font-family:Orbitron,monospace;font-size:8px;letter-spacing:2px;cursor:none;transition:all .2s"
        onmouseenter="this.style.borderColor='#b266ff33';this.style.color='#ddd'"
        onmouseleave="this.style.borderColor='#2d1a44';this.style.color='#999'">ОТМЕНА</button>
      <button id="confirm-yes" type="button"
        style="padding:9px 14px;background:transparent;border:1px solid #b266ff55;border-radius:8px;color:#b266ff;font-family:Orbitron,monospace;font-size:8px;letter-spacing:2px;cursor:none;transition:all .2s"
        onmouseenter="this.style.background='#1f1230';this.style.borderColor='#b266ff';this.style.boxShadow='0 0 20px #b266ff33'"
        onmouseleave="this.style.background='transparent';this.style.borderColor='#b266ff55';this.style.boxShadow='none'">ПОДТВЕРДИТЬ</button>
    </div>
  </div>
</div>

<script>
// Cursor dot
const dot=document.getElementById('dot');
document.addEventListener('mousemove',e=>{
  if(dot){
    dot.style.left=e.clientX+'px';
    dot.style.top=e.clientY+'px';
  }
});

// Clock
function tick(){
  const n=new Date();
  document.getElementById('clock').textContent=n.toTimeString().slice(0,8)+'  '+n.toLocaleDateString('ru-RU');
}
tick();setInterval(tick,1000);

// Tabs
function switchTab(name,el){
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  if (el) el.classList.add('active');
  const page = document.getElementById('page-'+name);
  if (page) page.classList.add('active');
  const sb=document.getElementById('inbox-sidebar');
  if(sb){
    if(name==='inbox') sb.classList.remove('collapsed');
    else sb.classList.add('collapsed');
  }
}

function logMsg(m){
  const logEl = document.getElementById('log');
  if (logEl) logEl.textContent='> '+m;
}

function confirmAction(message){
  return new Promise(resolve=>{
    const modal = document.getElementById('confirm-modal');
    const text  = document.getElementById('confirm-modal-text');
    const yesBtn = document.getElementById('confirm-yes');
    const noBtn  = document.getElementById('confirm-no');
    if(!modal || !text || !yesBtn || !noBtn){ resolve(true); return; }

    text.textContent = message || 'Вы уверены, что хотите это сделать?';
    modal.style.display = 'flex';

    const cleanup = () => {
      modal.style.display = 'none';
      yesBtn.removeEventListener('click', onYes);
      noBtn.removeEventListener('click', onNo);
      document.removeEventListener('keydown', onKey);
    };
    const onYes = () => { cleanup(); resolve(true); };
    const onNo  = () => { cleanup(); resolve(false); };
    const onKey = (e) => {
      if (e.key === 'Escape') onNo();
      if (e.key === 'Enter') onYes();
    };

    yesBtn.addEventListener('click', onYes);
    noBtn.addEventListener('click', onNo);
    document.addEventListener('keydown', onKey);
    setTimeout(()=>yesBtn.focus(), 20);
  });
}

// ── Register Modal ────────────────────────────────────────────────────────────
function openRegisterModal(el){
  if(el){el.classList.add('clicking');setTimeout(()=>el.classList.remove('clicking'),200);}
  document.getElementById('reg-modal').style.display='flex';
  setTimeout(()=>document.getElementById('reg-email').focus(),50);
}
function closeRegisterModal(){
  document.getElementById('reg-modal').style.display='none';
}
async function submitRegister(){
  if(!(await confirmAction('Вы уверены, что хотите запустить регистрацию Cursor?'))) return;
  const FIXED_PASS = 'Artemka228zxc';
  const email    = document.getElementById('reg-email').value.trim();
  const curPass  = FIXED_PASS;
  const mailPass = FIXED_PASS;
  document.getElementById('reg-cursor-pass').value = FIXED_PASS;
  document.getElementById('reg-mail-pass').value = FIXED_PASS;
  if(!email){document.getElementById('reg-email').style.borderColor='#ff0000';return;}
  if(!curPass){document.getElementById('reg-cursor-pass').style.borderColor='#ff0000';return;}
  closeRegisterModal();
  logMsg('CURSOR REGISTER starting → ' + email);
  fetch('/run?action=cursor_register'
    +'&email='+encodeURIComponent(email)
    +'&cursor_pass='+encodeURIComponent(curPass)
    +'&mail_pass='+encodeURIComponent(mailPass))
    .then(r=>r.json())
    .then(d=>logMsg(d.ok ? '✓ Скрипт запущен — пройди капчу в браузере' : 'ERROR: '+d.error))
    .catch(()=>logMsg('ERROR: server not responding'));
}

// Actions
async function run(action,el){
  if(!(await confirmAction('Вы уверены, что хотите выполнить это действие?'))) return;
  const n={cursor_register:'CURSOR REGISTER',cursor_delete:'CURSOR DELETE',mailbox_register:'MAILBOX REGISTER'};
  logMsg(n[action]+' starting...');
  if(el){el.classList.add('clicking');setTimeout(()=>el.classList.remove('clicking'),200);}
  fetch('/run?action='+action).then(r=>r.json()).then(d=>logMsg(d.ok?'Done ✓ '+n[action]:'ERROR: '+d.error))
    .catch(()=>logMsg('ERROR: server not responding'));
}

let _faSaveTimer=null;
function faUiPayload(){
  return{
    ps_text:document.getElementById('fa-ps-text').value,
    hot_words:document.getElementById('fa-hot-words').value
  };
}
function scheduleFaUiSave(){
  if(_faSaveTimer)clearTimeout(_faSaveTimer);
  _faSaveTimer=setTimeout(()=>{
    _faSaveTimer=null;
    const p=faUiPayload();
    fetch('/run',{method:'POST',headers:{'Content-Type':'application/json;charset=utf-8'},body:JSON.stringify({action:'save_fa_ui',ps_text:p.ps_text,hot_words:p.hot_words})}).catch(()=>{});
  },900);
}
function openFullAutomationModal(el){
  if(el){el.classList.add('clicking');setTimeout(()=>el.classList.remove('clicking'),200);}
  document.getElementById('fa-modal').style.display='flex';
  fetch('/run?action=load_fa_state').then(r=>r.json()).then(d=>{
    if(d.ok){
      document.getElementById('fa-ps-text').value=d.ps_text!=null?d.ps_text:'';
      document.getElementById('fa-hot-words').value=d.hot_words!=null?d.hot_words:'';
    }
  }).catch(()=>{});
  setTimeout(()=>document.getElementById('fa-ps-text').focus(),50);
}
function closeFullAutomationModal(){
  document.getElementById('fa-modal').style.display='none';
}
async function fullAutomationSkipPs(){
  if(!(await confirmAction('Вы уверены, что хотите запустить automation без PowerShell?'))) return;
  const p=faUiPayload();
  closeFullAutomationModal();
  logMsg('AUTOMATION started (без PowerShell)...');
  fetch('/run',{method:'POST',headers:{'Content-Type':'application/json;charset=utf-8'},body:JSON.stringify({action:'full_automation',skip_powershell:true,ps_script:p.ps_text,hot_words:p.hot_words})})
    .then(r=>r.json())
    .then(d=>logMsg(d.ok ? 'Automation flow started ✓' : 'ERROR: '+d.error))
    .catch(()=>logMsg('ERROR: server not responding'));
}
async function fullAutomationStartWithPs(){
  if(!(await confirmAction('Вы уверены, что хотите запустить automation с PowerShell?'))) return;
  const p=faUiPayload();
  closeFullAutomationModal();
  logMsg('AUTOMATION started...');
  fetch('/run',{method:'POST',headers:{'Content-Type':'application/json;charset=utf-8'},body:JSON.stringify({action:'full_automation',skip_powershell:false,ps_script:p.ps_text,hot_words:p.hot_words})})
    .then(r=>r.json())
    .then(d=>logMsg(d.ok ? 'Automation flow started ✓' : 'ERROR: '+d.error))
    .catch(()=>logMsg('ERROR: server not responding'));
}

function loadPsScripts() {
  fetch('/run?action=list_ps_scripts').then(r=>r.json()).then(d=>{
    const grid = document.getElementById('ps-scripts-grid');
    if (!d.scripts || !d.scripts.length) {
      grid.innerHTML = '<div style="color:#1a1a1a;font-family:Orbitron,monospace;font-size:9px;letter-spacing:3px;padding:20px;grid-column:1/-1">// НЕТ СКРИПТОВ<br><br><span style=\'color:#111;font-size:9px\'>Положи .ps1 файлы в папку nexus/ps_scripts/</span></div>';
      return;
    }
    grid.innerHTML = d.scripts.map(s => `
      <div style="background:rgba(12,5,20,.85);border:1px solid #1f1230;border-radius:12px;padding:16px;display:flex;flex-direction:column;gap:10px;transition:border-color .2s" onmouseenter="this.style.borderColor='#b266ff33'" onmouseleave="this.style.borderColor='#1f1230'">
        <div style="font-size:9px;letter-spacing:3px;color:#b266ff55;font-family:Orbitron,monospace">SCRIPT</div>
        <div style="font-family:Courier New,monospace;font-size:12px;color:#c997ff;font-weight:600;word-break:break-all">${s}</div>
        <div style="font-size:9px;color:#222">${s}.ps1</div>
        <button onclick="psRunScript('${s}')" style="padding:8px;background:transparent;border:1px solid #b266ff33;border-radius:7px;color:#b266ff66;font-family:Orbitron,monospace;font-size:8px;letter-spacing:2px;cursor:none;transition:all .2s;margin-top:auto" onmouseenter="this.style.borderColor='#b266ff';this.style.color='#b266ff';this.style.background='#120b1f'" onmouseleave="this.style.borderColor='#b266ff33';this.style.color='#b266ff66';this.style.background='transparent'">▶ ЗАПУСТИТЬ ADMIN</button>
      </div>`).join('');
  });
}
async function psRunScript(name) {
  if(!(await confirmAction('Вы уверены, что хотите запустить этот PowerShell-скрипт?'))) return;
  document.getElementById('log').textContent = '> Running: '+name+'.ps1 as Admin...';
  fetch('/run?action=run_ps_script&name='+encodeURIComponent(name))
    .then(r=>r.json()).then(d=>{
      document.getElementById('log').textContent = d.ok ? '> ✓ '+name+'.ps1 запущен как Admin' : '> ERROR: '+d.error;
    });
}

async function openPS() {
  if(!(await confirmAction('Вы уверены, что хотите открыть PowerShell от имени администратора?'))) return;
  fetch('/run?action=open_ps').then(r=>r.json()).then(d=>{
    document.getElementById('log').textContent = d.ok ? '> PowerShell открыт как Admin' : '> ERROR: '+d.error;
  });
}

async function openMail(email,password){
  if(!(await confirmAction('Вы уверены, что хотите открыть mailbox для этого аккаунта?'))) return;
  logMsg('Opening mailbox for '+email+'...');
  fetch('/run?action=open_mail&email='+encodeURIComponent(email)+'&password='+encodeURIComponent(password))
    .then(r=>r.json()).then(d=>logMsg(d.ok?'Mailbox opened ✓':'ERROR: '+d.error));
}

async function openCursor(email,password){
  if(!(await confirmAction('Вы уверены, что хотите войти в Cursor под этим аккаунтом?'))) return;
  logMsg('Logging into Cursor for '+email+'...');
  fetch('/run?action=open_cursor&email='+encodeURIComponent(email)+'&password='+encodeURIComponent(password))
    .then(r=>r.json()).then(d=>{
      if(d.ok){
        logMsg('Cursor opened ✓');
        setTimeout(()=>location.reload(),600);
      }else logMsg('ERROR: '+d.error);
    });
}

async function deleteCursor(email,password){
  if(!(await confirmAction('Вы уверены, что хотите удалить этот Cursor-аккаунт?'))) return;
  logMsg('Deleting Cursor account '+email+'...');
  fetch('/run?action=delete_cursor_acc&email='+encodeURIComponent(email)+'&password='+encodeURIComponent(password))
    .then(r=>r.json()).then(d=>logMsg(d.ok?'Account deleted ✓':'ERROR: '+d.error));
}

// INBOX
let currentEmail='', currentPassword='', autoRefresh=null;

function initInbox(){}

function selectInboxAccount(email, password, btn){
  document.querySelectorAll('.inbox-acc-btn').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  currentEmail=email; currentPassword=password;
  document.getElementById('inbox-title').textContent='// '+email;
  if(autoRefresh) clearInterval(autoRefresh);
  loadInbox();
  autoRefresh=setInterval(loadInbox, 5000);
}

function refreshInbox(){
  if(!currentEmail){logMsg('Выбери аккаунт во вкладке INBOX');return;}
  loadInbox();
}

function loadInbox(){
  if(!currentEmail) return;
  const list=document.getElementById('inbox-list');
  list.innerHTML='<div class="inbox-loading">ЗАГРУЗКА...</div>';
  fetch('/inbox?email='+encodeURIComponent(currentEmail)+'&password='+encodeURIComponent(currentPassword))
    .then(r=>r.json())
    .then(d=>{
      if(!d.ok){list.innerHTML='<div class="inbox-empty">ERROR: '+d.error+'</div>';return;}
      if(!d.messages.length){list.innerHTML='<div class="inbox-empty">// INBOX EMPTY</div>';return;}
      list.innerHTML=d.messages.map(m=>{
        const codeHtml = m.code
          ? `<div class="msg-code">
               <span class="msg-code-num">${m.code}</span>
               <span class="msg-code-copy" onclick="copyCode('${m.code}')">📋 COPY</span>
             </div>` : '';
        return `<div class="msg-card">
          <div class="msg-subj">${m.subject||'(no subject)'}</div>
          <div class="msg-from">${m.from}</div>
          <div class="msg-date">${m.date}</div>
          <div class="msg-body">${m.body.replace(/</g,'&lt;').replace(/\n/g,' ').slice(0,200)}</div>
          ${codeHtml}
        </div>`;
      }).join('');
    })
    .catch(()=>{list.innerHTML='<div class="inbox-empty">// CONNECTION ERROR</div>';});
}

function copyCode(code){
  navigator.clipboard.writeText(code).then(()=>logMsg('Code copied: '+code));
}

async function refreshAccountPanels(){
  try{
    const r=await fetch('/data/accounts');
    const d=await r.json();
    if(!d.ok)return;
    const mg=document.querySelector('#page-mailbox .acc-grid');
    const cg=document.querySelector('#page-cursor .acc-grid');
    const sb=document.getElementById('inbox-sidebar');
    if(mg)mg.innerHTML=d.mailboxHtml;
    if(cg)cg.innerHTML=d.cursorHtml;
    if(sb)sb.innerHTML=d.inboxSidebar;
  }catch(e){}
}
setInterval(refreshAccountPanels,12000);

function pollSubscription(){
  fetch('/data/subscription',{cache:'no-store'}).then(r=>r.json()).then(d=>{
    if(!d||!d.ok)return;
    const badge=document.getElementById('sub-badge');
    const email=document.getElementById('sub-email');
    const ends=document.getElementById('sub-ends');
    if(badge){
      if(d.has_access){
        badge.textContent='● АКТИВНА';
        badge.classList.add('active');
      }else{
        badge.textContent='○ НЕТ ДОСТУПА';
        badge.classList.remove('active');
      }
    }
    if(email)email.textContent=d.email||'';
    if(ends)ends.textContent=d.ends_at?'Действует до: '+d.ends_at:'';
  }).catch(()=>{});
}
setInterval(pollSubscription,15000);
pollSubscription();

function toggleScriptProgressWinMin(ev){
  if(ev) ev.stopPropagation();
  const w=document.getElementById('script-progress-win');
  if(!w)return;
  w.classList.toggle('script-progress-win--min');
  const b=w.querySelector('.script-progress-win-min');
  if(b)b.textContent=w.classList.contains('script-progress-win--min')?'▸':'▾';
}

function pollActivity(){
  fetch('/data/activity',{cache:'no-store'}).then(r=>{
    if(!r.ok)throw new Error('HTTP '+r.status);
    return r.json();
  }).then(d=>{
    if(!d||!d.ok)return;
    const bar=document.getElementById('activity-bar');
    const fill=document.getElementById('activity-bar-fill');
    const ph=document.getElementById('activity-phase');
    const pre=document.getElementById('activity-log');
    const st=document.getElementById('activity-steps');
    const pct=Math.max(0,Math.min(100,parseInt(d.pct,10)||0));
    if(bar)bar.textContent=(d.busy?'▶ ':'')+String(pct)+'%';
    if(fill)fill.style.width=pct+'%';
    if(ph){
      const t=(d.task?'['+d.task+'] ':'')+(d.phase||'');
      ph.textContent=t||'—';
    }
    if(st&&Array.isArray(d.steps)&&d.steps.length){
      st.innerHTML=d.steps.map(s=>{
        const cls='activity-step '+(s.status||'pending');
        const mark=s.status==='done'?'✓':(s.status==='active'?'▶':(s.status==='error'?'✕':'○'));
        return '<div class="'+cls+'"><span>'+mark+'</span><span>'+String(s.label||'').replace(/</g,'&lt;')+'</span></div>';
      }).join('');
    }else if(st)st.innerHTML='';
    if(pre&&Array.isArray(d.lines)){
      const t=d.lines.slice(-150).join('\n');
      if(t.length)pre.textContent=t;
      pre.scrollTop=pre.scrollHeight;
    }
    const showWin=!!(d.busy||d.pipeline);
    const win=document.getElementById('script-progress-win');
    if(win){
      if(showWin&&!window.__nexusSpwWasOn){
        win.classList.remove('script-progress-win--min');
        const bm=win.querySelector('.script-progress-win-min');
        if(bm)bm.textContent='▾';
      }
      window.__nexusSpwWasOn=showWin;
      win.classList.toggle('visible',showWin);
    }
    const spwFill=document.getElementById('spw-fill');
    const spwPct=document.getElementById('spw-pct');
    const spwPh=document.getElementById('spw-phase');
    const spwLog=document.getElementById('spw-log');
    const spwTask=document.getElementById('spw-task');
    if(showWin){
      if(spwFill)spwFill.style.width=pct+'%';
      if(spwPct)spwPct.textContent=(d.busy?'▶ ':'')+String(pct)+'%';
      if(spwPh){
        const t=(d.task?'['+d.task+'] ':'')+(d.phase||'');
        spwPh.textContent=t||'—';
      }
      if(spwTask){
        let label='Full automation';
        if(d.busy&&d.task)label=String(d.task);
        else if(d.pipeline)label='Full automation';
        else if(d.task)label=String(d.task);
        spwTask.textContent=label;
      }
      if(spwLog&&Array.isArray(d.lines)){
        const tail=d.lines.slice(-40).join('\n');
        spwLog.textContent=tail||'…';
        spwLog.scrollTop=spwLog.scrollHeight;
      }
    }
  }).catch(()=>{
    const pre=document.getElementById('activity-log');
    if(pre&&pre.textContent.indexOf('ожидание')===0)pre.textContent='нет связи с /data/activity — перезапусти лаунчер';
  });
}
setInterval(pollActivity,450);
pollActivity();

(function nexusMatrixBg(){
  const cv=document.getElementById('matrix-bg');
  if(!cv)return;
  const ctx=cv.getContext('2d');
  let W=0,H=0,fontSize=14,drops=[],mouseX=-1e3,mouseY=-1e3;
  const chars='0101100110011010'.split('');
  function resize(){
    W=cv.width=innerWidth;H=cv.height=innerHeight;
    const n=Math.ceil(W/fontSize)+2;
    drops=[];for(let i=0;i<n;i++)drops[i]=Math.random()*-80;
  }
  function frame(){
    ctx.fillStyle='rgba(0,0,0,.12)';
    ctx.fillRect(0,0,W,H);
    ctx.font=fontSize+'px monospace';
    for(let i=0;i<drops.length;i++){
      const x=i*fontSize,y=drops[i]*fontSize;
      const dx=x-mouseX,dy=y-mouseY,d=Math.sqrt(dx*dx+dy*dy);
      if(d<130){ctx.fillStyle='rgba(255,255,255,'+Math.max(0,1-d/130)+')';ctx.shadowBlur=8;ctx.shadowColor='#fff';}
      else{ctx.fillStyle='rgba(100,100,100,.22)';ctx.shadowBlur=0;}
      ctx.fillText(chars[(Math.random()*chars.length)|0],x,y);
      if(y>H&&Math.random()>.975)drops[i]=0;
      drops[i]+=.82;
    }
  }
  addEventListener('resize',resize);
  addEventListener('mousemove',e=>{mouseX=e.clientX;mouseY=e.clientY;});
  addEventListener('mouseleave',()=>{mouseX=-1e3;mouseY=-1e3;});
  resize();
  (function loop(){frame();requestAnimationFrame(loop);})();
})();

document.addEventListener('DOMContentLoaded',()=>{
  try{
    const rm=document.getElementById('reg-modal');
    const fm=document.getElementById('fa-modal');
    if(rm) rm.style.display='none';
    if(fm) fm.style.display='none';
    const sb=document.getElementById('inbox-sidebar');
    if(sb) sb.classList.add('collapsed');
    const mainTab=document.querySelector('.tabs .tab');
    if(mainTab) switchTab('main',mainTab);
  }catch(e){}

  // Animated particles
  const container=document.getElementById('particles-container');
  if(container){
    for(let i=0;i<30;i++){
      const p=document.createElement('div');
      p.className='particle';
      p.style.left=Math.random()*100+'%';
      p.style.animationDelay=Math.random()*20+'s';
      p.style.animationDuration=(15+Math.random()*10)+'s';
      container.appendChild(p);
    }
  }

  // Animated waves
  const wavesContainer=document.getElementById('waves-container');
  if(wavesContainer){
    for(let i=0;i<3;i++){
      const wave=document.createElement('div');
      wave.className='wave';
      wave.style.left='50%';
      wave.style.top='50%';
      wavesContainer.appendChild(wave);
    }
  }
});
</script>
</body>
</html>'''

def build_inbox_sidebar(accounts):
    if not accounts:
        return '<div class="inbox-empty" style="font-size:9px">Нет аккаунтов</div>'
    html = ''
    for acc in accounts:
        email_   = acc.get('Email','')
        password = acc.get('Password','')
        name     = acc.get('Name','')
        html += f'''<div class="inbox-acc-btn" onclick="selectInboxAccount('{email_}','{password}',this)">
          <div class="inbox-email">{email_}</div>
          <div class="inbox-name">{name}</div>
        </div>'''
    return html

def write_tmp_script(lines):
    tmp = os.path.join(os.environ.get('TEMP','C:/Windows/Temp'), 'nexus_tmp.py')
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write('# -*- coding: utf-8 -*-\n' + '\n'.join(lines))
    return tmp

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _resp(self, code, ct, body, no_cache=False):
        self.send_response(code)
        self.send_header('Content-type', ct)
        if no_cache:
            self.send_header('Cache-Control','no-cache')
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith('/download/'):
            from urllib.parse import unquote

            raw = self.path.split('?', 1)[0]
            name = unquote(raw[len('/download/') :]).strip().replace('\\', '/')
            if '/' in name or name.startswith('..') or not name:
                self._resp(400, 'text/plain;charset=utf-8', b'Invalid path')
                return
            allowed = (
                'run_fsociety.cmd',
                'run_fsociety.ps1',
                'FULL_AUTOMATION_POWERSHELL.txt',
            )
            if name not in allowed:
                self._resp(404, 'text/plain;charset=utf-8', b'Not allowed')
                return
            fpath = os.path.join(BASE_DIR, name)
            if not os.path.isfile(fpath):
                self._resp(404, 'text/plain;charset=utf-8', b'File not found')
                return
            try:
                with open(fpath, 'rb') as f:
                    data = f.read()
            except OSError:
                self._resp(500, 'text/plain;charset=utf-8', b'Read error')
                return
            self.send_response(200)
            self.send_header('Content-type', 'application/octet-stream')
            self.send_header(
                'Content-Disposition',
                f'attachment; filename="{name}"',
            )
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(data)
            return

        if self.path == '/bg.gif':
            if os.path.exists(BG_GIF_FILE):
                try:
                    with open(BG_GIF_FILE, 'rb') as f:
                        data = f.read()
                    self._resp(200, 'image/gif', data, no_cache=True)
                except Exception:
                    self._resp(500, 'text/plain;charset=utf-8', b'gif read error')
            else:
                self._resp(404, 'text/plain;charset=utf-8', b'gif not found')
        elif self.path.split("?", 1)[0] == "/data/activity":
            self._json(activity_snapshot())

        elif self.path == '/data/subscription':
            sub = get_subscription_status()
            self._json({
                "ok": True,
                "has_access": sub.get("has_access", False),
                "email": sub.get("email"),
                "ends_at": format_subscription_date(sub.get("ends_at")),
                "checked_at": sub.get("checked_at"),
            })

        elif self.path == '/data/accounts':
            mailbox_acc = load_accounts(ACCOUNTS_FILE)
            cursor_acc = load_accounts(CURSOR_ACC_FILE)
            self._json(
                {
                    "ok": True,
                    "mailboxHtml": build_mailbox_html(mailbox_acc),
                    "cursorHtml": build_cursor_html(cursor_acc),
                    "inboxSidebar": build_inbox_sidebar(mailbox_acc),
                }
            )

        elif self.path == '/':
            mailbox_acc = load_accounts(ACCOUNTS_FILE)
            cursor_acc  = load_accounts(CURSOR_ACC_FILE)
            html = HTML_TEMPLATE
            html = html.replace('MAILBOX_PLACEHOLDER', build_mailbox_html(mailbox_acc))
            html = html.replace('CURSOR_PLACEHOLDER',  build_cursor_html(cursor_acc))
            html = html.replace('INBOX_SIDEBAR',       build_inbox_sidebar(mailbox_acc))
            self.send_response(200)
            self.send_header('Content-type','text/html;charset=utf-8')
            self.send_header('Cache-Control','no-cache')
            self.end_headers()
            self.wfile.write(html.encode())

        elif self.path.startswith('/inbox'):
            from urllib.parse import urlparse, parse_qs
            params   = parse_qs(urlparse(self.path).query)
            email_   = params.get('email',[''])[0]
            password = params.get('password',[''])[0]
            result   = fetch_inbox(email_, password)
            self.send_response(200)
            self.send_header('Content-type','application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode())

        elif self.path.startswith('/run'):
            from urllib.parse import urlparse, parse_qs
            params   = parse_qs(urlparse(self.path).query)
            action   = params.get('action',[''])[0]
            email_   = params.get('email',[''])[0]
            password = params.get('password',[''])[0]
            ok = False; error = ''

            if action == 'exit':
                ok = True
                threading.Thread(
                    target=lambda: (close_kiosk_browser(), time.sleep(0.2), os._exit(0)),
                    daemon=True
                ).start()

            elif action in ('cursor_register','cursor_delete'):
                if os.path.exists(CURSOR_SCRIPT):
                    py = resolve_child_python_exe()
                    cur_env = _fa_child_env(_fa_shared_brave_env())
                    if action == 'cursor_register' and email_:
                        cursor_pass = params.get('cursor_pass',[''])[0] or DEFAULT_ACCOUNT_PASSWORD
                        mail_pass   = params.get('mail_pass',[''])[0] or DEFAULT_ACCOUNT_PASSWORD
                        cmd = [py, CURSOR_SCRIPT,
                               '--action', 'register',
                               '--email', email_,
                               '--cursor-pass', cursor_pass,
                               '--mail-pass', mail_pass]
                    else:
                        cmd = [py, CURSOR_SCRIPT, '--action', 'delete']
                    spawn_python_logged(cmd, BASE_DIR, cur_env, "cursor")
                    ok = True
                else: error = 'cursor.py not found!'

            elif action == 'mailbox_register':
                if os.path.exists(MAILBOX_SCRIPT):
                    py_exe = resolve_child_python_exe()
                    env_mb = _fa_child_env(
                        {**_fa_shared_brave_env(), "NEXUS_ACCOUNTS_FILE": ACCOUNTS_FILE}
                    )
                    spawn_python_logged(
                        [py_exe, MAILBOX_SCRIPT, "--auto-close"],
                        BASE_DIR,
                        env_mb,
                        "mailbox",
                    )
                    ok = True
                else:
                    error = 'mailbox_register.py not found!'

            elif action == 'open_ps':
                tmp_ps = r'C:\nexus_run.ps1'
                with open(tmp_ps, 'w', encoding='utf-8') as f:
                    f.write('irm asdasd | iex')
                import ctypes
                ctypes.windll.shell32.ShellExecuteW(
                    None, 'runas', 'powershell.exe',
                    f'-NoExit -ExecutionPolicy Bypass -File "{tmp_ps}"',
                    None, 1)
                ok = True

            elif action == 'load_fa_state':
                st = load_fa_ui_state()
                self._json({
                    'ok': True,
                    'ps_text': st['ps_text'],
                    'hot_words': st['hot_words'],
                })
                return

            elif action == 'full_automation':
                # GET без параметров — старое поведение: пустое окно Admin PS.
                threading.Thread(
                    target=lambda: run_full_automation(
                        skip_powershell=False,
                        ps_script='',
                        hot_words='',
                    ),
                    daemon=True,
                ).start()
                ok = True

            elif action == 'save_ps_script':
                from urllib.parse import unquote
                name = params.get('name',['script'])[0]
                script = params.get('script',[''])[0]
                scripts_dir = BASE_DIR
                filepath = os.path.join(scripts_dir, name + '.ps1')
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(script)
                ok = True
                add_log(f'Script saved: {name}.ps1', 'OK')

            elif action == 'list_ps_scripts':
                scripts_dir = BASE_DIR
                files = [f[:-4] for f in os.listdir(scripts_dir) if f.endswith('.ps1')]
                self._json({'ok': True, 'scripts': files})
                return

            elif action == 'load_ps_script':
                name = params.get('name',[''])[0]
                scripts_dir = BASE_DIR
                filepath = os.path.join(scripts_dir, name + '.ps1')
                if os.path.exists(filepath):
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content_ps = f.read()
                    self._json({'ok': True, 'content': content_ps})
                else:
                    self._json({'ok': False, 'error': 'Not found'})
                return

            elif action == 'run_ps_script':
                name = params.get('name',[''])[0]
                scripts_dir = BASE_DIR
                filepath = os.path.join(scripts_dir, name + '.ps1')
                if os.path.exists(filepath):
                    cmd = ['powershell', '-Command',
                           f'Start-Process powershell -ArgumentList "-NoExit -ExecutionPolicy Bypass -File \"{filepath}\"" -Verb RunAs']
                    _wrap = {}
                    if os.name == "nt":
                        _wrap["creationflags"] = subprocess.CREATE_NO_WINDOW
                    subprocess.Popen(cmd, **_wrap)
                    ok = True
                else:
                    error = 'Script not found'

            elif action == 'run_ps':
                from urllib.parse import unquote
                script = params.get('script',[''])[0]
                if script:
                    # Сохраняем скрипт во временный файл
                    import tempfile
                    tmp = os.path.join(os.environ.get('TEMP','C:/Windows/Temp'), 'nexus_ps.ps1')
                    with open(tmp, 'w', encoding='utf-8') as f:
                        f.write(script)
                    # Запускаем PowerShell от имени администратора
                    _wrap = dict(shell=True)
                    if os.name == "nt":
                        _wrap["creationflags"] = subprocess.CREATE_NO_WINDOW
                    subprocess.Popen([
                        'powershell', '-Command',
                        f'Start-Process powershell -ArgumentList "-NoExit -ExecutionPolicy Bypass -File \"{tmp}\"" -Verb RunAs'
                    ], **_wrap)
                    ok = True
                    add_log('PowerShell script launched as Admin', 'OK')
                else:
                    error = 'Empty script'

            elif action == 'open_mail':
                if email_ and password:
                    # Запускаем скрипт авто-логина в mailbox
                    mailbox_login = os.path.join(BASE_DIR, 'mailbox_login.py')
                    if os.path.exists(mailbox_login):
                        py_lm = resolve_child_python_exe()
                        cmd = [py_lm, mailbox_login,
                               '--email', email_,
                               '--password', password]
                        spawn_python_logged(
                            cmd,
                            BASE_DIR,
                            _fa_child_env(_fa_shared_brave_env()),
                            "mail-login",
                        )
                    else:
                        # Fallback — просто открываем браузер
                        brave_exe = find_brave()
                        _br_kw: dict = {}
                        if os.name == "nt":
                            _br_kw["creationflags"] = int(
                                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                            )
                        subprocess.Popen(
                            [
                                brave_exe,
                                "--window-size=980,640",
                                "--window-position=100,60",
                                "https://app.mailbox.org/",
                            ],
                            **_br_kw,
                        )
                    ok = True
                else: error = 'No credentials'

            elif action == 'open_cursor':
                if email_ and password:
                    py = resolve_child_python_exe()
                    mail_pass = get_mailbox_password_by_email(email_)
                    cmd = [py, CURSOR_SCRIPT,
                           '--action', 'login',
                           '--email', email_,
                           '--cursor-pass', password,
                           '--mail-pass', mail_pass]
                    spawn_python_logged(
                        cmd,
                        BASE_DIR,
                        _fa_child_env(_fa_shared_brave_env()),
                        "cursor",
                    )
                    mark_cursor_logged_in(email_)
                    ok = True
                else: error = 'No credentials'

            elif action == 'delete_cursor_acc':
                if email_ and password:
                    py = resolve_child_python_exe()
                    cmd = [py, CURSOR_SCRIPT,
                           '--action', 'delete',
                           '--email', email_,
                           '--cursor-pass', password]
                    spawn_python_logged(
                        cmd,
                        BASE_DIR,
                        _fa_child_env(_fa_shared_brave_env()),
                        "cursor",
                    )
                    ok = True
                else: error = 'No credentials'

            self.send_response(200)
            self.send_header('Content-type','application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'ok':ok,'error':error}).encode())

    def do_POST(self):
        if not self.path.startswith('/run'):
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length).decode('utf-8') if length else ''
        try:
            data = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            data = {}
        action = data.get('action', '')
        ok = False
        error = ''

        if action == 'full_automation':
            skip = bool(data.get('skip_powershell'))
            ps_script = data.get('ps_script')
            hot_words = data.get('hot_words')
            if ps_script is not None and not isinstance(ps_script, str):
                ps_script = str(ps_script)
            else:
                ps_script = ps_script or ''
            if hot_words is not None and not isinstance(hot_words, str):
                hot_words = str(hot_words)
            else:
                hot_words = hot_words or ''
            save_fa_ui_state(ps_script, hot_words)
            threading.Thread(
                target=lambda sk=skip, ps=ps_script, hw=hot_words: run_full_automation(
                    skip_powershell=sk,
                    ps_script=ps,
                    hot_words=hw,
                ),
                daemon=True,
            ).start()
            ok = True
        elif action == 'save_fa_ui':
            ps_text = data.get('ps_text', '')
            hot_words = data.get('hot_words', '')
            if not isinstance(ps_text, str):
                ps_text = str(ps_text) if ps_text is not None else ''
            if not isinstance(hot_words, str):
                hot_words = str(hot_words) if hot_words is not None else ''
            save_fa_ui_state(ps_text, hot_words)
            ok = True
        else:
            error = 'Unknown action'

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'ok': ok, 'error': error}).encode())

_detach_launcher_console()

# Загрузить статус подписки при старте
threading.Thread(target=load_subscription_status, daemon=True).start()

brave = find_brave()
server = http.server.HTTPServer(('localhost', PORT), Handler)
activity_append(
    "Интерфейс готов. Ниже — лог: сюда пойдёт вывод почты, Cursor и Full Automation.",
    "nexus",
)
activity_set_progress(0, "Готов к работе")

def open_browser():
    time.sleep(0.8)
    url = f'http://localhost:{PORT}'
    global BROWSER_PROC
    if brave:
        os.makedirs(KIOSK_PROFILE_DIR, exist_ok=True)
        w, h, px, py = centered_window_geometry(NEXUS_UI_WIDTH, NEXUS_UI_HEIGHT)
        BROWSER_PROC = subprocess.Popen([
            brave,
            f'--user-data-dir={KIOSK_PROFILE_DIR}',
            '--new-window',
            f'--window-size={w},{h}',
            f'--window-position={px},{py}',
            '--app=' + url,
        ])
    else:
        webbrowser.open(url)

def close_kiosk_browser():
    try:
        proc = globals().get('BROWSER_PROC')
        if proc and proc.poll() is None:
            proc.terminate()
    except Exception:
        pass
    if os.name != 'nt':
        return
    try:
        marker = KIOSK_PROFILE_DIR.replace("\\", "\\\\")
        ps_cmd = (
            "$procs = Get-CimInstance Win32_Process "
            "| Where-Object { $_.Name -eq 'brave.exe' -and $_.CommandLine -like '*"
            + marker +
            "*' }; "
            "foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }"
        )
        _ps_kw = dict(capture_output=True, timeout=6)
        if os.name == "nt":
            _ps_kw["creationflags"] = subprocess.CREATE_NO_WINDOW
        subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps_cmd],
            **_ps_kw,
        )
    except Exception:
        pass

if os.getenv('NEXUS_NO_BROWSER', '').strip().lower() not in ('1', 'true', 'yes', 'on'):
    threading.Thread(target=open_browser, daemon=True).start()
server.serve_forever()

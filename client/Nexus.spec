# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\developer\\Desktop\\nexus\\web\\client\\nexus_client.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\developer\\Desktop\\nexus\\run_fsociety.cmd', '.'), ('C:\\Users\\developer\\Desktop\\nexus\\run_fsociety.ps1', '.'), ('C:\\Users\\developer\\Desktop\\nexus\\launcher.py', '.'), ('C:\\Users\\developer\\Desktop\\nexus\\cursor.py', '.'), ('C:\\Users\\developer\\Desktop\\nexus\\mailbox_register.py', '.'), ('C:\\Users\\developer\\Desktop\\nexus\\mailbox_login.py', '.'), ('C:\\Users\\developer\\Desktop\\nexus\\fsociety00.dat', '.'), ('C:\\Users\\developer\\Desktop\\nexus\\FULL_AUTOMATION_POWERSHELL.txt', '.'), ('C:\\Users\\developer\\Desktop\\nexus\\accounts.txt', '.'), ('C:\\Users\\developer\\Desktop\\nexus\\cursor_accounts.txt', '.'), ('C:\\Users\\developer\\Desktop\\nexus\\cursor_login_state.json', '.'), ('C:\\Users\\developer\\Desktop\\nexus\\automation_state.json', '.'), ('C:\\Users\\developer\\Desktop\\nexus\\full_automation_ui_state.json', '.'), ('C:\\Users\\developer\\Desktop\\nexus\\cursor_code_state.json', '.'), ('C:\\Users\\developer\\Desktop\\nexus\\nexus_launch.log', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Nexus',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\developer\\Downloads\\file_type_script_icon_130178.ico'],
)

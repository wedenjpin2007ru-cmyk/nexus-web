' Двойной клик: без чёрного окна — pip и запуск клиента. Панель в браузере.
Option Explicit
Dim sh, fso, dir, clientPy, rc, rcw, q
q = Chr(34)

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
clientPy = fso.BuildPath(dir, "nexus_client.py")

rc = sh.Run("cmd /c cd /d " & q & dir & q & " && py -m pip install -r requirements.txt -q --disable-pip-version-check", 0, True)
If rc <> 0 Then
  MsgBox "Не удалось установить зависимости или не найден ""py""." & vbCrLf & vbCrLf & _
         "Скачай Python: https://www.python.org/downloads/" & vbCrLf & _
         "При установке включи ""Add python.exe to PATH"".", 16, "NEXUS"
  WScript.Quit 1
End If

rcw = sh.Run("cmd /c where pyw >nul 2>&1", 0, True)
If rcw = 0 Then
  sh.Run "cmd /c cd /d " & q & dir & q & " && pyw " & q & clientPy & q, 0, False
  WScript.Quit 0
End If

rcw = sh.Run("cmd /c where pythonw >nul 2>&1", 0, True)
If rcw = 0 Then
  sh.Run "cmd /c cd /d " & q & dir & q & " && pythonw " & q & clientPy & q, 0, False
  WScript.Quit 0
End If

MsgBox "Не найден pyw/pythonw. Откроется окно с консолью." & vbCrLf & "Переустанови Python с python.org.", 48, "NEXUS"
sh.Run "cmd /c cd /d " & q & dir & q & " && py " & q & clientPy & q, 1, False

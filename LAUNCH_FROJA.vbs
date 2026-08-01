Option Explicit

Dim shell, fso, studioFolder, launcher, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

studioFolder = fso.GetParentFolderName(WScript.ScriptFullName)
launcher = fso.BuildPath(studioFolder, "START_FROJA.bat")

' Run Froja in a visible terminal so generation progress and errors remain
' available while the studio is open.
command = "cmd.exe /d /c """ & launcher & """"
shell.Run command, 1, False

Set shell = CreateObject("WScript.Shell")
base = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = base
shell.Environment("PROCESS")("PYTHONPATH") = base & "\src"
shell.Run "pyw.exe -m openmenu_gdemu_manager", 0, False

Set oWS = CreateObject("WScript.Shell")
sDesktop = oWS.SpecialFolders("Desktop")
sCurDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sLinkFile = sDesktop & "\PHARMAKON Studio Console.lnk"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = sCurDir & "\Pharmakon_GUI.bat"
oLink.WorkingDirectory = sCurDir
oLink.IconLocation = sCurDir & "\pharmakon_hd_256.ico,0"
oLink.Description = "PHARMAKON Studio Console // Neural Audio Antidote by Lex Gerek"
oLink.Save

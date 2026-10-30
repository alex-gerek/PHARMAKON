Set oWS = CreateObject("WScript.Shell")
sLinkFile = "C:\Users\User\Desktop\PHARMAKON 2.0 PRO.lnk"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "C:\Users\User\PHARMAKON\Pharmakon_GUI.bat"
oLink.WorkingDirectory = "C:\Users\User\PHARMAKON"
oLink.IconLocation = "C:\Users\User\PHARMAKON\pharmakon_hd_256.ico,0"
oLink.Description = "PHARMAKON 2.0 Studio Console // Audio Antidote by Lex Gerek"
oLink.Save

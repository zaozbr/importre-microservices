import win32com.client, os
path = r'C:\Users\Usuario\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\ImportreSupervisor.lnk'
shell = win32com.client.Dispatch('WScript.Shell')
s = shell.CreateShortcut(path)
s.TargetPath = r'C:\Users\Usuario\AppData\Local\Programs\Python\Python314\python.exe'
s.Arguments = r'-u D:\roms\library\roms\psx\importre_supervisor.py'
s.WorkingDirectory = r'D:\roms\library\roms\psx'
s.WindowStyle = 7
s.Save()
print('updated', path)

import winshell, sys
try:
    s = winshell.shortcut(r'C:\Users\Usuario\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\ImportreSupervisor.lnk')
    print('Target:', s.path)
    print('Args:', s.arguments)
    print('Working:', s.working_directory)
except Exception as e:
    print('ERROR:', e)

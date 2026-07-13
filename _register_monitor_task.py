"""Registra tarefa agendada do Windows para manter o monitor sempre rodando."""
import subprocess
from pathlib import Path

PSX_DIR = Path(r"D:\roms\library\roms\psx")
PYTHON = r"C:\Users\Usuario\AppData\Local\Programs\Python\Python314\python.exe"
MONITOR = PSX_DIR / "_monitor_importre.py"
TASK_NAME = "ImportreMonitor"

# Comando XML para a tarefa
xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Monitor autonomo do importre PSX — reinicia supervisores e corrige travamentos</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
    <BootTrigger>
      <Enabled>true</Enabled>
    </BootTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>false</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{PYTHON}</Command>
      <Arguments>"{MONITOR}"</Arguments>
      <WorkingDirectory>{PSX_DIR}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""

xml_path = PSX_DIR / "_monitor_task.xml"
xml_path.write_text(xml, encoding="utf-16")

# Deletar tarefa antiga se existir
subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"], capture_output=True)

# Registrar nova tarefa
result = subprocess.run(
    ["schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(xml_path), "/F"],
    capture_output=True, text=True
)
print("stdout:", result.stdout)
print("stderr:", result.stderr)
print("returncode:", result.returncode)

if result.returncode == 0:
    print(f"Tarefa '{TASK_NAME}' registrada com sucesso.")
else:
    print("Falha ao registrar tarefa.")

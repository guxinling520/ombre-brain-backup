@echo off
schtasks /create /tn "CyberbossAutoMaintain" /tr "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File \"C:\Users\Lenovo\.cyberboss\scripts\auto-maintain.ps1\"" /sc daily /st 00:30 /f
schtasks /create /tn "CyberbossAutoMaintain-Noon" /tr "powershell.exe -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File \"C:\Users\Lenovo\.cyberboss\scripts\auto-maintain.ps1\"" /sc daily /st 12:30 /f
echo Done
pause

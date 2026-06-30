# register-task.ps1 — 注册 Cyberboss 自动维护定时任务

$TaskName = "CyberbossAutoMaintain"
$ScriptPath = "C:\Users\Lenovo\.cyberboss\scripts\auto-maintain.ps1"

# Unregister old task if exists
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# Create action
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ScriptPath`""

# Two triggers: 00:30 (archive new chats) and 12:30 (mid-day refresh)
$Trigger1 = New-ScheduledTaskTrigger -Daily -At 00:30
$Trigger2 = New-ScheduledTaskTrigger -Daily -At 12:30

# Settings
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Principal
$Principal = New-ScheduledTaskPrincipal -UserId "Lenovo" -LogonType S4U -RunLevel Limited

# Register
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger1, $Trigger2 -Settings $Settings -Principal $Principal -Force

Write-Host "Task '$TaskName' registered successfully"
Get-ScheduledTask -TaskName $TaskName | Format-List TaskName, State, Triggers

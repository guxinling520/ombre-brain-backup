# auto-maintain.ps1 — Cyberboss 日常维护脚本
# 由 Windows 定时任务每天触发，或手动运行
# 执行：归档新聊天 → 日记同步 → 更新上下文 → baseline标记 → 闹钟桥接

$Cyberboss = "C:\Users\Lenovo\.cyberboss"
$LogFile = "$Cyberboss\logs\auto-maintain.log"
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

"[$Timestamp] 🟢 开始自动维护" | Out-File -FilePath $LogFile -Append

# 1. 归档新聊天记录
try {
    $env:PYTHONIOENCODING = "utf-8"
    $result = python3 "$Cyberboss\scripts\archive-chats.py" 2>&1
    "  [archive] $result" | Out-File -FilePath $LogFile -Append
} catch {
    "  [archive] ❌ 失败: $_" | Out-File -FilePath $LogFile -Append
}

# 2. 日记→时间轴同步（仅同步缺失日期，避免重复）
try {
    $env:CYBERBOSS_HOME = $Cyberboss
    $result = node "$Cyberboss\diary-to-timeline.mjs" --missing 2>&1
    foreach ($line in $result) { "  [timeline] $line" | Out-File -FilePath $LogFile -Append }
} catch {
    "  [timeline] ❌ 失败: $_" | Out-File -FilePath $LogFile -Append
}

# 3. 更新上下文快照
try {
    $result = python3 "$Cyberboss\scripts\update-context.py" 2>&1
    "  [context] $result" | Out-File -FilePath $LogFile -Append
} catch {
    "  [context] ❌ 失败: $_" | Out-File -FilePath $LogFile -Append
}

# 4. 生成 baseline 待处理标记（提醒 AI 从日记抽取变化到 baseline）
$TodayDate = Get-Date -Format "yyyy-MM-dd"
$PendingFile = "$Cyberboss\context\.baseline-pending.md"
@"
# baseline pending
generated: $Timestamp
diary: $TodayDate

read today's diary and update baseline if needed:
1. new behavior patterns -> patterns.md
2. updated personal facts -> facts.md
3. preference changes -> preferences.md
4. milestone events -> milestones.md
5. other notable judgments/decisions

delete this file after done.
"@ | Out-File -FilePath $PendingFile -Encoding utf8
"  [baseline] flag -> .baseline-pending.md" | Out-File -FilePath $LogFile -Append

# 5. 提醒→闹钟桥接（到期提醒自动推送手机闹钟）
try {
    $result = python3 "$Cyberboss\scripts\reminder-alarm-bridge.py" 2>&1
    "  [alarm] $result" | Out-File -FilePath $LogFile -Append
} catch {
    "  [alarm] ❌ 失败: $_" | Out-File -FilePath $LogFile -Append
}

$EndTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$EndTime] ✅ 维护完成" | Out-File -FilePath $LogFile -Append
"" | Out-File -FilePath $LogFile -Append

Write-Host "✅ 维护完成"

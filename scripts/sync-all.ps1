# sync-all.ps1 --- nightly full-link sync
param(
    [string]$Date = "",
    [switch]$BuildOnly = $false
)

$Cyberboss = "C:\Users\Lenovo\.cyberboss"
$Scripts = "$Cyberboss\scripts"
$LogDir = "$Cyberboss\logs"
$LogFile = "$LogDir\sync-all.log"

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$Timestamp] START sync-all" | Out-File -FilePath $LogFile -Append

if (-not $Date) { $Date = Get-Date -Format "yyyy-MM-dd" }
"  [date] $Date" | Out-File -FilePath $LogFile -Append

# --- Step 1: diary -> timeline ---
if (-not $BuildOnly) {
    try {
        $env:CYBERBOSS_HOME = $Cyberboss
        $result = node "$Cyberboss\diary-to-timeline.mjs" $Date 2>&1
        foreach ($line in $result) { "  [timeline] $line" | Out-File -FilePath $LogFile -Append }
        Write-Host "  [OK] timeline synced" -ForegroundColor Green
    } catch {
        "  [timeline] FAIL: $_" | Out-File -FilePath $LogFile -Append
        Write-Host "  [FAIL] timeline: $_" -ForegroundColor Red
    }
}

# --- Step 2: rebuild timeline site ---
try {
    $result = node "F:/cyberboss_new/cyberboss/node_modules/timeline-for-agent/bin/timeline-for-agent.js" build 2>&1
    foreach ($line in $result) { "  [site] $line" | Out-File -FilePath $LogFile -Append }
    Write-Host "  [OK] site rebuilt" -ForegroundColor Green
} catch {
    "  [site] FAIL: $_" | Out-File -FilePath $LogFile -Append
    Write-Host "  [FAIL] site: $_" -ForegroundColor Red
}

# --- Step 3: OB -> GitHub backup ---
try {
    $OB_Vault = "C:\Users\Lenovo\Documents\我的OB库"
    Set-Location $OB_Vault
    $out = git add -A 2>&1
    $changed = git diff --cached --name-only 2>&1
    if ($changed) {
        # Use proxy only if available
        $proxy = "http://127.0.0.1:7890"
        try { $null = curl.exe -s --max-time 2 $proxy 2>$null } catch { $proxy = $null }
        $gitCmd = if ($proxy) { "git -c http.proxy=`"$proxy`"" } else { "git" }
        Invoke-Expression "$gitCmd commit -m 'diary sync $(Get-Date -Format 'yyyy-MM-dd HH:mm')' 2>&1" | Out-Null
        Invoke-Expression "$gitCmd push origin master 2>&1" | ForEach-Object { "  [github] $_" | Out-File -FilePath $LogFile -Append }
        Write-Host "  [OK] OB pushed to GitHub" -ForegroundColor Green
    } else {
        "  [github] nothing to commit" | Out-File -FilePath $LogFile -Append
        Write-Host "  [OK] OB up to date" -ForegroundColor Green
    }
} catch {
    "  [github] FAIL: $_" | Out-File -FilePath $LogFile -Append
    Write-Host "  [FAIL] GitHub push: $_" -ForegroundColor Red
}

# --- Step 4: baseline pending flag ---
$FlagFile = "$Cyberboss/context/.baseline-pending.md"
@"
# baseline pending
generated: $Timestamp
diary: $Date

check diary for:
1. new behavior patterns -> patterns.md
2. updated personal facts -> facts.md
3. preference changes -> preferences.md
4. milestone events -> milestones.md
5. other notable judgments/decisions

delete this file after done.
"@ | Out-File -FilePath $FlagFile -Encoding utf8
"  [baseline] flag created -> .baseline-pending.md" | Out-File -FilePath $LogFile -Append
Write-Host "  [INFO] check .baseline-pending.md" -ForegroundColor Yellow

# --- Step 5: chat archive ---
try {
    $env:PYTHONIOENCODING = "utf-8"
    $result = python3 "$Scripts\archive-chats.py" 2>&1
    "  [archive] $result" | Out-File -FilePath $LogFile -Append
} catch {
    "  [archive] FAIL: $_" | Out-File -FilePath $LogFile -Append
}

# --- Step 6: cyberboss -> GitHub backup ---
try {
    Set-Location $Cyberboss
    $out = git add -A 2>&1
    $changed = git diff --cached --name-only 2>&1
    if ($changed) {
        $proxy = "http://127.0.0.1:7890"
        try { $null = curl.exe -s --max-time 2 $proxy 2>$null } catch { $proxy = $null }
        $gitCmd = if ($proxy) { "git -c http.proxy=`"$proxy`"" } else { "git" }
        Invoke-Expression "$gitCmd commit -m 'cyberboss sync $(Get-Date -Format 'yyyy-MM-dd HH:mm')' 2>&1" | Out-Null
        Invoke-Expression "$gitCmd push origin master 2>&1" | ForEach-Object { "  [cb-github] $_" | Out-File -FilePath $LogFile -Append }
        Write-Host "  [OK] cyberboss pushed to GitHub" -ForegroundColor Green
    } else {
        "  [cb-github] nothing to commit" | Out-File -FilePath $LogFile -Append
        Write-Host "  [OK] cyberboss up to date" -ForegroundColor Green
    }
} catch {
    "  [cb-github] FAIL: $_" | Out-File -FilePath $LogFile -Append
    Write-Host "  [FAIL] cyberboss GitHub push: $_" -ForegroundColor Red
}

# --- done ---
$EndTime = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
"[$EndTime] DONE sync-all" | Out-File -FilePath $LogFile -Append
"" | Out-File -FilePath $LogFile -Append

Write-Host ""
Write-Host "[DONE] sync-all complete" -ForegroundColor Green
Write-Host "  log: $LogFile" -ForegroundColor Cyan

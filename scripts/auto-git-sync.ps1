# auto-git-sync.ps1 — lightweight git commit + push for cyberboss memory data
# Called by Windows Task Scheduler. No logs, no timeline rebuild, no archive.
param()

$Cyberboss = "C:\Users\Lenovo\.cyberboss"
Set-Location $Cyberboss

$out = git add -A 2>&1
$changed = git diff --cached --name-only 2>&1

if (-not $changed) {
    exit 0
}

$proxy = "http://127.0.0.1:7890"
try { $null = curl.exe -s --max-time 2 $proxy 2>$null } catch { $proxy = $null }
$gitCmd = if ($proxy) { "git -c http.proxy=`"$proxy`"" } else { "git" }

Invoke-Expression "$gitCmd commit -m 'auto-sync $(Get-Date -Format 'yyyy-MM-dd HH:mm')' 2>&1" | Out-Null
Invoke-Expression "$gitCmd push origin master 2>&1" | Out-Null

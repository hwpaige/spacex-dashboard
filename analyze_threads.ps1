# Raspberry Pi Thread Analysis Script
# This script SSHs into the Pi, identifies threads of the SpaceX Dashboard, and measures their load.

param(
    [string]$PiHost = "pi.local",
    [string]$Username = "harrison",
    [string]$Password = "hpaige",
    [string]$OutputFile = "thread_analysis_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
)

Write-Host "=== SpaceX Dashboard Thread Analysis ===" -ForegroundColor Cyan
Write-Host "Target: $Username@$PiHost" -ForegroundColor Yellow

$remoteScript = @'
#!/bin/bash
# Analysis script to run on the Pi

echo "=== SYSTEM STATE ==="
echo "Date: $(date)"
echo "CPU Temp: $(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{print $1/1000}')°C"
echo "Load Avg: $(cat /proc/loadavg)"
echo ""

# Find the main app PID
APP_PID=$(pgrep -f "app.py" | head -n 1)

if [ -z "$APP_PID" ]; then
    echo "ERROR: SpaceX Dashboard (app.py) not found running."
    exit 1
fi

echo "=== DASHBOARD PROCESS FOUND: PID $APP_PID ==="
echo ""

echo "--- Thread List (TID, CPU%, Command) ---"
ps -L -p $APP_PID -o tid,pcpu,comm | sort -k2 -rn
echo ""

echo "--- Detailed Thread Resource Usage (top -H) ---"
# Run top for a few seconds to get meaningful CPU percentages for threads
top -H -b -n 2 -d 1 -p $APP_PID | awk '/PID USER/{p=1} p' | tail -n +1
echo ""

echo "--- Memory Map Summary ---"
pmap -x $APP_PID | tail -n 1
echo ""

echo "--- Open Files and Sockets (by thread) ---"
lsof -p $APP_PID | head -n 20
echo ""

echo "--- Recent Thread-Specific Logs ---"
APP_LOG="$HOME/Desktop/project/docs/app.log"
if [ ! -f "$APP_LOG" ]; then
    APP_LOG="$HOME/spacex-dashboard/docs/app.log"
fi
if [ ! -f "$APP_LOG" ]; then
    APP_LOG="$HOME/spacex-dashboard/src/app.log"
fi

if [ -f "$APP_LOG" ]; then
    echo "Last 50 log entries with thread/worker info:"
    grep -E "Updater|Loader|Thread|Backend" "$APP_LOG" | tail -n 50
else
    echo "App log not found."
fi

echo ""
echo "=== END OF ANALYSIS ==="
'@

# Fix line endings for Linux bash
$fixedScript = $remoteScript -replace "`r`n", "`n"

Write-Host "Connecting to Pi and running thread analysis..." -ForegroundColor Yellow
try {
    # Pipe the fixed script to ssh
    $result = $fixedScript | ssh "$Username@$PiHost" "bash -s" 2>&1
} catch {
    Write-Error "Failed to connect to Pi: $($_.Exception.Message)"
    exit 1
}

# Save results
$result | Out-File -FilePath $OutputFile -Encoding UTF8

Write-Host ""
Write-Host "Analysis complete! Results saved to $OutputFile" -ForegroundColor Green
Write-Host ""

# Quick summary of the most heavy threads
$heavyThreads = $result | Select-String "--- Thread List" -Context 0, 10
Write-Host "Top Threads by CPU usage:" -ForegroundColor Cyan
$heavyThreads | ForEach-Object { Write-Host $_ }

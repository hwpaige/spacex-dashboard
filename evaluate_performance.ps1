# Raspberry Pi Performance Evaluation Script
# This script SSHs into the Pi, evaluates performance, and identifies bottlenecks.

param(
    [string]$PiHost = "pi.local",
    [string]$Username = "harrison",
    [string]$Password = "hpaige",
    [string]$OutputFile = "performance_evaluation_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
)

Write-Host "=== SpaceX Dashboard Performance Evaluation ===" -ForegroundColor Cyan
Write-Host "Target: $Username@$PiHost" -ForegroundColor Yellow

$remoteScript = @"
#!/bin/bash
# Analysis script to run on the Pi

echo "=== SYSTEM INFORMATION ==="
echo "Date: \$(date)"
echo "Uptime: \$(uptime)"
echo "CPU Temp: \$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{print \$1/1000}')°C"
echo ""

echo "=== RESOURCE USAGE ==="
echo "Memory Usage:"
free -h
echo ""
echo "CPU Load (last 1, 5, 15 min):"
cat /proc/loadavg
echo ""

echo "=== TOP PROCESSES (CPU) ==="
ps aux --sort=-%cpu | head -10
echo ""

echo "=== TOP PROCESSES (MEM) ==="
ps aux --sort=-%mem | head -10
echo ""

echo "=== APP-SPECIFIC ANALYSIS ==="
APP_LOG="\$HOME/spacex-dashboard/docs/app.log"
if [ ! -f "\$APP_LOG" ]; then
    APP_LOG="\$HOME/spacex-dashboard/src/app.log"
fi

if [ -f "\$APP_LOG" ]; then
    echo "Found app log at: \$APP_LOG"
    echo ""
    echo "--- Slowest Boot Steps (from Profiler) ---"
    grep "PROFILER:" "\$APP_LOG" | tail -50 | awk -F'at ' '{print \$2, \$1}' | sort -rn | head -10
    
    echo ""
    echo "--- Recent Profiler Summary ---"
    # Find the last "Boot Performance Summary" and print until the end of it
    grep -A 20 "--- Boot Performance Summary ---" "\$APP_LOG" | tail -21
else
    echo "App log not found. Checked: ~/spacex-dashboard/docs/app.log and ~/spacex-dashboard/src/app.log"
fi

echo ""
echo "=== NETWORK STATUS ==="
nmcli device status 2>/dev/null || ip addr show
"@

Write-Host "Connecting to Pi and running analysis..." -ForegroundColor Yellow
Write-Host "(You may be prompted for the password: $Password)" -ForegroundColor Gray

# Attempt to use SSH. 
# Note: Automating password entry in plain SSH on Windows is tricky without extra tools.
# We'll use the standard SSH command.
try {
    $result = $remoteScript | ssh "$Username@$PiHost" "bash -s" 2>&1
} catch {
    Write-Error "Failed to connect to Pi: $($_.Exception.Message)"
    exit 1
}

# Save results
$result | Out-File -FilePath $OutputFile -Encoding UTF8

Write-Host ""
Write-Host "=== EVALUATION RESULTS SUMMARY ===" -ForegroundColor Cyan

# Parse results for quick display
$cpuLoad = $result | Where-Object { $_ -match "CPU Load" } | Select-Object -Skip 1 -First 1
$memUsage = $result | Where-Object { $_ -match "^Mem:" }
$temp = $result | Where-Object { $_ -match "CPU Temp:" }

Write-Host "System Load: $cpuLoad"
Write-Host "Memory:      $memUsage"
Write-Host "Temperature: $temp"

# Look for bottlenecks
Write-Host ""
Write-Host "=== IDENTIFIED POTENTIAL BOTTLENECKS ===" -ForegroundColor Red

$bottlenecksFound = $false

# 1. Check for multiple instances
$appInstances = $result | Select-String "app.py" | Measure-Object
if ($appInstances.Count -gt 2) {
    Write-Host "[!] Multiple instances of app.py detected. This wastes CPU and Memory." -ForegroundColor Red
    $bottlenecksFound = $true
}

# 2. Check for high CPU
if ($cpuLoad -match "(\d+\.\d+)") {
    $load = [double]$matches[1]
    if ($load -gt 1.5) {
        Write-Host "[!] High system load ($load). CPU is likely a bottleneck." -ForegroundColor Red
        $bottlenecksFound = $true
    }
}

# 3. Check for memory pressure
if ($memUsage -match "Mem:\s+(\d+[GKM]i?)\s+(\d+[GKM]i?)") {
    Write-Host "[i] Memory usage details: $memUsage" -ForegroundColor Yellow
}

# 4. Profiler analysis
$slowSteps = $result | Select-String "PROFILER:"
if ($slowSteps) {
    Write-Host "[i] Profiler logs found. Check $OutputFile for detailed boot timings." -ForegroundColor Yellow
}

if (-not $bottlenecksFound) {
    Write-Host "No obvious system-level bottlenecks detected. Check application logs for logic-level issues." -ForegroundColor Green
}

Write-Host ""
Write-Host "Full report saved to: $OutputFile" -ForegroundColor Cyan
Write-Host ""
Write-Host "=== PROPOSED OPTIMIZATION PLAN ===" -ForegroundColor Green
Write-Host "1. Review timer intervals in app.py (ensure they are > 1000ms for non-critical updates)."
Write-Host "2. Optimize trajectory calculations by reducing points or caching results."
Write-Host "3. Disable unnecessary QtWebEngine features/processes if memory is tight."
Write-Host "4. Use 'htop' on the Pi for real-time monitoring of process threads."

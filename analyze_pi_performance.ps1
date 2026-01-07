# Raspberry Pi Performance Analysis Script
# Run this script to SSH into the Pi and analyze performance

param(
    [string]$PiHost = "pi.local",
    [string]$Username = "harrison",
    [string]$Password = "hpaige",
    [string]$OutputFile = "pi_performance_analysis_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
)

Write-Host "=== Raspberry Pi Performance Analysis ===" -ForegroundColor Cyan
Write-Host "Connecting to $Username@$PiHost..." -ForegroundColor Yellow

# Create a script to run all commands in one SSH session
$remoteScript = @"
#!/bin/bash
echo "=== Raspberry Pi Performance Analysis ==="
echo "Date: \$(date)"
echo "Host: \$(hostname)"
echo ""

echo "=== RUNNING APP INSTANCES ==="
echo "SpaceX-related processes:"
ps aux | grep -i spacex | grep -v grep || echo "No SpaceX processes found"
echo ""
echo "Python processes:"
ps aux | grep python | grep -v grep || echo "No Python processes found"
echo ""
echo "app.py processes:"
ps aux | grep app.py | grep -v grep || echo "No app.py processes found"
echo ""

echo "=== SYSTEM RESOURCES ==="
echo "Uptime:"
uptime
echo ""
echo "Top processes:"
top -b -n1 | head -20
echo ""

echo "=== MEMORY USAGE ==="
free -h
echo ""
echo "VM Statistics (3 samples):"
vmstat 1 3
echo ""

echo "=== CPU INFORMATION ==="
echo "CPU Temperature (millidegrees C):"
cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo "Temperature sensor not available"
echo ""
echo "CPU Info:"
cat /proc/cpuinfo | grep 'model name\|cpu MHz' | head -2
echo ""

echo "=== NETWORK CONNECTIONS ==="
echo "Active connections:"
netstat -tlnp 2>/dev/null | head -20 || ss -tlnp 2>/dev/null | head -20 || echo "Network tools not available"
echo ""

echo "=== DISK USAGE ==="
df -h
echo ""
echo "Largest directories in /home:"
du -sh /home/* 2>/dev/null | sort -hr | head -10 || echo "No accessible home directories"
echo ""

echo "=== I/O STATISTICS ==="
iostat -x 1 2 2>/dev/null || echo "iostat not available - install sysstat package"
echo ""

echo "=== TOP PROCESSES ==="
echo "Top CPU consumers:"
ps aux --sort=-%cpu | head -10
echo ""
echo "Top memory consumers:"
ps aux --sort=-%mem | head -10
echo ""

echo "=== SYSTEM LOAD ==="
echo "Load averages:"
cat /proc/loadavg
echo ""

echo "=== ADDITIONAL INFO ==="
echo "Kernel version:"
uname -a
echo ""
echo "Available memory details:"
cat /proc/meminfo | head -10
echo ""

echo "Analysis complete."
"@

# Run all commands in one SSH session
Write-Host "Running performance analysis on Raspberry Pi..." -ForegroundColor Yellow
try {
    $result = $remoteScript | & ssh "$Username@$PiHost" "bash -s" 2>&1
}
catch {
    Write-Error "SSH command failed: $($_.Exception.Message)"
    exit 1
}

# Save output to file
Write-Host "Saving results to $OutputFile..." -ForegroundColor Yellow
$result | Out-File -FilePath $OutputFile -Encoding UTF8

Write-Host "Analysis complete! Results saved to $OutputFile" -ForegroundColor Green
Write-Host "" -ForegroundColor White

# Display summary on screen
Write-Host "=== QUICK SUMMARY ===" -ForegroundColor Cyan

# Parse results for summary
$lines = $result -split "`n"

# Count app instances
$appProcesses = $lines | Where-Object { $_ -match "SpaceX-related processes:" } | Select-Object -Skip 1 | Where-Object { $_ -and $_.Trim() -ne "" -and $_ -notmatch "^$" }
$appCount = ($appProcesses | Where-Object { $_ -notmatch "No SpaceX processes found" }).Count
Write-Host "SpaceX app instances running: $appCount" -ForegroundColor $(if ($appCount -gt 1) { "Red" } else { "Green" })

# Check memory
$memLine = $lines | Where-Object { $_ -match "^Mem:" } | Select-Object -First 1
if ($memLine) {
    Write-Host "Memory usage: $memLine" -ForegroundColor Yellow
}

# Check temperature
$tempLine = $lines | Where-Object { $_ -match "^\d+$" } | Where-Object { $lines[$lines.IndexOf($_) - 1] -match "CPU Temperature" } | Select-Object -First 1
if ($tempLine) {
    try {
        $tempC = [math]::Round([int]$tempLine / 1000, 1)
        $tempColor = if ($tempC -gt 80) { "Red" } elseif ($tempC -gt 60) { "Yellow" } else { "Green" }
        Write-Host "CPU Temperature: ${tempC}°C" -ForegroundColor $tempColor
    } catch {
        Write-Host "CPU Temperature: $tempLine" -ForegroundColor Yellow
    }
}

# Check load average
$loadLine = $lines | Where-Object { $_ -match "^\d+\.\d+ \d+\.\d+ \d+\.\d+" } | Select-Object -First 1
if ($loadLine) {
    Write-Host "System load: $loadLine" -ForegroundColor Yellow
}

Write-Host "" -ForegroundColor White
Write-Host "Full results available in: $OutputFile" -ForegroundColor Cyan
Write-Host "Review the output file for detailed performance analysis and optimization recommendations." -ForegroundColor White
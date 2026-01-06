#!/bin/bash

# Raspberry Pi Performance Analysis Script
# Run this script to analyze performance on the Raspberry Pi
# Usage: ./analyze_pi_performance.sh [output_file]

OUTPUT_FILE="${1:-pi_performance_analysis_$(date +%Y%m%d_%H%M%S).txt}"

echo "=== Raspberry Pi Performance Analysis ==="
echo "Date: $(date)"
echo "Host: $(hostname)"
echo ""

# Function to run command and capture output
run_cmd() {
    echo "Running: $1"
    eval "$1" 2>&1
    echo ""
}

# Initialize output file
{
echo "=== Raspberry Pi Performance Analysis ==="
echo "Date: $(date)"
echo "Host: $(hostname)"
echo ""

# 1. Check running instances of the app
echo "=== RUNNING APP INSTANCES ==="
run_cmd "ps aux | grep -i spacex | grep -v grep"
run_cmd "ps aux | grep python | grep -v grep"
run_cmd "ps aux | grep app.py | grep -v grep"

# 2. System resource usage
echo "=== SYSTEM RESOURCES ==="
run_cmd "uptime"
run_cmd "top -b -n1 | head -20"

# 3. Memory usage
echo "=== MEMORY USAGE ==="
run_cmd "free -h"
run_cmd "vmstat 1 3"

# 4. CPU usage and temperature
echo "=== CPU INFORMATION ==="
run_cmd "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 'Temperature sensor not available'"
run_cmd "cat /proc/cpuinfo | grep 'model name\|cpu MHz' | head -2"

# 5. Network connections
echo "=== NETWORK CONNECTIONS ==="
run_cmd "netstat -tlnp 2>/dev/null | head -20 || ss -tlnp 2>/dev/null | head -20"

# 6. Disk usage
echo "=== DISK USAGE ==="
run_cmd "df -h"
run_cmd "du -sh /home/* 2>/dev/null | sort -hr | head -10"

# 7. Check for performance bottlenecks
echo "=== I/O STATISTICS ==="
run_cmd "iostat -x 1 2 2>/dev/null || echo 'iostat not available - install with: sudo apt install sysstat'"

# 8. Check Python process details
echo "=== TOP PROCESSES ==="
run_cmd "ps aux --sort=-%cpu | head -10"
run_cmd "ps aux --sort=-%mem | head -10"

# 9. Check system load
echo "=== SYSTEM LOAD ==="
run_cmd "cat /proc/loadavg"

# 10. Additional diagnostics
echo "=== ADDITIONAL DIAGNOSTICS ==="
run_cmd "dmesg | tail -10"
run_cmd "journalctl -n 10 --no-pager 2>/dev/null || echo 'journalctl not available'"

} > "$OUTPUT_FILE"

echo "Analysis complete! Results saved to $OUTPUT_FILE"
echo ""
echo "=== QUICK SUMMARY ==="

# Count app instances
APP_COUNT=$(ps aux | grep -i spacex | grep -v grep | wc -l)
echo "SpaceX app instances running: $APP_COUNT"
if [ "$APP_COUNT" -gt 1 ]; then
    echo "WARNING: Multiple instances detected!" >&2
fi

# Check memory
echo "Memory usage:"
free -h | grep "Mem:"

# Check temperature
if [ -f /sys/class/thermal/thermal_zone0/temp ]; then
    TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)
    TEMP_C=$(echo "scale=1; $TEMP / 1000" | bc 2>/dev/null || echo "N/A")
    echo "CPU Temperature: ${TEMP_C}°C"
    if [ "$(echo "$TEMP_C > 80" | bc 2>/dev/null)" = "1" ]; then
        echo "WARNING: High temperature detected!" >&2
    fi
fi

echo ""
echo "Full results available in: $OUTPUT_FILE"
echo "Review the output file for detailed performance analysis."
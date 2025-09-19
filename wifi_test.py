#!/usr/bin/env python3
"""
WiFi Test Script for SpaceX Dashboard
Tests the updated WiFi functionality that works with systemd-networkd
"""

import subprocess
import sys
import time

def run_command(cmd, description):
    """Run a command and return the result"""
    try:
        print(f"\n--- {description} ---")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        print(f"Command: {' '.join(cmd)}")
        print(f"Return code: {result.returncode}")
        if result.stdout:
            print(f"Output:\n{result.stdout}")
        if result.stderr:
            print(f"Error:\n{result.stderr}")
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        print(f"Error running command: {e}")
        return False, "", str(e)

def test_wifi_interface():
    """Test WiFi interface detection"""
    print("=== WiFi Interface Test ===")

    interfaces = ['wlan0', 'wlp2s0', 'wlp3s0', 'wlx000000000000']
    found_interface = None

    for interface in interfaces:
        success, stdout, stderr = run_command(['ip', 'link', 'show', interface], f"Check {interface}")
        if success:
            found_interface = interface
            break

    if not found_interface:
        print("❌ No WiFi interface found")
        return False

    print(f"✅ Found WiFi interface: {found_interface}")

    # Test iw command
    success, stdout, stderr = run_command(['iw', 'dev', found_interface, 'info'], f"Test iw on {found_interface}")
    if success:
        print("✅ iw command works")
    else:
        print("❌ iw command failed - may need sudo or installation")

    return True

def test_wifi_status():
    """Test WiFi connection status"""
    print("\n=== WiFi Status Test ===")

    interfaces = ['wlan0', 'wlp2s0', 'wlp3s0', 'wlx000000000000']
    active_interface = None

    for interface in interfaces:
        success, stdout, stderr = run_command(['ip', 'addr', 'show', interface], f"Check IP on {interface}")
        if success and 'inet ' in stdout:
            active_interface = interface
            print(f"✅ {interface} has IP address - likely connected")
            break

    if not active_interface:
        print("❌ No interface with IP address found")
        return False

    # Test iw link
    success, stdout, stderr = run_command(['iw', 'dev', active_interface, 'link'], f"Check link status on {active_interface}")
    if success and 'SSID:' in stdout:
        ssid_match = None
        for line in stdout.split('\n'):
            if 'SSID:' in line:
                ssid_match = line.split('SSID:', 1)[1].strip()
                break
        if ssid_match:
            print(f"✅ Connected to SSID: {ssid_match}")
        else:
            print("✅ Connected to WiFi (SSID not parsed)")
    else:
        print("❌ Not connected to WiFi or iw link failed")

    return True

def test_wifi_scan():
    """Test WiFi scanning"""
    print("\n=== WiFi Scan Test ===")

    interfaces = ['wlan0', 'wlp2s0', 'wlp3s0', 'wlx000000000000']
    wifi_interface = None

    for interface in interfaces:
        success, stdout, stderr = run_command(['ip', 'link', 'show', interface], f"Check {interface} exists")
        if success:
            wifi_interface = interface
            break

    if not wifi_interface:
        print("❌ No WiFi interface found for scanning")
        return False

    # Try scan with sudo first, then without
    scan_commands = [
        ['sudo', 'iw', 'dev', wifi_interface, 'scan'],
        ['iw', 'dev', wifi_interface, 'scan']
    ]

    scan_success = False
    for cmd in scan_commands:
        success, stdout, stderr = run_command(cmd, f"WiFi scan attempt with {' '.join(cmd)}")
        if success:
            networks = [line for line in stdout.split('\n') if line.startswith('BSS ')]
            print(f"✅ Scan successful - found {len(networks)} networks")
            scan_success = True
            break
        else:
            print(f"❌ Scan failed with {' '.join(cmd)}")

    if not scan_success:
        print("❌ All scan attempts failed")
        return False

    return True

def test_services():
    """Test required services"""
    print("\n=== Service Test ===")

    services = ['wpa_supplicant', 'systemd-networkd']
    all_good = True

    for service in services:
        success, stdout, stderr = run_command(['systemctl', 'is-active', service], f"Check {service} status")
        if success and 'active' in stdout.strip():
            print(f"✅ {service} is active")
        else:
            print(f"❌ {service} is not active")
            all_good = False

    return all_good

def main():
    """Main test function"""
    print("SpaceX Dashboard WiFi Test")
    print("=" * 40)

    tests = [
        ("WiFi Interface Detection", test_wifi_interface),
        ("Service Status", test_services),
        ("WiFi Connection Status", test_wifi_status),
        ("WiFi Scanning", test_wifi_scan),
    ]

    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test {test_name} failed with error: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "="*40)
    print("TEST SUMMARY")
    print("="*40)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1

    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("🎉 All tests passed! WiFi functionality should work in your app.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        print("💡 Try running with sudo: sudo python3 wifi_test.py")

    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

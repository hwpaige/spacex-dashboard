#!/usr/bin/env python3
"""
Generate track maps for all 2025 F1 circuits
"""
import json
import os
from sys import path
path.append('../src')
from track_generator import generate_track_map

def main():
    # Load F1 cache data
    cache_file = '../cache/f1_cache.json'
    if not os.path.exists(cache_file):
        print(f"Error: {cache_file} not found")
        return

    with open(cache_file, 'r') as f:
        data = json.load(f)

    # Extract unique circuits from the schedule
    circuits = set()
    for race in data['data']['schedule']:
        circuit_name = race['circuit_short_name']
        circuits.add(circuit_name)

    print(f"Found {len(circuits)} circuits in 2025 season:")
    for circuit in sorted(circuits):
        print(f"  - {circuit}")

    # Generate track maps for all circuits
    print("\nGenerating track maps...")
    generated = 0
    failed = 0

    for circuit in sorted(circuits):
        try:
            print(f"Generating map for {circuit}...")
            result = generate_track_map(circuit)
            if result:
                print(f"  ✓ Success: {result}")
                generated += 1
            else:
                print(f"  ✗ Failed: {circuit}")
                failed += 1
        except Exception as e:
            print(f"  ✗ Error for {circuit}: {e}")
            failed += 1

    print(f"\nSummary: {generated} generated, {failed} failed")

if __name__ == "__main__":
    main()
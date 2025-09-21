from track_generator import generate_track_map

# Test generating track maps for a few circuits
circuits = ['Silverstone']

for circuit in circuits:
    print(f"Generating track map for {circuit}...")
    path = generate_track_map(circuit)
    if path:
        print(f"Generated: {path}")
    else:
        print(f"Failed to generate for {circuit}")
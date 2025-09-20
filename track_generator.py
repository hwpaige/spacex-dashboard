import numpy as np
import pandas as pd
import fastf1
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import os

# Track rotations for F1 circuits
track_rotations = [('Sakhir', 92.0), ('Jeddah', 104.0), ('Melbourne', 44.0), ('Baku', 357.0), ('Miami', 2.0), ('Monte Carlo', 62.0), ('Catalunya', 95.0), ('Montreal', 62.0), ('Silverstone', 92.0), ('Hungaroring', 40.0), ('Spa-Francorchamps', 91.0), ('Zandvoort', 0.0), ('Monza', 95.0), ('Singapore', 335.0), ('Suzuka', 49.0), ('Lusail', 61.0), ('Austin', 0.0), ('Mexico City', 36.0), ('Interlagos', 0.0), ('Las Vegas', 90.0), ('Yas Marina Circuit', 335.0), ('Shanghai', 45.0), ('Imola', 45.0), ('Red Bull Ring', 45.0)]

# Circuit name mapping from 2025 schedule to track_rotations keys
circuit_name_mapping = {
    'Albert Park Circuit': 'Melbourne',
    'Shangai International Circuit': 'Shanghai',
    'Suzuka International Circuit': 'Suzuka',
    'Bahrain International Circuit': 'Sakhir',
    'Jeddah Corniche Circuit': 'Jeddah',
    'Miami International Autodrome': 'Miami',
    'Imola Autodromo Internazionale Enzo e Dino Ferrari': 'Imola',
    'Circuit de Monaco': 'Monte Carlo',
    'Circuit de Barcelona-Catalunya': 'Catalunya',
    'Circuit Gilles Villeneuve': 'Montreal',
    'Red Bull Ring': 'Red Bull Ring',
    'Silverstone Circuit': 'Silverstone',
    'Circuit de Spa-Francorchamps': 'Spa-Francorchamps',
    'Hungaroring': 'Hungaroring',
    'Circuit Zandvoort': 'Zandvoort',
    'Autodromo Nazionale Monza': 'Monza',
    'Baku City Circuit': 'Baku',
    'Marina Bay Street Circuit': 'Singapore',
    'Circuit of The Americas': 'Austin',
    'Autódromo Hermanos Rodríguez': 'Mexico City',
    'Autodromo José Carlos Pace | Interlagos': 'Interlagos',
    'Las Vegas Strip Circuit': 'Las Vegas',
    'Lusail International Circuit': 'Lusail',
    'Yas Marina Circuit': 'Yas Marina Circuit'
}

# Rotation function
def rotate(xy, *, angle):
    rot_mat = np.array([[np.cos(angle), np.sin(angle)],
                        [-np.sin(angle), np.cos(angle)]])
    return np.matmul(xy, rot_mat)

# Generate track map for a circuit
def generate_track_map(circuit):
    # Map circuit name to track_rotations key
    rotation_key = circuit_name_mapping.get(circuit, circuit)
    
    cache_dir = os.path.join(os.path.dirname(__file__), 'cache')
    os.makedirs(cache_dir, exist_ok=True)
    # Sanitize circuit name for filename (remove/replace invalid characters)
    safe_circuit_name = circuit.replace('|', '-').replace('/', '-').replace('\\', '-').replace(':', '-').replace('*', '-').replace('?', '-').replace('"', '-').replace('<', '-').replace('>', '-')
    png_file = os.path.join(cache_dir, f'{safe_circuit_name}_track.png')
    
    if os.path.exists(png_file):
        print(f"Cache hit: {png_file}")
        return png_file
    
    try:
        print(f"Fetching data for {circuit} (using rotation key: {rotation_key})...")
        # Get data from fastf1
        year = 2023  # Use a recent year for track data
        session = fastf1.get_session(year, rotation_key, 'Race')
        session.load()
        
        pos = session.laps.pick_fastest().get_pos_data()
        circuit_info = session.get_circuit_info()
        
        print(f"Processing track data for {circuit}...")
        track = pos[['X', 'Y']].to_numpy()
        track_angle = [rotation for name, rotation in track_rotations if name == rotation_key][0] / 180 * np.pi
        rotated_track = rotate(track, angle=track_angle)

        # Scale
        scale_factor = 1.5
        rotated_track *= scale_factor

        # Close the loop
        rotated_track = np.vstack([rotated_track, rotated_track[0]])

        # Calculate start-finish line direction (perpendicular to track direction)
        # Use the first few points to determine track direction
        if len(rotated_track) > 5:
            # Calculate direction vector from first few points
            direction = rotated_track[5] - rotated_track[0]  # Point a bit ahead minus start
            direction = direction / np.linalg.norm(direction)  # Normalize
            
            # Perpendicular vector (rotate 90 degrees)
            perp_direction = np.array([-direction[1], direction[0]])
            
            # Start-finish line length (relative to track scale)
            line_length = 200 * scale_factor
            
            # Start-finish line endpoints
            start_pos = rotated_track[0]
            start_finish_line = np.array([
                start_pos - perp_direction * line_length / 2,
                start_pos + perp_direction * line_length / 2
            ])
        else:
            # Fallback for very short tracks
            start_pos = rotated_track[0]
            start_finish_line = np.array([
                [start_pos[0], start_pos[1] - 200 * scale_factor],
                [start_pos[0], start_pos[1] + 200 * scale_factor]
            ])

        # Create figure with higher resolution
        fig, ax = plt.subplots(figsize=(8, 6), dpi=200)
        ax.plot(rotated_track[:, 0], rotated_track[:, 1], color='#636efa', linewidth=5, solid_capstyle='round')
        ax.plot(start_finish_line[:, 0], start_finish_line[:, 1], color='red', linewidth=2)

        # Style
        ax.set_facecolor('none')
        fig.patch.set_facecolor('none')
        ax.axis('off')
        ax.set_aspect('equal')
        
        plt.savefig(png_file, bbox_inches='tight', pad_inches=0, transparent=True)
        plt.close(fig)
        
        print(f"Generated track map PNG for {circuit}: {png_file}")
        return png_file
    except Exception as e:
        print(f"Error generating track map for {circuit}: {e}")
        import traceback
        traceback.print_exc()
        return None
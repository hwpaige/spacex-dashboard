import pandas as pd
import fastf1
import os

circuit_names = ('Sakhir', 'Jeddah', 'Melbourne', 'Baku', 'Miami', 'Monte Carlo', 'Catalunya', 'Montreal', 'Silverstone', 'Hungaroring', 'Spa-Francorchamps', 'Zandvoort', 'Monza', 'Singapore', 'Suzuka', 'Lusail', 'Austin', 'Mexico City', 'Interlagos', 'Las Vegas', 'Yas Marina Circuit')

# Function to save position data to CSV
def save_position_data_to_csv(circuit_names):
    base_dir = r"C:\Users\hpaige\PycharmProjects\F1_Dash\Circuits\Tracks"
    all_rotations = []
    for circuit in circuit_names:
        year = 2023
        print(f"Getting position data for {circuit} {year}")
        # Assume each meeting has only one session for simplification
        session_name = "Race"  # Adjust based on actual data

        # Use fastf1 to get session and load data
        session = fastf1.get_session(year, circuit, session_name)
        session.load()

        # Get position data
        circuit_info = session.get_circuit_info()
        circuit_rotation = circuit_info.rotation
        all_rotations.append((circuit, circuit_rotation))
        print(f"Rotation for {circuit}: {circuit_rotation}")


    # Print full list of rotations
    print("All Rotations:", all_rotations)


if __name__ == "__main__":
    save_position_data_to_csv(circuit_names)

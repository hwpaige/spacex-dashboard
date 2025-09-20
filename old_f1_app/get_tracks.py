import pandas as pd
import fastf1
import os

circuit_names = ('Sakhir', 'Jeddah', 'Melbourne', 'Baku', 'Miami', 'Monte Carlo', 'Catalunya', 'Montreal', 'Silverstone', 'Hungaroring', 'Spa-Francorchamps', 'Zandvoort', 'Monza', 'Singapore', 'Suzuka', 'Lusail', 'Austin', 'Mexico City', 'Interlagos', 'Las Vegas', 'Yas Marina Circuit')

# Function to save position data to CSV
def save_position_data_to_csv(circuit_names):
    base_dir = r"C:\Users\hpaige\PycharmProjects\F1_Dash\Circuits\Tracks"
    for circuit in circuit_names:
        year = 2023
        print(f"Getting position data for {circuit} {year}")
        # Assume each meeting has only one session for simplification
        session_name = "Race"  # Adjust based on actual data

        # Use fastf1 to get session and load data
        session = fastf1.get_session(year, circuit, session_name)
        session.load()

        # Get position data
        pos_data = session.laps.pick_fastest().get_pos_data()

        # Convert position data to DataFrame
        pos_data_df = pd.DataFrame(pos_data)

        # Save DataFrame to CSV
        filename = os.path.join(base_dir, f"{year}_{circuit}_track.csv")
        pos_data_df.to_csv(filename, index=False)
        print(f"Saved: {filename}")


if __name__ == "__main__":
    save_position_data_to_csv(circuit_names)

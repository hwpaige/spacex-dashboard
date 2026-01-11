import paramiko
import sys
import re

def check_pi_brightness():
    host = "pi.local"
    user = "harrison"
    password = "hpaige"
    
    print(f"Connecting to {user}@{host}...")
    
    try:
        # Initialize SSH client
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=user, password=password, timeout=10)
        
        def run_sudo_command(command):
            print(f"\n--- Executing: {command} ---")
            # Using get_pty=True is essential for sudo to prompt correctly
            stdin, stdout, stderr = client.exec_command(f"sudo -S {command}", get_pty=True)
            
            # Send the password to the sudo prompt
            stdin.write(password + '\n')
            stdin.flush()
            
            # Read and print the output in real-time
            full_output = ""
            for line in stdout:
                # Filter out the sudo password prompt if it appears
                if "[sudo] password for" not in line:
                    print(line.strip())
                    full_output += line
            
            return full_output

        # Step 1: Update and Install ddcutil
        run_sudo_command("apt update")
        run_sudo_command("apt install ddcutil -y")
        
        # Step 2: Load I2C module
        run_sudo_command("modprobe i2c-dev")
        
        # Verify it's loaded
        stdin, stdout, stderr = client.exec_command("lsmod | grep i2c_dev")
        lsmod_out = stdout.read().decode().strip()
        if lsmod_out:
            print(f"I2C module verified: {lsmod_out}")
        else:
            print("Warning: i2c_dev not found in lsmod.")

        # Step 3: Detect Monitors
        detect_out = run_sudo_command("ddcutil detect")
        
        # Step 4: Try to find the bus number for DFR1125
        # The user mentioned DFR1125 specifically
        bus_match = re.search(r"I2C bus:\s+/dev/i2c-(\d+)", detect_out)
        if bus_match:
            bus_num = bus_match.group(1)
            print(f"\nDetected I2C bus: {bus_num}")
            
            # Step 5: Query Capabilities
            run_sudo_command(f"ddcutil capabilities --bus={bus_num}")
            
            print(f"\nIf 'Brightness (code 10)' was listed above, you can try setting it:")
            print(f"  ddcutil setvcp --bus={bus_num} 10 50")
        else:
            print("\nCould not automatically identify the I2C bus from 'ddcutil detect' output.")
            print("Please check the output manually for your display.")

        client.close()
        print("\nDisconnected from Pi.")
        
    except Exception as e:
        print(f"\nError occurred: {e}")
        print("Make sure you can reach the Pi at 'pi.local' and have 'paramiko' installed.")
        print("To install paramiko: pip install paramiko")

if __name__ == "__main__":
    try:
        import paramiko
    except ImportError:
        print("Error: 'paramiko' library not found.")
        print("Please install it using: pip install paramiko")
        sys.exit(1)
        
    check_pi_brightness()

import paramiko
import sys

def identify_modes():
    hostname = "pi.local"
    username = "harrison"
    password = "hpaige"
    
    print(f"Connecting to {username}@{hostname}...")
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(hostname, username=username, password=password, timeout=10)
        print("Connected successfully!")
        
        commands = [
            "echo '--- DRM Modes ---'",
            "for f in /sys/class/drm/card*-*/modes; do echo \"$f:\"; cat \"$f\"; done",
            "echo '\n--- modetest (connectors) ---'",
            "sudo modetest -c",
            "echo '\n--- ddcutil detect ---'",
            "sudo ddcutil detect",
            "echo '\n--- ddcutil capabilities (Bus 13) ---'",
            "sudo ddcutil capabilities --bus=13",
            "echo '\n--- ddcutil Power Control (VCP d6) ---'",
            "sudo ddcutil getvcp d6 --bus=13",
            "echo '\n--- vcgencmd display_power ---'",
            "sudo vcgencmd display_power",
            "echo '\n--- Backlight devices ---'",
            "ls -l /sys/class/backlight/",
            "echo '\n--- Framebuffer blanking ---'",
            "cat /sys/class/graphics/fb0/blank 2>/dev/null || echo 'fb0/blank not found'"
        ]
        
        for cmd in commands:
            print(f"\nExecuting: {cmd}")
            # Use sudo -S to read password from stdin if needed
            if "sudo " in cmd:
                cmd = cmd.replace("sudo ", f"echo {password} | sudo -S ")
            
            stdin, stdout, stderr = client.exec_command(cmd)
            
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            # Filter out the [sudo] password prompt from stderr
            if error and f"[sudo] password for {username}:" in error:
                error = error.replace(f"[sudo] password for {username}:", "").strip()
            
            if output:
                print(output)
            if error:
                print(f"Error: {error}")
                
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        client.close()
        print("\nConnection closed.")

if __name__ == "__main__":
    identify_modes()

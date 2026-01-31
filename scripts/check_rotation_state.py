import paramiko
import sys

def check_rotation_state():
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
            "echo '--- OS Version ---'",
            "cat /etc/os-release | grep VERSION_ID",
            "echo '\n--- Active Service ---'",
            "systemctl is-active spacex-dashboard-eglfs",
            "systemctl is-active spacex-dashboard",
            "echo '\n--- kms.json content ---'",
            "cat /home/harrison/Desktop/project/src/kms.json",
            "echo '\n--- EGLFS Service Environment ---'",
            "systemctl show spacex-dashboard-eglfs --property=Environment",
            "echo '\n--- Screen Info (DRM) ---'",
            "for f in /sys/class/drm/card*-*/modes; do echo \"$f:\"; cat \"$f\"; done",
            "echo '\n--- Recent Logs (Rotation related) ---'",
            "journalctl -u spacex-dashboard-eglfs --since '10 minutes ago' | grep -i 'rotation'",
            "echo '\n--- App Log ---'",
            "tail -n 20 /home/harrison/app.log"
        ]
        
        for cmd in commands:
            print(f"\nExecuting: {cmd}")
            stdin, stdout, stderr = client.exec_command(cmd)
            output = stdout.read().decode().strip()
            if output:
                print(output)
            error = stderr.read().decode().strip()
            if error:
                print(f"Error: {error}")
                
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        client.close()
        print("\nConnection closed.")

if __name__ == "__main__":
    check_rotation_state()

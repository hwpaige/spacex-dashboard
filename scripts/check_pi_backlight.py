import paramiko

def run_pi_cmd(cmd):
    host = "pi.local"
    user = "harrison"
    password = "hpaige"
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password)
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    client.close()
    return out, err

if __name__ == "__main__":
    print("Backlight devices:")
    out, err = run_pi_cmd("ls /sys/class/backlight/")
    print(out if out else "None found")
    
    print("\nBrightness files:")
    out, err = run_pi_cmd("find /sys/class/backlight/ -name brightness")
    print(out if out else "None found")

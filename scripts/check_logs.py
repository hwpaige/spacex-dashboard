import paramiko

def check_logs():
    host = "192.168.68.80"
    user = "harrison"
    password = "hpaige"
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password)
    
    # Check for initial brightness fetch
    stdin, stdout, stderr = client.exec_command('grep "Backend: Initial DFR1125 brightness fetched" /home/harrison/app.log | tail')
    print("Initial fetch logs:")
    print(stdout.read().decode())
    
    # Check for any new brightness set logs
    stdin, stdout, stderr = client.exec_command('grep "Backend: Set DFR1125 brightness" /home/harrison/app.log | tail')
    print("Set brightness logs:")
    print(stdout.read().decode())
    
    # Check for errors
    stdin, stdout, stderr = client.exec_command('grep "ERROR - Backend: Failed to set brightness" /home/harrison/app.log | tail')
    print("Error logs:")
    print(stdout.read().decode())
    
    client.close()

if __name__ == "__main__":
    check_logs()

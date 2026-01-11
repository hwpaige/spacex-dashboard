import paramiko

def get_journal():
    host = "pi.local"
    user = "harrison"
    password = "hpaige"
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password)
    stdin, stdout, stderr = client.exec_command('sudo -S journalctl -u spacex-dashboard.service -n 200 --no-pager', get_pty=True)
    stdin.write(password + '\n')
    stdin.flush()
    print(stdout.read().decode())
    client.close()

if __name__ == "__main__":
    get_journal()

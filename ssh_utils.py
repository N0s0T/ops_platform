"""SSH 工具：SSHManager、批量执行、SFTP上传、命令安全校验"""
import os
import paramiko
from config import Config
from concurrent.futures import ThreadPoolExecutor, as_completed

class SSHManager:
    """SSH 连接管理器（上下文管理器，自动关闭连接）"""

    def __init__(self, host, port, username, password=None, pkey=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.pkey = pkey
        self.client = None

    def connect(self):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(
            hostname=self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            pkey=self.pkey,
            timeout=Config.SSH_TIMEOUT
        )

    def execute(self, command):
        if not self.client:
            self.connect()
        _, stdout, stderr = self.client.exec_command(command)
        output = stdout.read().decode('utf-8', errors='replace').strip()
        error = stderr.read().decode('utf-8', errors='replace').strip()
        exit_code = stdout.channel.recv_exit_status()
        return output, error, exit_code

    def upload_file(self, local_path, remote_path):
        if not self.client:
            self.connect()
        sftp = self.client.open_sftp()
        try:
            if remote_path.endswith('/'):
                remote_path = remote_path + os.path.basename(local_path)
            sftp.put(local_path, remote_path)
            return True
        finally:
            sftp.close()

    def test_connection(self):
        try:
            self.connect()
            self.execute('echo ok')
            return True, 'online'
        except Exception as e:
            return False, str(e)
        finally:
            self.close()

    def close(self):
        if self.client:
            self.client.close()
            self.client = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

def check_command_safety(command):
    for blocked in Config.COMMAND_BLACKLIST:
        if blocked in command:
            return False, f'禁止执行危险命令: {blocked}'
    return True, None

def batch_execute(hosts, command):
    is_safe, reason = check_command_safety(command)
    if not is_safe:
        return [{'success': False, 'host_name': '', 'error': reason}]

    results = []

    def run_on_host(host):
        try:
            with SSHManager(host.hostname, host.port, host.username, host.password) as ssh:
                output, error, exit_code = ssh.execute(command)
                return {
                    'success': exit_code == 0,
                    'host_id': host.id, 'host_name': host.name,
                    'hostname': host.hostname,
                    'output': output, 'error': error, 'exit_code': exit_code
                }
        except Exception as e:
            return {
                'success': False,
                'host_id': host.id, 'host_name': host.name,
                'hostname': host.hostname,
                'output': '', 'error': str(e), 'exit_code': -1
            }

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(run_on_host, host): host for host in hosts}
        for future in as_completed(futures):
            results.append(future.result())

    return results
